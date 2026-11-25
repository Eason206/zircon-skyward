# Skyward for zircon

[English](README.md) | **简体中文**

为 **Redmi Note 13 Pro+（`zircon`）** 适配的 Rust 恢复项目 Skyward 实验版，
已同步 [kirklin/skyward](https://github.com/kirklin/skyward) 的完整 **0.5.1** 源码。
镜像基于提供的 **OS3.0.305.0.WNOCNXM** 原厂 boot 与 vendor_boot，
保留原厂内核、设备树及恢复模式驱动。

**当前版本：`v0.5.1-alpha.2`。已完成编译和离线校验，尚未进行实机启动验证。**

[下载实验版](https://github.com/Eason206/zircon-skyward/releases/tag/v0.5.1-alpha.2)
· [编译与验证记录](docs/ZIRCON.zh-CN.md)
· [设备配置](devices/zircon.toml)
· [QEMU 可视预览与模拟 Wi-Fi](docs/QEMU.md)

## 上游完整功能

已合并上游 main 分支至 `43ec6da19402cf344b966bbb8c85c04fd2ffdcad`。
[UPSTREAM.toml](UPSTREAM.toml) 固定本次同步来源；[同步记录](docs/UPSTREAM.md) 列出功能与设备要求。

- 双系统、系统切换、A/B 槽位控制，以及刷入 ROM 后自动重新写入 Skyward。
- 锁屏密码 FBE 解密、元数据加密，以及未加密数据分区的直接访问。
- 从内置存储、USB 存储或 ADB 安装 ROM ZIP 和 OTA payload；刷写启动镜像、完整 super、逻辑分区、稀疏镜像及按分区命名的镜像。
- 系统与 Skyward 在线更新、WLAN 管理、MTP、root ADB 与 fastbootd。
- 系统、应用数据、内置存储和校准／身份分区备份，以及向新建的数据文件系统恢复备份。
- 文件管理器、文本编辑器、终端、分区挂载、文件系统修复、清除数据、日志和功能搜索。
- 电池与设备信息、浅色／深色主题、跟随安装系统的时区，以及 62 个时区的选择。
- 上游全部 15 种语言：简体中文、繁體中文、English、Türkçe、Русский、Українська、Español、Português (Brasil)、Bahasa Indonesia、Tiếng Việt、Deutsch、Français、Italiano、Polski、日本語。

以上为已同步的功能实现；zircon 的设备可用状态见下表。

## 设备与范围

| 项目 | 初版适配 |
| --- | --- |
| 设备 | Redmi Note 13 Pro+ / zircon / 原厂型号 23090RA98C |
| 平台 | MediaTek MT6886 / 天玑 7200-Ultra |
| 原厂 vendor 版本 | OS3.0.305.0.WNOCNXM |
| 目标分区 | vendor_boot，64 MiB，Android v4 启动头 |
| 显示 | 1220 × 2712，初始 UI 密度 480 DPI |
| 原厂恢复模式模块 | N16U 面板、mediatek-drm、goodix_core、xiaomi_touch |
| 源码许可 | GPL-3.0-or-later |

原厂指纹中的 `:13/` 描述 vendor/recovery 属性，不能据此确定完整安装系统的
Android 版本。输入镜像的标识与哈希记录在 [devices/zircon-stock.json](devices/zircon-stock.json)。

## 验证状态

| 项目 | 状态 |
| --- | --- |
| ARM64 recovery、静态 system-init、本机打包器 | 编译成功 |
| 镜像、压缩包与 AVB SHA-256 校验 | 离线通过 |
| 原厂 DTB、init、adbd、策略、库与 206 个内核模块 | 保留并校验一致 |
| 显示与触摸 | 原厂驱动已准备，实机表现待验证 |
| ADB 与 MTP | 已包含，实机表现待验证 |
| Wi-Fi 与震动控制配置 | 真机配置暂未启用；QEMU 支持明确标记的模拟 Wi-Fi |
| QEMU 可视预览 | 图片、扫描、密码连接及断开流程已验证，见 [说明](docs/QEMU.md) |
| FBE 解密、刷包、备份恢复、双系统 | 已包含完整上游实现，设备验证待完成 |

此 alpha 用于已解锁 Bootloader、固件匹配的设备进行适配测试。目标分区是
**vendor_boot**；该镜像不能作为内核 boot.img 直接传给 `fastboot boot`。
恢复模式下的 ADB 是无需手机端授权的 root shell。

## 下载与校验

从 [Releases](https://github.com/Eason206/zircon-skyward/releases) 下载 ZIP、
`SHA256SUMS`、`verification.json` 和 `BUILDINFO.json`。解压获得 64 MiB 的
`.img`，再核对 ZIP 与镜像哈希：

```sh
unzip skyward-v0.5.1-alpha.2-zircon-OS3.0.305.0.WNOCNXM-experimental.zip
shasum -a 256 -c SHA256SUMS
```

此版本标为 **Pre-release（预发布）**，GitHub 的稳定版 `releases/latest`
接口不会返回它。这个适配版的 Skyward 更新源已指向本仓库。

## 编译

需要 Rust **1.100.0**、`aarch64-linux-android` target、Android NDK
**r29 / 29.0.14206865**、cargo-ndk **4.1.2**、Python **3.11+**、LZ4 和 ripgrep。
初版在 macOS ARM64 上构建；CI 使用 NDK 支持的 Linux x86_64 构建主机。
先安装 [rustup](https://rustup.rs/) 与 [NDK r29](https://developer.android.com/ndk/downloads)。

```sh
git clone https://github.com/Eason206/zircon-skyward.git
cd zircon-skyward
export ANDROID_NDK_HOME="/path/to/android-ndk-r29"
./scripts/setup-env.sh
./scripts/build-zircon.sh \
  --stock /path/to/vendor_boot.img \
  --boot /path/to/boot.img
```

请提供设备清单对应的原厂输入，它们不存储在 Git 中。脚本会先检查 SHA-256，
保留原厂内核，编译程序、打包并验证 vendor_boot，在 `out/zircon/` 生成镜像、ZIP、
校验和及报告。也可将两份输入放入 `target/stock/zircon/` 后使用默认路径。

手动执行 Cargo 命令前，在仓库目录运行 `source scripts/env.sh`。
[编译说明](docs/ZIRCON.zh-CN.md) 提供本地原厂镜像接口、保留组件与待适配项目的详细记录。

## 测试与 CI

发布候选版通过 **941 项工作区测试**，包含 zircon 原厂加密条目的回归测试，
以及上游安装、备份和界面测试。完整测试与 Clippy 检查命令：

```sh
cargo test --locked --workspace
cargo clippy --locked --workspace --all-targets -- -D warnings
```

[GitHub Actions](.github/workflows/build.yml) 运行工作区检查并编译恢复工具。
完整 zircon 镜像需要本地原厂输入；Release 附件来自使用这些输入独立校验的构建。

## 上游与许可

当前同步至 [kirklin/skyward](https://github.com/kirklin/skyward)
的 `43ec6da19402cf344b966bbb8c85c04fd2ffdcad`（0.5.1）。
最初 zircon 适配参考 [mytiantian001/pearl-skyward](https://github.com/mytiantian001/pearl-skyward)
的 `d1d349481248e32a43bed7a1bfcd1124840beba8`。
上游源码历史与版权声明予以保留。zircon 适配由 [Eason206](https://github.com/Eason206) 维护。

Skyward 源码采用 **GPL-3.0-or-later**。完整条款见 [LICENSE](LICENSE)，
上游署名、字体及原厂组件的独立许可说明见 [NOTICE.md](NOTICE.md)。
