#!/usr/bin/env python3
"""Run zircon ARM64 component tests with its stock kernel in QEMU virt.

This is not an MT6886 board emulator. The component init skips Android init
and all vendor driver startup. Disks are new loop files inside guest RAM.
"""

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import platform
import plistlib
import re
import shutil
import socket
import stat
import struct
import subprocess
import sys
import time
import tomllib
import zipfile
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def newc(entries):
    archive = bytearray()
    for inode, (name, content, mode, major, minor) in enumerate(entries, 1_000_000):
        encoded = name.encode() + b"\0"
        fields = (inode, mode, 0, 0, 1, 0, len(content), 0, 0, major, minor, len(encoded), 0)
        archive.extend(b"070701" + b"".join(f"{field:08x}".encode() for field in fields))
        archive.extend(encoded)
        archive.extend(b"\0" * (-len(archive) % 4))
        archive.extend(content)
        archive.extend(b"\0" * (-len(archive) % 4))
    return bytes(archive)


def boot(qemu, kernel, initrd, output, rdinit, timeout):
    accelerator = "hvf" if platform.system() == "Darwin" and platform.machine() == "arm64" else "tcg"
    cpu = "host" if accelerator == "hvf" else "cortex-a76"
    command = [qemu, "-machine", "virt,gic-version=3", "-accel", accelerator, "-cpu", cpu,
               "-smp", "2", "-m", "2048", "-kernel", str(kernel), "-initrd", str(initrd),
               "-append", f"console=ttyAMA0 earlycon=pl011,0x09000000 loglevel=3 rdinit={rdinit} "
               "androidboot.hardware=zircon androidboot.force_normal_boot=0 androidboot.slot_suffix=_a panic=-1",
               "-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot"]
    timed_out = False
    with output.open("wb") as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    return {"command": command, "exit_code": process.returncode, "timed_out": timed_out,
            "accelerator": accelerator, "log": output.name}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-boot", type=Path, default=ROOT / "target/stock/zircon/boot.img")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "out/qemu-zircon")
    parser.add_argument("--interactive", action="store_true", help="Open a visible Skyward UI on QEMU virt with a generic display kernel.")
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "Cargo.toml").read_text())["workspace"]["package"]["version"]
    device = tomllib.loads((ROOT / "devices/zircon.toml").read_text())
    stock = json.loads((ROOT / "devices/zircon-stock.json").read_text())
    image = args.image or ROOT / "out/zircon" / f"skyward-v{version}-zircon-{stock['version']}-experimental.img"
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    qemu = shutil.which("qemu-system-aarch64")
    if not qemu:
        raise SystemExit("Install qemu-system-aarch64 first.")
    ndk = Path(os.environ.get("ANDROID_NDK_HOME", Path.home() / "android-ndk/android-ndk-r29"))
    host = "darwin-x86_64" if platform.system() == "Darwin" else "linux-x86_64"
    clang = ndk / f"toolchains/llvm/prebuilt/{host}/bin/aarch64-linux-android30-clang"
    if not clang.is_file():
        raise SystemExit("Set ANDROID_NDK_HOME to Android NDK r29.")
    spec = importlib.util.spec_from_file_location("zircon_verify", ROOT / "scripts/verify-zircon.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    boot_bytes = args.stock_boot.read_bytes()
    if digest(boot_bytes) != stock["boot"]["sha256"]:
        raise SystemExit("The stock boot image does not match zircon-stock.json.")
    packed = verifier.vendor_boot(image)
    entries = verifier.ramdisk_entries(packed["ramdisk"])
    if entries["skyward/device.toml"]["data"] != (ROOT / "devices/zircon.toml").read_bytes():
        raise SystemExit("Build the current zircon image before running these tests.")
    kernel_blob = boot_bytes[4096:4096 + struct.unpack_from("<I", boot_bytes, 8)[0]]
    kernel = output / "stock-Image"
    kernel.write_bytes(subprocess.check_output(["lz4", "-d", "-c"], input=kernel_blob))
    ramdisk = subprocess.check_output(["lz4", "-d", "-c"], input=packed["ramdisk"])
    raw_initrd = output / "packed-ramdisk.cpio"
    raw_initrd.write_bytes(ramdisk)
    init = output / "qemu-guest-init"
    subprocess.run([str(clang), "-static", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(ROOT / "scripts/qemu/guest-init.c"), str(ROOT / "scripts/qemu/interactive-init.c"), "-o", str(init)], check=True)
    content = "Skyward zircon QEMU ARM64 — 离线测试\n".encode()
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("hello.txt", content)
    compressed = subprocess.check_output(["zstd", "-q", "-c"], input=content)
    extra = [("qemu", b"", stat.S_IFDIR | 0o755, 0, 0),
             ("qemu-guest-init", init.read_bytes(), stat.S_IFREG | 0o755, 0, 0),
             ("qemu/skyward.img", packed["data"], stat.S_IFREG | 0o644, 0, 0),
             ("qemu/super-metadata.bin", (ROOT / "crates/skyward-lp/tests/ishtar-super-metadata.bin").read_bytes(), stat.S_IFREG | 0o644, 0, 0),
             ("qemu/sample.zip", archive.getvalue(), stat.S_IFREG | 0o644, 0, 0),
             ("qemu/sample.zst", compressed, stat.S_IFREG | 0o644, 0, 0)]
    for name, major, minor in [("console", 5, 1), ("null", 1, 3), ("zero", 1, 5), ("random", 1, 8), ("urandom", 1, 9)]:
        extra.append((f"dev/{name}", b"", stat.S_IFCHR | 0o600, major, minor))
    for number in range(4):
        extra.append((f"dev/loop{number}", b"", stat.S_IFBLK | 0o600, 7, number))
    extra.append(("TRAILER!!!", b"", 0, 0, 0))
    if args.interactive:
        subprocess.run([sys.executable, str(ROOT / "scripts/qemu/prepare-ui-kernel.py")], check=True)
        generic = ROOT / ".work/qemu-ui"
        adapter = output / "virtual-panel.so"
        subprocess.run([str(clang), "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(ROOT / "scripts/qemu/virtual-panel.c"), "-ldl", "-o", str(adapter)], check=True)
        extra.pop()
        extra.extend([("qemu/interactive", b"", stat.S_IFREG | 0o644, 0, 0),
                      ("qemu/virtual-panel.so", adapter.read_bytes(), stat.S_IFREG | 0o644, 0, 0),
                      ("qemu/epoch", str(int(time.time())).encode(), stat.S_IFREG | 0o644, 0, 0),
                      ("qemu/modules", b"", stat.S_IFDIR | 0o755, 0, 0),
                      ("qemu/module-order.txt", (generic / "module-order.txt").read_bytes(), stat.S_IFREG | 0o644, 0, 0)])
        for name in (generic / "module-order.txt").read_text().splitlines():
            extra.append((f"qemu/modules/{name}", (generic / "modules" / name).read_bytes(), stat.S_IFREG | 0o644, 0, 0))
        extra.append(("TRAILER!!!", b"", 0, 0, 0))
    test_initrd = output / "component-initrd.cpio.gz"
    test_initrd.write_bytes(gzip.compress(ramdisk + newc(extra), compresslevel=1, mtime=0))
    if args.interactive:
        qmp = output / "qmp.sock"
        if qmp.exists():
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                try:
                    connection.connect(str(qmp))
                except ConnectionRefusedError:
                    qmp.unlink()
                else:
                    raise SystemExit(f"An existing QEMU QMP socket is present: {qmp}")
        accelerator = "hvf" if platform.system() == "Darwin" and platform.machine() == "arm64" else "tcg"
        display = "cocoa" if platform.system() == "Darwin" else "gtk"
        qemu_data = Path(qemu).resolve().parent.parent / "share/qemu"
        if platform.system() == "Darwin":
            # Give the Cocoa window an application identity for normal
            # desktop activation and accessibility, using the installed QEMU.
            bundle = ROOT / ".work/qemu-ui/QEMU Zircon.app"
            executable = bundle / "Contents/MacOS/qemu-system-aarch64"
            executable.parent.mkdir(parents=True, exist_ok=True)
            temporary = executable.with_name(executable.name + ".new")
            shutil.copy2(qemu, temporary)
            temporary.replace(executable)
            info = {"CFBundleIdentifier": "org.qemu.zircon-skyward-preview",
                    "CFBundleName": "QEMU Zircon", "CFBundleDisplayName": "QEMU Zircon",
                    "CFBundleExecutable": "qemu-system-aarch64", "CFBundlePackageType": "APPL",
                    "CFBundleVersion": "1", "CFBundleInfoDictionaryVersion": "6.0",
                    "NSHighResolutionCapable": True}
            with (bundle / "Contents/Info.plist").open("wb") as plist:
                plistlib.dump(info, plist)
            registry = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
            subprocess.run([registry, "-f", str(bundle)], check=True)
            qemu = str(executable)
        command = [qemu, "-L", str(qemu_data), "-name", f"zircon - Skyward {version} - QEMU ARM64 virt", "-machine", "virt,gic-version=3",
                   "-accel", accelerator, "-cpu", "host" if accelerator == "hvf" else "cortex-a76",
                   "-smp", "2", "-m", "2048", "-kernel", str(ROOT / ".work/qemu-ui/Image"),
                   "-initrd", str(test_initrd), "-append", "console=ttyAMA0 loglevel=4 rdinit=/qemu-guest-init androidboot.slot_suffix=_a androidboot.hardware=zircon",
                   "-device", "virtio-gpu-pci,xres=1220,yres=2712", "-device", "virtio-tablet-pci",
                   "-device", "virtio-keyboard-pci", "-display", display, "-serial", "stdio", "-monitor", "none",
                   "-qmp", f"unix:{qmp},server=on,wait=off"]
        log_path = output / "interactive.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            startup = log_path.read_text(errors="replace")
            if process.poll() is not None or "QEMU_SKYWARD_UI_EXITED" in startup:
                raise SystemExit(f"QEMU UI startup failed. See {log_path}\n{startup[-3000:]}")
            if "frame Home" in startup:
                break
            time.sleep(0.1)
        else:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise SystemExit(f"QEMU did not draw the home screen within 20 seconds. See {log_path}")
        state = {"pid": process.pid, "command": command, "qmp_socket": str(qmp), "log": str(log_path),
                 "generic_kernel": json.loads((ROOT / ".work/qemu-ui/prepared.json").read_text()),
                 "tested_recovery_sha256": digest(entries["system/bin/recovery"]["data"]),
                 "display_adapter": "QEMU-only ioctl shim: virtual connector exposed as embedded DisplayPort",
                 "ui_ready": True, "wlan_simulated": True,
                 "full_device_emulated": False, "data_partition": "new unencrypted guest-RAM loop file"}
        (output / "interactive.json").write_text(json.dumps(state, indent=2) + "\n")
        print(json.dumps({"pid": process.pid, "qmp": str(qmp), "log": str(log_path)}, indent=2))
        return 0
    stock_run = boot(qemu, kernel, raw_initrd, output / "stock-boot.log", "/init", 25)
    component_run = boot(qemu, kernel, test_initrd, output / "components.log", "/qemu-guest-init", 150)
    log = (output / "components.log").read_text(errors="replace").replace("\r", "")
    tests = []
    expected = {"cli_help": "Skyward", "cli_version": version, "zircon_config": "zircon",
                "vendor_boot_identify": "vendor", "logical_partition_metadata": "system",
                "unzip_stream": content.decode().strip(), "zstd_stream": content.decode().strip(),
                "ext4_format": None, "ext4_roundtrip": "persisted bytes matched", "ext4_fsck": None,
                "f2fs_format": None, "f2fs_roundtrip": "persisted bytes matched", "f2fs_fsck": None}
    for name, wanted in expected.items():
        match = re.search(rf"QEMU_TEST_BEGIN {name}\n(.*?)\nQEMU_TEST_END {name} (-?\d+)\n", log, re.S)
        code = int(match.group(2)) if match else None
        text = match.group(1).strip() if match else "Test did not run."
        passed = code == 0 and (wanted is None or wanted.lower() in text.lower())
        tests.append({"name": name, "result": "passed" if passed else "failed", "exit_code": code, "output": text[:6000]})
    stock_log = (output / "stock-boot.log").read_text(errors="replace")
    report = {"device_config": device["device"]["codename"], "board_model": "QEMU virt; not MT6886",
              "qemu": subprocess.check_output([qemu, "--version"], text=True).splitlines()[0],
              "stock_boot_sha256": digest(boot_bytes), "stock_kernel_sha256": digest(kernel.read_bytes()),
              "tested_image_sha256": digest(packed["data"]),
              "tested_recovery_sha256": digest(entries["system/bin/recovery"]["data"]),
              "source_commit": json.loads((image.parent / "BUILDINFO.json").read_text())["source_commit"],
              "phone_tested": False, "full_device_emulated": False,
              "stock_boot": {**stock_run, "kernel_panic": "Kernel panic" in stock_log,
                             "mediatek_watchdog_smc_failure": "kwdt_thread" in stock_log and "__arm_smccc_smc" in stock_log},
              "components": component_run, "suite_completed": "QEMU_COMPONENT_SUITE_COMPLETE" in log,
              "tests": tests, "passed": sum(test["result"] == "passed" for test in tests),
              "failed": sum(test["result"] == "failed" for test in tests),
              "limitations": ["No MT6886 board or secure firmware emulation.",
                              "No zircon display, touchscreen, WLAN, haptics or hardware-backed FBE validation.",
                              "Component init bypasses Android init and vendor driver startup.",
                              "All formatted disks are new guest-RAM loop files."]}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "failed": report["failed"],
                      "suite_completed": report["suite_completed"], "report": str(output / "report.json")}, indent=2))
    for test in tests:
        print(test["result"], test["name"], test["exit_code"])
        if test["result"] != "passed": print(test["output"][-1200:])
    return 0 if report["failed"] == 0 and report["suite_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
