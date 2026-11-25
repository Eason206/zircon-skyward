#!/usr/bin/env python3
"""Prepare a pinned Debian ARM64 kernel and virtual GPU/input modules.

This kernel is only for the visible QEMU demo, never for the zircon image.
"""

import gzip
import hashlib
import json
import lzma
import subprocess
import tarfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".work/qemu-ui"
PACKAGE = "linux-image-6.12.117+deb13-arm64"
FILENAME = "pool/main/l/linux-signed-arm64/linux-image-6.12.117+deb13-arm64_6.12.117-1_arm64.deb"
SHA256 = "73805585385c78e048e63fdfba66da36bab724c2cdebd96a3055a8a4f1ae287a"
SIZE = 93443312


def download(package):
    # Keep the existing prefix and fetch the remaining ranges independently.
    prefix = package.stat().st_size if package.exists() else 0
    if prefix >= SIZE:
        package.unlink()
        prefix = 0
    parts = OUT / "download-parts"
    parts.mkdir(exist_ok=True)
    ranges = [(start, min(start + 8 * 1024 * 1024, SIZE) - 1)
              for start in range(prefix, SIZE, 8 * 1024 * 1024)]

    def fetch(bounds):
        start, end = bounds
        part = parts / f"{start}-{end}.part"
        have = part.stat().st_size if part.exists() else 0
        for attempt in range(4):
            if have == end - start + 1:
                return part
            request = urllib.request.Request("https://deb.debian.org/debian/" + FILENAME,
                                             headers={"Range": f"bytes={start + have}-{end}"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response, part.open("ab") as output:
                    if response.status != 206:
                        raise RuntimeError("The download server did not honor the requested range.")
                    while chunk := response.read(128 * 1024):
                        output.write(chunk)
                have = part.stat().st_size
            except (OSError, TimeoutError):
                have = part.stat().st_size if part.exists() else 0
                if attempt == 3:
                    raise
        raise RuntimeError(f"Incomplete kernel package range {start}-{end}")

    with ThreadPoolExecutor(max_workers=4) as pool:
        complete = list(pool.map(fetch, ranges))
    with package.open("ab") as output:
        for part in complete:
            with part.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
    assert package.stat().st_size == SIZE


def expand(content, name):
    if name.endswith(".xz"):
        return lzma.decompress(content)
    if name.endswith(".gz"):
        return gzip.decompress(content)
    if name.endswith(".zst"):
        return subprocess.check_output(["zstd", "-d", "-c"], input=content)
    return content


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    package = OUT / "linux-image.deb"
    if not package.exists() or hashlib.sha256(package.read_bytes()).hexdigest() != SHA256:
        download(package)
    blob = package.read_bytes()
    assert hashlib.sha256(blob).hexdigest() == SHA256
    assert blob.startswith(b"!<arch>\n")
    offset, archive = 8, None
    while offset + 60 <= len(blob):
        header = blob[offset:offset + 60]
        size = int(header[48:58])
        name = header[:16].decode().strip().rstrip("/")
        content = blob[offset + 60:offset + 60 + size]
        offset += 60 + size + size % 2
        if name.startswith("data.tar"):
            archive = expand(content, name)
            break
    assert archive is not None
    with tarfile.open(fileobj=BytesIO(archive), mode="r:") as tar:
        files = {member.name.removeprefix("./"): member for member in tar.getmembers() if member.isfile()}
        kernel_name = next(name for name in files if name.startswith("boot/vmlinuz-"))
        kernel = tar.extractfile(files[kernel_name]).read()
        (OUT / "Image").write_bytes(kernel)
        module_files = [name for name in files if "/lib/modules/" in "/" + name and ".ko" in Path(name).name]
        by_name = {Path(name).name.split(".ko")[0].replace("-", "_"): name for name in module_files}
        builtin_file = next(name for name in files if name.endswith("/modules.builtin"))
        builtin = {Path(name).name.split(".ko")[0].replace("-", "_")
                   for name in tar.extractfile(files[builtin_file]).read().decode().splitlines()}
        expanded = {}
        wanted = ["virtio_gpu", "virtio_input", "virtio_pci", "virtio_mmio", "evdev", "uinput", "loop",
                  "crc32_generic", "crc32_arm64", "crc32c_generic", "crc32c_arm64", "quota_v2", "f2fs", "ext4"]
        order, seen = [], set()

        def take(name):
            if name in seen:
                return
            seen.add(name)
            if name in builtin and name not in by_name:
                return
            path = by_name[name]
            content = expand(tar.extractfile(files[path]).read(), path)
            expanded[name] = content
            dependencies = next((field[8:].decode().split(",") for field in content.split(b"\0") if field.startswith(b"depends=")), [])
            for dependency in filter(None, dependencies):
                take(dependency)
            order.append(name)

        for name in wanted:
            if name in by_name:
                take(name)
        assert "virtio_gpu" in by_name and "uinput" in by_name
        modules = OUT / "modules"
        modules.mkdir(exist_ok=True)
        names = []
        for name in order:
            content = expanded[name]
            target = Path(by_name[name]).name.split(".ko")[0] + ".ko"
            (modules / target).write_bytes(content)
            names.append(target)
        (OUT / "module-order.txt").write_text("".join(name + "\n" for name in names))
        metadata = {"package": PACKAGE, "url": "https://deb.debian.org/debian/" + FILENAME,
                    "package_sha256": SHA256, "kernel_member": kernel_name,
                    "kernel_sha256": hashlib.sha256(kernel).hexdigest(), "modules": names}
        (OUT / "prepared.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(json.dumps({"kernel": kernel_name, "modules": len(names)}, indent=2))


if __name__ == "__main__":
    main()
