# zircon build, upstream sync and validation

[English](ZIRCON.md) | [简体中文](ZIRCON.zh-CN.md)

This experimental Redmi Note 13 Pro+ (`zircon`) port includes the complete
Skyward 0.5.1 source from `kirklin/skyward` at
`43ec6da19402cf344b966bbb8c85c04fd2ffdcad`. [UPSTREAM.toml](../UPSTREAM.toml)
pins the baseline, and [the sync notes](UPSTREAM.md) list the functionality.
The initial port used `mytiantian001/pearl-skyward` at
`d1d349481248e32a43bed7a1bfcd1124840beba8`. Builds continue to use the two supplied
stock images for **OS3.0.305.0.WNOCNXM**. The original kernel stays in boot; Skyward
replaces the recovery service inside vendor_boot.

## Build environment

| Tool | Required version |
| --- | --- |
| Rust | 1.100.0, pinned by rust-toolchain.toml |
| Rust target | aarch64-linux-android |
| Android NDK | r29 / 29.0.14206865 |
| cargo-ndk | 4.1.2 |
| Minimum Android API | 30 |
| Image verification | Python 3.11+ and LZ4 |
| Environment helper | ripgrep (`rg`), bash |

The initial build was produced on macOS ARM64. The packer runs on the host and
NDK clang builds the Android binaries. The existing kernel is retained; building
an Android system or a new kernel is unnecessary for this port. Linux x86_64 can
use NDK's corresponding Linux host toolchain.

Install [rustup](https://rustup.rs/) and [Android NDK r29](https://developer.android.com/ndk/downloads).
Set `ANDROID_NDK_HOME` when the NDK is outside the paths recognized by
`scripts/env.sh`. Install Python 3.11+, LZ4 and ripgrep as well.

## Rebuild

From the repository root:

```sh
export ANDROID_NDK_HOME="/path/to/android-ndk-r29"
./scripts/setup-env.sh
./scripts/build-zircon.sh \
  --stock /path/to/vendor_boot.img \
  --boot /path/to/boot.img
```

Alternatively, place both stock inputs under `target/stock/zircon/` and run
`./scripts/build-zircon.sh` with its defaults. Those inputs are not part of this
Git repository. The script checks their pinned SHA-256 values, builds the native
packer, Android ARM64 recovery and static system-init, packs vendor_boot and
verifies the image and ZIP. Outputs go to `out/zircon/`.

For manual Cargo commands, run `source scripts/env.sh` from the checkout. The
helper supports bash and zsh. `--skip-build` reuses existing binaries and should
only be used after building the current source.

## Device evidence

| Item | Stock input evidence |
| --- | --- |
| Device | zircon / 23090RA98C / MT6886 |
| Vendor build | OS3.0.305.0.WNOCNXM; patch 2026-08-01 |
| boot | v4, 64 MiB, kernel present, generic ramdisk empty |
| vendor_boot | v4, 64 MiB, 4096-byte pages, one type 1 ramdisk fragment |
| DTB | 275488 bytes, including a 64-byte MTK wrapper |
| Panel | N16U, 1220 × 2712 |
| Touch | goodix_core and xiaomi_touch in modules.load.recovery |
| USB controller | 11201000.usb0 |
| Storage | A/B, dynamic partitions, F2FS userdata and metadata |
| Service directory | Stock recovery carries and starts servicemanager |

The panel dimensions also agree with the same author's
[zircon TWRP BoardConfig](https://github.com/mytiantian001/android_device_xiaomi_zircon_twrp/blob/a15/BoardConfig.mk).
That older TWRP DTB and its boot parameters were not used for this build. The
`:13/` fingerprints belong to vendor/recovery properties; they do not identify
the Android version of the complete installed system.

The port uses zircon's identity, resolution and calibration partition list.
Its service directory is allowed to reread the descriptions Skyward publishes.
The stock recovery already loads the panel and touch modules, so no
pearl-specific WLAN or haptic module is requested.

480 DPI is an initial UI value from the recovery's generic HAL property block.
The installed system's overlays were not supplied. Rounded-corner, status-bar,
WLAN, haptic-control and TEE-helper parameters still need device-specific work.

## Offline verification

`scripts/verify-zircon.py` checks stock versions and hashes, then verifies that:

- Partition size, boot header and parameters, complete DTB, fragment identity and bootconfig are preserved.
- Original init, adbd, policy, libraries, fstab and all kernel modules retain their data and archive metadata.
- Packed recovery, static system-init and device configuration match the build inputs.
- Recovery is an Android AArch64 ELF using linker64, and system-init has no interpreter or shared-library dependency.
- Install command symlinks, recovery properties and the vendor_boot AVB SHA-256 descriptor are correct.
- ZIP contents are readable and the enclosed image matches the standalone image.

The offline check covers **206 kernel modules** and **1117 stock
archive entries**. Full workspace tests and lints can be run with:

```sh
cargo test --locked --workspace
cargo clippy --locked --workspace --all-targets -- -D warnings
```

All **946 host workspace tests** passed for this release candidate, including
the stock zircon fstab regression and upstream functionality tests. Release assets contain
`verification.json`, `BUILDINFO.json` and `SHA256SUMS` for the published build.

## Phone validation

Offline verification establishes that the image was built and packed correctly.
It does not establish phone compatibility. Boot, display/touch, ADB/MTP, Wi-Fi,
haptics, FBE decryption, flashing, backup/restore and dual boot have not been
tested on a phone. WLAN and haptic configuration are not enabled in this alpha;
decryption code remains present, with this build's vendor/odm services still to
be mapped and checked.

The target partition is **vendor_boot**. This is not a kernel boot image that can
be passed directly to `fastboot boot`. ADB in recovery is a root shell without
phone authorization, as the upstream recovery design specifies.

## Local stock image support and CI

`[stock] package` may be omitted for local-image ports; stock version and recovery
SHA-256 remain mandatory. Check or copy a local vendor_boot with:

```sh
target/release/skyward-pack stock \
  --config devices/zircon.toml \
  --image /path/to/vendor_boot.img \
  --out target/stock/zircon/vendor_boot.img
```

`recovery --stock` also verifies the configured hash before packing. The pearl
reference configuration retains its original OTA URL.

GitHub Actions builds the source/tools and runs tests and lints. Packing this
zircon image requires the exact local stock inputs, which are deliberately kept
outside Git. Releases publish independently verified local builds. Skyward's
update source is this repository; GitHub's `releases/latest` excludes alpha
pre-releases until a stable release is published.


See [the QEMU notes](QEMU.md) for the visible ARM64 preview, simulated Wi-Fi and validation limits.
