# 第三方组件与上游来源

本仓库的控制代码沿用上游 MIT 许可，保留原始版权声明。x86 适配基于 [wkj2333666/Li-Dong-Le](https://github.com/wkj2333666/Li-Dong-Le)，上游基线提交为 `f68b48f32f088253be648deca4528f16340f8434`。

| 组件 | 来源及说明 |
|---|---|
| Redroid / Android | [remote-android/redroid-doc](https://github.com/remote-android/redroid-doc)，多种上游许可；构建时保留镜像已有许可文件 |
| Android 12 / Houdini WSA 镜像 | [ERSTT/redroid](https://github.com/ERSTT/redroid)，`erstt/redroid@sha256:7c1f4355fa245e55cc15fa46ff3be8c347cee73c3eeb5c8b7a6def93013eb54d`；含专有转译运行时，部署时从提供者拉取 |
| Frida 16.7.19 | [官方发布](https://github.com/frida/frida/releases/tag/16.7.19)，wxWindows Library Licence / LGPL 相关条款；未修改二进制，下载后校验，许可随镜像保存在 `/licenses/frida/` |
| Python / Debian 软件包 | [Python](https://www.python.org/psf/license/)；Debian `adb`、`tzdata`、`ca-certificates` 各自许可 |
| 乐动力 10.14.2 | 原版 APK 从上游固定提交单独下载；非本项目 MIT 许可覆盖 |
| 微信 8.0.42 ARM32 | [腾讯官网](https://weixin.qq.com/)提供的兼容包，从腾讯 CDN 单独下载；非本项目 MIT 许可覆盖 |

源码包和本次 Release 不再附带第三方 APK、转译库或 Android 镜像。Git 历史保留上游最初的 APK Git LFS 指针。下载 URL 与 SHA256 见 `apks/manifest.json`，不能把本项目的代码许可理解为第三方二进制的再分发授权。

本项目与上述第三方应用运营者无隶属关系。公共代码中的应用标识符和 appKey 来自应用协议，并非用户账号凭据；用户令牌、Cookie 和账号数据只应存放在私有数据目录。
