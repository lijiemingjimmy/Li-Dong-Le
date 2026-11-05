# 第三方组件

本项目自己编写的控制代码按 MIT 发布。以下运行时组件由各自上游提供，保留各自许可；其源码和二进制在构建或部署时获取，不放入Git仓库。

| 组件 | 用途 | 上游 |
|---|---|---|
| Redroid / Android | 容器内 Android；Android init 配置在构建时局部修改 | https://github.com/remote-android/redroid-doc |
| Python | 控制服务及脚本运行时 | https://www.python.org/psf/license/ |
| Debian adb、tzdata、ca-certificates | ADB、时区、TLS证书 | https://packages.debian.org/ |
| Docker Engine / Compose | 构建、容器编排 | https://github.com/docker/compose |
| Frida 16.7.19 | 仅修正客户端对已连接Ethernet的网络可用性误判 | https://github.com/frida/frida/tree/16.7.19 |

Redroid 的许可说明见其官方 README；Android 及其依赖包含多种开源许可。Docker 构建保留上游镜像中的第三方许可文件，不将这些组件重新许可为 MIT。

Frida保留其wxWindows Library Licence及LGPL例外条款，许可证随Android镜像放在`/licenses/`。服务器二进制从固定上游版本下载，不放入Git仓库。本项目不修改Frida本身。

仓库通过Git LFS保存`apks/ledongli.apk`（乐动力10.14.2）和`apks/wechat.apk`（微信8.0.79），均为未修改的原始安装包。它们由Compose只读挂载供安装，不进入Docker构建上下文或控制镜像。校验值见`apks/SHA256SUMS`。

第三方APK的版权及使用条款归各自权利人所有，不属于本项目MIT许可证的授权范围。本项目与这些应用的运营方没有隶属关系；原始安装包不包含部署者的账号、登录态或作业运行数据。
