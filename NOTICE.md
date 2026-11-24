# Attribution and third-party materials / 署名与第三方材料

This repository contains the zircon port of Skyward, a recovery written in Rust.
The Skyward source is distributed under **GPL-3.0-or-later**, as specified in
[LICENSE](LICENSE) and the workspace metadata. Original copyright and license
notices remain in the source and Git history.

本仓库是 Rust 恢复项目 Skyward 的 zircon 适配版。Skyward 源码按 **GPL-3.0-or-later**
分发，具体条款见 [LICENSE](LICENSE)。源码中的原始版权、许可声明与 Git 历史予以保留。

## Upstream / 上游

- Original Skyward / 原始项目: [kirklin/skyward](https://github.com/kirklin/skyward).
- Current source baseline / 当前同步基线: Skyward 0.5.1, commit `43ec6da19402cf344b966bbb8c85c04fd2ffdcad`; see [UPSTREAM.toml](UPSTREAM.toml).
- Reference port / 本次参考: [mytiantian001/pearl-skyward](https://github.com/mytiantian001/pearl-skyward), commit `d1d349481248e32a43bed7a1bfcd1124840beba8`.
- Intermediate fork / 中间分支: [BkaNeko/xaga-skyward](https://github.com/BkaNeko/xaga-skyward).
- zircon port maintainer / zircon 适配维护者: [Eason206](https://github.com/Eason206).

## Fonts and firmware / 字体与固件

- KirkMono ships with its SIL Open Font License notice in [resources/fonts/KirkMono-OFL.txt](resources/fonts/KirkMono-OFL.txt); the recovery image carries that notice as well.
- MiSansVF retains its embedded copyright notice: “Copyright © 2020-2025 Beijing Xiaomi Mobile Software Co.,Ltd. All Rights Reserved.” It was inherited from the reference repository and remains a separately licensed font.
- The recovery image preserves the stock device tree, drivers, init, adbd, libraries and other vendor recovery components. Their original licenses and ownership remain applicable. GPL licensing of this repository does not relicense those components.
- Original `boot.img` and `vendor_boot.img` inputs are kept outside Git; their identities are recorded by version and SHA-256 in [devices/zircon-stock.json](devices/zircon-stock.json).

KirkMono 的 SIL Open Font License 声明随源码与恢复镜像提供。MiSansVF 保留内嵌的小米版权声明。
生成的恢复镜像沿用原厂设备树、驱动、init、adbd、库等组件；这些组件仍适用各自的原始许可，
本仓库的 GPL 许可不改变其许可。原始输入镜像置于 Git 之外，版本与哈希记录在设备清单中。
