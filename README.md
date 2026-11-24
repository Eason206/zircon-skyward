# Skyward for zircon

**English** | [简体中文](README.zh-CN.md)

An experimental port of the Rust-based Skyward recovery for **Redmi Note 13
Pro+ (`zircon`)**. The initial release is built from the supplied
**OS3.0.305.0.WNOCNXM** stock boot and vendor_boot images and preserves their
kernel, device tree and recovery drivers.

**Current release: `v0.3.3-alpha.1`. Built and verified offline; not boot-tested
on a phone.**

[Download the alpha](https://github.com/Eason206/zircon-skyward/releases/tag/v0.3.3-alpha.1)
· [Build and validation notes](docs/ZIRCON.md)
· [Device configuration](devices/zircon.toml)

## Device and scope

| Item | Initial port |
| --- | --- |
| Device | Redmi Note 13 Pro+ / zircon / stock model 23090RA98C |
| Platform | MediaTek MT6886 / Dimensity 7200-Ultra |
| Stock vendor build | OS3.0.305.0.WNOCNXM |
| Target partition | vendor_boot, 64 MiB, Android header v4 |
| Display | 1220 × 2712; initial UI density 480 DPI |
| Stock recovery modules | N16U panel, mediatek-drm, goodix_core, xiaomi_touch |
| Source license | GPL-3.0-or-later |

The `:13/` stock fingerprints describe vendor/recovery properties, not the
Android version of the complete installed system. Input identities and hashes
are recorded in [devices/zircon-stock.json](devices/zircon-stock.json).

## Validation status

| Area | Status |
| --- | --- |
| ARM64 recovery, static system-init and native packer | Built successfully |
| Image, archive and AVB SHA-256 verification | Passed offline |
| Original DTB, init, adbd, policy, libraries and 206 kernel modules | Preserved and checked |
| Display and touch | Stock drivers prepared; phone behavior untested |
| ADB and MTP | Included; phone behavior untested |
| Wi-Fi and haptic configuration | Not enabled in this alpha |
| FBE decryption, flashing, backup/restore and dual boot | Core code retained; device validation pending |

This alpha is for port testing on a device with an unlocked bootloader and
matching stock firmware. The image targets **vendor_boot**; it cannot be passed
directly to `fastboot boot` as a kernel boot image. Recovery ADB runs as root
without phone-side authorization.

## Download and verify

Download the ZIP, `SHA256SUMS`, `verification.json` and `BUILDINFO.json` from
[Releases](https://github.com/Eason206/zircon-skyward/releases). Extract the ZIP to
obtain the 64 MiB `.img` and check both the ZIP and image against SHA256SUMS:

```sh
unzip skyward-v0.3.3-alpha.1-zircon-OS3.0.305.0.WNOCNXM-experimental.zip
shasum -a 256 -c SHA256SUMS
```

The release is marked as a **pre-release**. GitHub's stable `releases/latest`
endpoint excludes it. Skyward's update source for this port is this repository.

## Build

Requirements: Rust **1.100.0**, the `aarch64-linux-android` target, Android NDK
**r29 / 29.0.14206865**, cargo-ndk **4.1.2**, Python **3.11+**, LZ4 and ripgrep.
The initial build host is macOS ARM64; Linux x86_64 is supported by the NDK host
toolchain and used by CI. Install [rustup](https://rustup.rs/) and
[NDK r29](https://developer.android.com/ndk/downloads) first.

```sh
git clone https://github.com/Eason206/zircon-skyward.git
cd zircon-skyward
export ANDROID_NDK_HOME="/path/to/android-ndk-r29"
./scripts/setup-env.sh
./scripts/build-zircon.sh \
  --stock /path/to/vendor_boot.img \
  --boot /path/to/boot.img
```

Supply the exact stock inputs listed in the device manifest. They are not
stored in Git. The build checks their SHA-256 values, retains the existing
kernel, builds the binaries, packs and verifies vendor_boot, then produces the
image, ZIP, checksums and reports under `out/zircon/`. Alternatively, place the
two inputs in `target/stock/zircon/` and use the script's default paths.

For manual Cargo commands, run `source scripts/env.sh` from the checkout.
See [the build notes](docs/ZIRCON.md) for the local-image packer interface,
preserved components and remaining device work.

## Tests and CI

The release candidate passed **878 workspace tests**, including **56 related
port tests**. The focused test and lint commands are:

```sh
cargo test --locked -p skyward-config -p skyward-pack -p skyward-bootimg -p skyward-modules
cargo clippy --locked -p skyward-config -p skyward-pack --all-targets -- -D warnings
```

[GitHub Actions](.github/workflows/build.yml) runs workspace checks and builds
the recovery tools. Packing a zircon recovery image requires the local stock
inputs. Releases attach separately verified builds from those inputs.

## Credits and license

Derived from [mytiantian001/pearl-skyward](https://github.com/mytiantian001/pearl-skyward)
at `d1d349481248e32a43bed7a1bfcd1124840beba8`; original Skyward is maintained at
[kirklin/skyward](https://github.com/kirklin/skyward). Upstream source history and
copyright notices are retained. The zircon port is maintained by
[Eason206](https://github.com/Eason206).

Skyward source is licensed under **GPL-3.0-or-later**. See [LICENSE](LICENSE) and
[NOTICE.md](NOTICE.md) for source attribution and separately licensed fonts and
stock vendor components.
