# Skyward 0.5.1 sync / 上游功能同步

[English](#english) | [简体中文](#简体中文)

## 简体中文

本次将 [kirklin/skyward](https://github.com/kirklin/skyward) 的完整 main 分支合并到
zircon 适配，固定至 `43ec6da19402cf344b966bbb8c85c04fd2ffdcad`（0.5.1），同步日期为
2026-11-24。来源记录在 [UPSTREAM.toml](../UPSTREAM.toml)，构建报告和发布 ZIP 也携带该记录。

| 功能 | 同步范围 |
| --- | --- |
| 双系统与槽位 | 第二套系统的安装、启动、切换和删除；A/B 槽位控制 |
| 解密与数据访问 | FBE、元数据加密、未加密数据分区；安全服务和 NFC／安全元件驱动的启动顺序 |
| 安装与刷写 | ROM ZIP、OTA payload、ADB sideload、USB 存储；boot/init_boot/vendor_boot/recovery/dtbo/vbmeta、完整 super、逻辑分区、稀疏镜像及按分区命名的镜像 |
| 更新与保留 Recovery | 系统与 Skyward 在线更新；安装后重新写入 Skyward |
| 备份与恢复 | 系统、应用数据、内置存储、校准／身份分区；在新建数据文件系统中恢复 |
| 文件与维护 | 文件管理、文本编辑器、终端、挂载、文件系统检查和修复、日志、清除数据、功能搜索 |
| 网络与 USB | WLAN 管理、MTP、root ADB、fastbootd |
| 界面与设备信息 | 15 种语言、浅色／深色主题、电池与设备信息、跟随系统时区和 62 个时区的选择 |
| 构建与测试 | Rust 1.100.0、上游依赖使用检查、全部工作区测试；保留上游设备配置和服务 fixture |

本次接入上游全部 19 个新提交。上游新增代码与功能均进入工作区；原有 zircon
配置、原厂镜像 SHA-256 检查、vendor_boot 识别与重新刷入、BinderFS 初始化，以及
本仓库的更新源继续使用。原来的 pearl 参考历史保留在 Git 中。

zircon 的原厂 `fstab.mt6886` 指定了 `fileencryption` 与 `keydirectory`，没有再次指定
`metadata_encryption` 算法。合并保留该情况下的 AES-XTS 默认算法，同时优先采用表中
明确指定的算法，兼容上游新增的未加密分区路径。回归测试使用原厂 userdata 条目验证
这一行为。

设备配置和功能验证状态见 [zircon 编译说明](ZIRCON.zh-CN.md)。当前输入仍为先前确认的
两份 OS3.0.305.0.WNOCNXM 原厂 boot/vendor_boot 镜像。Wi-Fi 和震动配置尚未启用；
FBE 解密、刷包、备份恢复和双系统在 zircon 上仍待实机验证。上游完整的软件实现已经
包含，手机的 vendor/odm 服务、驱动和硬件可用情况须按同版本固件核对。

查看当前源码包含同步基线：

```sh
git merge-base --is-ancestor 43ec6da19402cf344b966bbb8c85c04fd2ffdcad HEAD
```

GitHub Actions 会检查这一关系和版本信息，再验证配置。发布版本为
`v0.5.1-alpha.1`，其 `BUILDINFO.json` 同时记录本仓库提交和上游基线。

## English

The complete [kirklin/skyward](https://github.com/kirklin/skyward) main branch is merged
into the zircon port through `43ec6da19402cf344b966bbb8c85c04fd2ffdcad` (0.5.1),
as of 2026-11-24. [UPSTREAM.toml](../UPSTREAM.toml), the build report and the release
ZIP record that baseline.

| Feature | Synced scope |
| --- | --- |
| Dual boot and slots | Install, start, switch and remove a second system; A/B slot control |
| Decryption and data | FBE, metadata encryption, plain data partitions, secure service and NFC/secure-element driver startup |
| Installing and flashing | ROM ZIPs, OTA payloads, ADB sideload and USB storage; boot/init_boot/vendor_boot/recovery/dtbo/vbmeta, whole super, logical partitions, sparse images and partition-named images |
| Updates and recovery retention | System/Skyward online updates and restoring Skyward after a ROM install |
| Backup and restore | System, app data, internal storage and calibration/identity partitions; restore into a newly created data filesystem |
| Files and maintenance | File manager, editor, terminal, mounts, filesystem checking/repair, logs, wiping and feature search |
| Networking and USB | WLAN management, MTP, root ADB and fastbootd |
| UI and device information | All 15 languages, light/dark themes, battery/device information, installed-system time-zone detection and 62 time zones |
| Builds and regression coverage | Rust 1.100.0, upstream dependency checks and full workspace tests; upstream device configurations and service fixtures |

All 19 new upstream commits are included. The port retains its zircon configuration,
stock SHA-256 checks, vendor_boot detection/retention, BinderFS startup and release
repository. The original pearl reference history is retained.

The stock zircon `fstab.mt6886` names file encryption and a metadata key directory,
but omits the metadata cipher. The merge preserves the AES-XTS default for that case,
prefers an explicitly named cipher elsewhere in the table, and retains upstream's
plain-data support. A regression test reads the stock userdata entry.

See [the zircon build notes](ZIRCON.md) for device validation. Builds still use the
two supplied OS3.0.305.0.WNOCNXM stock inputs. WLAN and haptic configuration are not
enabled; FBE, flashing, backup/restore and dual boot still require zircon phone tests
and matching vendor/odm service and driver validation.

CI verifies that the pinned upstream commit is an ancestor of the build, and checks
version/configuration consistency. Release `v0.5.1-alpha.1` records both the port
commit and upstream baseline in `BUILDINFO.json`.
