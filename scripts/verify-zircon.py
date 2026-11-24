#!/usr/bin/env python3
"""Check the local stock inputs and a packed zircon image without a phone."""

import argparse
import hashlib
import json
import struct
import subprocess
import sys
import tomllib
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def align(size, page):
    return (size + page - 1) // page * page


def section(data, offset, size):
    require(0 <= offset <= len(data) and 0 <= size <= len(data) - offset,
            f"Image section {offset}+{size} exceeds the image")
    return data[offset:offset + size]


def avb_footer(data):
    require(len(data) >= 64 and data[-64:-60] == b"AVBf", "Missing AVB footer")
    major, minor, size, offset, length = struct.unpack_from(">IIQQQ", data, len(data) - 60)
    require((major, minor) == (1, 0), "Unexpected AVB footer version")
    require(size <= offset and offset + length <= len(data) - 64, "Invalid AVB footer bounds")
    vbmeta = section(data, offset, length)
    require(vbmeta[:4] == b"AVB0", "Footer does not point to vbmeta")
    return {"image_size": size, "vbmeta_offset": offset, "vbmeta_size": length}, vbmeta


def vendor_boot(path):
    data = path.read_bytes()
    require(data[:8] == b"VNDRBOOT" and u32(data, 8) == 4, "Expected vendor_boot v4")
    page = u32(data, 12)
    require(page >= 512 and page & (page - 1) == 0, "Invalid page size")
    ramdisk_size, header_size, dtb_size = u32(data, 24), u32(data, 2096), u32(data, 2100)
    require(header_size == 2128, "Unexpected vendor_boot header size")
    ramdisk_at = align(header_size, page)
    dtb_at = ramdisk_at + align(ramdisk_size, page)
    table_at = dtb_at + align(dtb_size, page)
    table_size, count, entry_size, config_size = struct.unpack_from("<4I", data, 2112)
    require(count == 1 and entry_size == 108 and table_size == 108,
            "This zircon port requires exactly one 108-byte ramdisk fragment")
    table = section(data, table_at, table_size)
    require(u32(table, 0) == ramdisk_size and u32(table, 4) == 0, "Fragment bounds differ from the ramdisk")
    bootconfig_at = table_at + align(table_size, page)
    footer, vbmeta = avb_footer(data)
    end = bootconfig_at + align(config_size, page)
    require(end <= footer["image_size"], "Image sections overlap vbmeta")
    return {
        "data": data,
        "header": data[:24] + data[28:2112] + data[2128:header_size],
        "ramdisk": section(data, ramdisk_at, ramdisk_size),
        "dtb": section(data, dtb_at, dtb_size),
        "table_identity": table[8:],
        "bootconfig": section(data, bootconfig_at, config_size),
        "footer": footer,
        "vbmeta": vbmeta,
    }


def ramdisk_entries(compressed):
    require(compressed[:4] == bytes.fromhex("02214c18"), "Expected legacy LZ4 ramdisk framing")
    result = subprocess.run(["lz4", "-d", "-c"], input=compressed, capture_output=True, check=True)
    data, offset, entries = result.stdout, 0, {}
    while True:
        header = section(data, offset, 110)
        require(header[:6] in (b"070701", b"070702"), f"Invalid newc magic at {offset}")
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        size, name_size = fields[6], fields[11]
        require(name_size > 0, "Empty cpio name")
        name_bytes = section(data, offset + 110, name_size)
        require(name_bytes[-1:] == b"\0", "Unterminated cpio name")
        name = name_bytes[:-1].decode("utf-8")
        offset = align(offset + 110 + name_size, 4)
        content = section(data, offset, size)
        offset = align(offset + size, 4)
        if name == "TRAILER!!!":
            return entries
        require(name not in entries, f"Duplicate cpio entry: {name}")
        # The packer renumbers inodes; every other archived field stays.
        metadata = tuple(fields[1:6] + fields[7:11])
        entries[name] = {"metadata": metadata, "data": content}


def properties(data):
    values = {}
    for line in data.decode("utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            values[name] = value
    return values


def elf_info(data):
    require(data[:6] == b"\x7fELF\x02\x01" and struct.unpack_from("<H", data, 18)[0] == 183,
            "Expected an AArch64 ELF64 little-endian binary")
    ph_offset = struct.unpack_from("<Q", data, 32)[0]
    ph_size, ph_count = struct.unpack_from("<HH", data, 54)
    require(ph_size >= 56, "Invalid ELF program header size")
    interpreter, dynamic, loads = None, b"", []
    for i in range(ph_count):
        header = section(data, ph_offset + i * ph_size, 56)
        kind, _, offset, address, _, size, _, _ = struct.unpack("<II6Q", header)
        if kind == 1:
            loads.append((address, offset, size))
        elif kind == 2:
            dynamic = section(data, offset, size)
        elif kind == 3:
            interpreter = section(data, offset, size).rstrip(b"\0").decode("utf-8")
    needed, strings_at = [], None
    for offset in range(0, len(dynamic), 16):
        tag, value = struct.unpack_from("<qQ", dynamic, offset)
        if tag == 0:
            break
        if tag == 1:
            needed.append(value)
        elif tag == 5:
            strings_at = value
    libraries = []
    if needed:
        require(strings_at is not None, "ELF dependency strings are missing")
        offsets = [offset + strings_at - address for address, offset, size in loads
                   if address <= strings_at < address + size]
        require(len(offsets) == 1, "Cannot locate ELF dependency strings")
        for name in needed:
            start = offsets[0] + name
            end = data.find(b"\0", start)
            require(0 <= start <= end < len(data), "Invalid ELF dependency string")
            libraries.append(data[start:end].decode("utf-8"))
    return {"machine": "AArch64", "interpreter": interpreter, "needed": libraries}


def check_packed_avb(image):
    vbmeta = image["vbmeta"]
    require(u32(vbmeta, 28) == 0, "Packed vbmeta must use algorithm NONE")
    auth_size = struct.unpack_from(">Q", vbmeta, 12)[0]
    desc_at, desc_size = struct.unpack_from(">QQ", vbmeta, 96)
    desc = section(vbmeta, 256 + auth_size + desc_at, desc_size)
    require(struct.unpack_from(">Q", desc, 0)[0] == 2, "Missing AVB hash descriptor")
    size = struct.unpack_from(">Q", desc, 16)[0]
    require(size == image["footer"]["image_size"], "AVB image length differs from the footer")
    require(desc[24:56].rstrip(b"\0") == b"sha256", "Unexpected AVB hash algorithm")
    name_len, salt_len, hash_len = struct.unpack_from(">III", desc, 56)
    name = section(desc, 132, name_len)
    salt = section(desc, 132 + name_len, salt_len)
    digest = section(desc, 132 + name_len + salt_len, hash_len)
    require(name == b"vendor_boot" and hash_len == 32, "AVB descriptor names another partition")
    actual = hashlib.sha256(salt + image["data"][:size]).digest()
    require(digest == actual, "Packed image does not match its AVB SHA-256 descriptor")


def verify(args):
    root = Path(__file__).resolve().parent.parent
    cfg_bytes = args.config.read_bytes()
    cfg = tomllib.loads(cfg_bytes.decode("utf-8"))
    manifest = json.loads((root / "devices/zircon-stock.json").read_text())
    require(cfg["device"]["codename"] == "zircon", "Expected the zircon device configuration")
    require(cfg["stock"]["version"] == manifest["version"], "Configuration and stock manifest versions differ")
    stock = vendor_boot(args.stock)
    stock_sum = sha256(stock["data"])
    require(stock_sum == cfg["stock"]["recovery"] == manifest["vendor_boot"]["sha256"],
            "Stock vendor_boot SHA-256 differs from the pinned zircon input")
    require(len(stock["data"]) == manifest["vendor_boot"]["size"], "Stock partition size differs")
    entries = ramdisk_entries(stock["ramdisk"])
    props = properties(entries["prop.default"]["data"])
    require(props.get("ro.product.vendor.device") == "zircon", "Stock ramdisk is for another phone")
    require(props.get("ro.vendor.build.version.incremental") == manifest["version"], "Stock vendor version differs")
    loaded = entries["lib/modules/modules.load.recovery"]["data"].decode("utf-8").splitlines()
    for module in manifest["recovery_modules"]:
        require(module in loaded and f"lib/modules/{module}" in entries, f"Recovery module is missing: {module}")
    require(stock["dtb"][64:68] == bytes.fromhex("d00dfeed"), "Missing FDT inside the stock MTK DTB wrapper")
    report = {
        "device": "zircon",
        "stock_version": manifest["version"],
        "stock_vendor_boot_sha256": stock_sum,
        "stock_size": len(stock["data"]),
        "stock_ramdisk_entries": len(entries),
        "stock_dtb_sha256": sha256(stock["dtb"]),
        "config_sha256": sha256(cfg_bytes),
        "phone_tested": False,
    }
    if args.boot:
        boot = args.boot.read_bytes()
        require(sha256(boot) == manifest["boot"]["sha256"], "Stock boot SHA-256 differs from the supplied input")
        require(boot[:8] == b"ANDROID!" and u32(boot, 40) == 4, "Expected boot v4")
        require(u32(boot, 12) == 0, "The supplied boot should have no generic ramdisk")
        avb_footer(boot)
        report["stock_boot_sha256"] = sha256(boot)
    if args.image:
        require(args.binary and args.system_init, "Packed image checks need --binary and --system-init")
        built = vendor_boot(args.image)
        require(len(built["data"]) == len(stock["data"]), "Packed partition size changed")
        for name in ("header", "dtb", "table_identity", "bootconfig"):
            require(built[name] == stock[name], f"Packed {name} differs from stock")
        check_packed_avb(built)
        packed = ramdisk_entries(built["ramdisk"])
        changed = {"prop.default", "system/bin/recovery", "system/bin/7za", "system/bin/avbctl",
                   "system/bin/resetprop", "system/bin/unzip", "system/bin/zstd"}
        for name, entry in entries.items():
            if name not in changed:
                require(packed.get(name) == entry, f"Stock entry changed or missing: {name}")
        binaries = {"system/bin/recovery": args.binary, "skyward/system-init": args.system_init}
        binary_report = {}
        for name, path in binaries.items():
            content = path.read_bytes()
            require(packed[name]["data"] == content, f"Packed {name} differs from the build")
            binary_report[name] = elf_info(content)
            binary_report[name]["sha256"] = sha256(content)
        require(binary_report["system/bin/recovery"]["interpreter"] == "/system/bin/linker64",
                "Recovery does not use Android's linker64")
        static = binary_report["skyward/system-init"]
        require(static["interpreter"] is None and not static["needed"], "system-init is not standalone static")
        require(packed["skyward/device.toml"]["data"] == cfg_bytes, "Packed device configuration differs")
        for command in changed - {"prop.default", "system/bin/recovery"}:
            require(packed[command]["data"] == b"recovery" and packed[command]["metadata"][0] & 0o170000 == 0o120000,
                    f"Install command is not a link to recovery: {command}")
        new_props = properties(packed["prop.default"]["data"])
        for name, value in {"ro.secure": "0", "ro.adb.secure": "0", "ro.debuggable": "1"}.items():
            require(new_props.get(name) == value, f"Recovery property is missing: {name}={value}")
        for name in ("ro.build.version.release", "ro.build.version.security_patch", "ro.vendor.build.security_patch"):
            require(name not in new_props, f"Recovery still pins the installed system's {name}")
        module_count = sum(name.startswith("lib/modules/") and name.endswith(".ko") for name in entries)
        report.update({
            "image": args.image.name,
            "image_sha256": sha256(built["data"]),
            "image_size": len(built["data"]),
            "packed_ramdisk_entries": len(packed),
            "unchanged_kernel_modules": module_count,
            "preserved_stock_entries": len(set(entries) - changed),
            "avb_sha256_verified": True,
            "binaries": binary_report,
        })
    report["result"] = "passed"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", type=Path, required=True)
    parser.add_argument("--boot", type=Path)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent.parent / "devices/zircon.toml")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--system-init", type=Path)
    parser.add_argument("--report", type=Path)
    try:
        verify(parser.parse_args())
    except (ValueError, OSError, KeyError, struct.error, subprocess.CalledProcessError) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
