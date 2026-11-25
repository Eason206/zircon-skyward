# QEMU preview / QEMU 预览

## 简体中文

`v0.5.1-alpha.2` 修正了 Redmi Note 13 Pro+ 的手机图片，加入可见的 ARM64
QEMU 预览和带“模拟”标记的 Wi-Fi 测试。手机恢复模式启动不会启用模拟 Wi-Fi。

在已有 [zircon 编译环境](ZIRCON.zh-CN.md) 的仓库中，安装 QEMU、Zstandard
和 LZ4。macOS 可执行 `brew install qemu zstd lz4`，Linux 需要带 GTK 显示的
`qemu-system-aarch64`。准备清单对应的两份原厂输入后，在仓库根目录执行：

```sh
source scripts/env.sh
./scripts/build-zircon.sh
"$SKYWARD_PYTHON" scripts/test-qemu-zircon.py --interactive --out out/qemu-ui
```

脚本首次运行会从 Debian 官方服务器下载哈希固定的 ARM64 通用内核及虚拟
显示／输入模块，只用于预览。macOS 使用 HVF、Cocoa 窗口和独立的 QEMU Zircon
应用标识；Linux 使用 TCG 和 GTK。终端出现 PID 前，脚本会等待 Skyward 绘制主页，
启动失败会输出日志位置。启动命令、PID、QMP socket 和运行信息保存在
`out/qemu-ui/interactive.json`，日志为同目录的 `interactive.log`。

在 macOS 前台选择 **QEMU Zircon**；窗口过大时使用 **View → Zoom To Fit**，
再调整窗口大小。鼠标点击对应触摸，使用界面键盘输入文字。物理键盘的 ↑／↓
对应音量键、Enter 对应电源键、Esc 对应返回。关闭 QEMU 窗口即可结束预览。
脚本会拒绝在同一输出目录重复启动仍在运行的实例。

主页的 **Wi-Fi（模拟）** 可打开无线开关、刷新、输入密码、查看网络详情和
删除网络。`QEMU-Skyward` 和 `QEMU-WPA3` 的测试密码均为 `qemu-demo`；
`QEMU-Open` 无需密码。连接状态会显示“已连接，但无法访问互联网”，不会访问
真实热点；模拟环境中的在线更新与下载会显示解释提示。

2026-11-25 已验证正确手机图片、Wi-Fi 入口、三个热点扫描、密码长度检查、
错误密码提示、正确密码连接、开放热点连接、网络详情和删除网络断开。
主机工作区 946 项测试及主机／Android Clippy 通过。ARM64 组件测试另行执行：

```sh
"$SKYWARD_PYTHON" scripts/test-qemu-zircon.py --out out/qemu-zircon
```

组件报告为 `out/qemu-zircon/report.json`，检查 CLI、zircon 配置、vendor_boot
识别、逻辑分区元数据、解压和 ext4／F2FS 格式化、读写、fsck。所有测试磁盘都在
虚拟机 RAM 中创建。QEMU virt 不模拟 MT6886 整机：原厂 Android init 的启动会
触发无法模拟的 MediaTek 看门狗安全固件调用。可见预览使用通用内核与单独 init，
不能证明真机显示、触摸、Wi-Fi、震动、TEE／FBE 解密或完整 Android 启动可用。
发布的 vendor_boot 镜像继续保留原厂内核、DTB 和全部恢复模式模块。

## English

`v0.5.1-alpha.2` corrects the Redmi Note 13 Pro+ phone image and adds a visible ARM64
QEMU preview with explicitly labelled Wi-Fi simulation. Normal phone recovery
startup never enables the simulation.

With the [zircon build environment](ZIRCON.md) and matching stock inputs ready,
install QEMU, Zstandard and LZ4 (`brew install qemu zstd lz4` on macOS; a GTK-enabled
`qemu-system-aarch64` on Linux), then run the commands above at the repository root.
The first interactive run downloads a SHA-256-pinned kernel and virtual display/input
modules from Debian. These are used only by the preview. macOS uses HVF/Cocoa;
Linux uses TCG/GTK. Startup waits for the home frame before reporting success.
The PID, command, QMP socket and log are recorded under `out/qemu-ui`.

Select **QEMU Zircon** on macOS. Use **View → Zoom To Fit** and resize the window
if necessary. Click to touch, and use the on-screen keyboard to type. Physical
Up/Down map to volume, Enter to power, and Esc to Back. Close the QEMU window to
stop it. A second instance using the same output directory is rejected.

**Wi-Fi (simulation)** supports power, refresh, passwords, network details and
forgetting. Both `QEMU-Skyward` and `QEMU-WPA3` use `qemu-demo`; `QEMU-Open` needs
no password. Connections are explicitly offline. Online updates and downloads
show a simulation notice.

On 2026-11-25 the preview was checked for the correct phone image, Wi-Fi entry,
three simulated hotspots, password-length validation, wrong-password reporting,
password-protected and open connections, details and forgetting. All 946 host
workspace tests and host/Android Clippy passed. Run the component command above
for CLI/configuration, vendor_boot, LP metadata, archive streams and ext4/F2FS
formatting, read/write and fsck checks; the report is `out/qemu-zircon/report.json`.

QEMU virt is not an MT6886 board. Stock Android init hits an unsupported MediaTek
watchdog secure-firmware call. The visible preview uses a generic kernel and a
separate init; it does not validate zircon hardware or hardware-backed FBE.
All test disks are new guest-RAM files. The released vendor_boot keeps the stock
kernel, DTB and recovery modules.
