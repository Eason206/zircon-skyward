# zircon 初版适配与编译

[English](ZIRCON.md) | [简体中文](ZIRCON.zh-CN.md)

本项目基于 [mytiantian001/pearl-skyward](https://github.com/mytiantian001/pearl-skyward) 的 `d1d349481248e32a43bed7a1bfcd1124840beba8`，增加 Redmi Note 13 Pro+（zircon）的实验适配。初版使用提供的 OS3.0.305.0.WNOCNXM `boot.img` 和 `vendor_boot.img`。

设备配置在 [devices/zircon.toml](../devices/zircon.toml)，输入镜像的版本、哈希和头部参数在 [devices/zircon-stock.json](../devices/zircon-stock.json)。构建保留原厂内核，通过替换 vendor_boot 中的 recovery 程序运行 Skyward。

## 本机环境

已使用以下工具进行实际构建：

| 工具 | 版本／位置 |
| --- | --- |
| 构建主机 | macOS ARM64 |
| Rust | 1.100.0，按 rust-toolchain.toml 固定 |
| Android target | aarch64-linux-android |
| Android NDK | r29 / 29.0.14206865，位置由 ANDROID_NDK_HOME 指定 |
| cargo-ndk | 4.1.2 |
| 最低 Android API | 30 |
| 镜像验证 | Python 3.11、LZ4 |
| 环境辅助 | ripgrep（rg）、bash |

NDK 自带的 clang 用于 Android 交叉编译；打包器由本机 Rust 编译。现阶段不需要编译 Android 系统或内核，也不需要 Linux 虚拟机。

## 重建

在此仓库根目录执行：

```sh
./scripts/setup-env.sh
./scripts/build-zircon.sh
```

默认读取 `target/stock/zircon/` 中的两份原厂输入；它们不上传 Git。独立克隆仓库时请自行提供清单对应的输入，或明确指定路径：

```sh
./scripts/build-zircon.sh \
  --stock /path/to/vendor_boot.img \
  --boot /path/to/boot.img
```

构建脚本会先核对两份输入的 SHA-256，再编译 `skyward-pack`、ARM64 `skyward` 和静态 `system-init`，然后打包、验证并生成 ZIP。产物在 `out/zircon/`，名称含 `zircon`、原厂版本和 `experimental`，同时输出 `SHA256SUMS`、`verification.json`、`BUILDINFO.json` 与 `SOURCE.txt`。构建读取指定输入，不修改原文件。

手动运行 Cargo 前，在仓库目录执行 `source scripts/env.sh`。环境脚本支持当前的 zsh，也可由构建脚本在 bash 中加载。其他机器可将 NDK 放在常见 SDK 目录，或设置 `ANDROID_NDK_HOME`。

只有已完成当前源码构建后才使用 `--skip-build`；它会复用已有二进制。

## 适配依据

| 项目 | 从输入中确认的内容 |
| --- | --- |
| 设备 | zircon，型号 23090RA98C，MT6886 |
| vendor 版本 | OS3.0.305.0.WNOCNXM，补丁日期 2026-08-01 |
| boot | v4，64 MiB，内核存在、通用 ramdisk 为空 |
| vendor_boot | v4，64 MiB，4096 字节页，单个 type 1 ramdisk |
| DTB | 275488 字节，含 64 字节 MTK 包装；整体保留 |
| 屏幕 | N16U 面板驱动，1220 × 2712 |
| 触摸 | goodix_core 与 xiaomi_touch，已列入 modules.load.recovery |
| USB | 原厂 recovery 使用 11201000.usb0 |
| 分区与文件系统 | A/B、动态分区，userdata 与 metadata 为 F2FS |
| 服务目录 | recovery 携带 servicemanager，并在 init 阶段启动 |

屏幕分辨率还与同一作者的 [zircon TWRP BoardConfig](https://github.com/mytiantian001/android_device_xiaomi_zircon_twrp/blob/a15/BoardConfig.mk) 一致；旧 TWRP 的 DTB 和启动参数没有用于本次打包。输入镜像中的 `:13/` 指 vendor/recovery 的属性，不能据此确定完整已安装系统的 Android 版本。

与 pearl 配置相比，这里使用 zircon 的机型、分辨率和分区备份列表，并允许 servicemanager 重新读取发布的服务描述。原厂恢复模式已经加载屏幕、触摸等驱动，初版无需额外加载 pearl 的 haptic 或 WLAN 模块。

480 DPI 是恢复镜像通用 HAL 属性块提供的初始 UI 值，尚未核对安装系统的设备 overlay。圆角、状态栏、Wi-Fi、震动控制与 TEE 辅助服务参数没有从 pearl 复制过来。

## 离线验证与实机边界

`scripts/verify-zircon.py` 会检查两份输入的版本和哈希，并检查生成镜像：

- vendor_boot 分区大小、启动头、启动参数、完整 DTB、ramdisk 类型和 bootconfig 保持正确。
- 原厂 init、adbd、SELinux 策略、库、fstab 和全部内核模块的内容与归属信息保留。
- 镜像内的 Skyward、system-init 和设备配置与本次构建一致；恢复程序是 Android ARM64 ELF，system-init 无解释器和共享库依赖。
- 安装命令链接到 recovery，恢复模式属性已设置，AVB footer 与 vendor_boot 的 SHA-256 描述符一致。
- ZIP 可完整解压，其中的镜像哈希与裸镜像一致。

初版镜像的离线验证确认 64 MiB 分区打包通过，206 个内核模块及 1117 个保留的原厂条目校验一致。发布候选版通过 878 项主机工作区测试，其中包含以下 56 项适配相关测试：

```sh
cargo test --locked -p skyward-config -p skyward-pack -p skyward-bootimg -p skyward-modules
cargo clippy --locked -p skyward-config -p skyward-pack --all-targets -- -D warnings
```

镜像的实际哈希见 `out/zircon/SHA256SUMS`，结构与二进制检查结果见 `out/zircon/verification.json`，源码提交和工具链见 `out/zircon/BUILDINFO.json`。发布附件同时提供这些报告。

这些检查证明构建与打包通过，不代替实机启动。初版尚未验证显示／触摸实际表现、ADB／MTP、Wi-Fi、震动、FBE 解密、刷包、备份恢复和双系统。Wi-Fi 和震动配置暂未启用；解密代码保留，但所需的 vendor/odm 服务还未针对这个版本核对。目标是 `vendor_boot` 分区，该镜像不能作为普通内核 boot.img 直接用于 `fastboot boot`。

## 本地原厂镜像支持

`[stock] package` 现在可省略；版本与 recovery SHA-256 仍必填。可单独验证或保存原厂 vendor_boot：

```sh
target/release/skyward-pack stock \
  --config devices/zircon.toml \
  --image /path/to/vendor_boot.img \
  --out target/stock/zircon/vendor_boot.img
```

`recovery --stock` 也会检查设备配置固定的哈希，拒绝其他版本或机型的输入。pearl 的完整 OTA 下载方式仍可使用。

GitHub Actions 检查工作区源码并编译恢复工具。完整 zircon 镜像使用本地、哈希固定的原厂输入独立打包与校验后发布。Skyward 更新源指向本仓库；GitHub 的 `releases/latest` 排除实验预发布版本，待稳定版发布后才会提供稳定更新。
