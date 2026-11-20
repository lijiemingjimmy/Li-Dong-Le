# Li-Dong-Le

乐动力 Android 客户端的本机自动化运行方案。项目保留上游 MIT 代码署名，提供 Windows x86_64、x86_64 Linux 两条部署路线；源码不包含 APK、登录态、Cookie 或运行回执。

## 先选运行方式

| 平台 | 推荐路线 | 入口 | 说明 |
|---|---|---|---|
| Windows 10/11 x86_64 | Android Emulator + WHPX | `ldl-windows.ps1` | 适合普通 Windows 电脑，不需要 Docker |
| x86_64 Linux | Docker + Android 12/Houdini | `ldl` | 已在特定 AMD Linux 主机验证 |

Windows 是当前主页推荐路线。Android 官方说明 API 30 x86_64 模拟器支持 ARMv7/ARM64 应用，Windows 使用 WHPX 加速：[ARM ABI 支持](https://developer.android.com/studio/releases/emulator)、[WHPX 配置](https://developer.android.com/studio/run/emulator-acceleration)。

## Windows 快速开始

完整步骤见 [Windows 文档目录](docs/README.md)。第一次安装在 PowerShell 中执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-windows.ps1
py -3 deploy\fetch_apks.py
py -3 deploy\fetch_apks.py --verify-only
.\ldl-windows.ps1 start
.\ldl-windows.ps1 install-apks
.\ldl-windows.ps1 compatibility
.\ldl-windows.ps1 open-app
```

在 Android 模拟器或本地控制台登录微信和乐动力：

<http://127.0.0.1:16081/>

然后初始化并检查：

```powershell
.\ldl-windows.ps1 setup
.\ldl-windows.ps1 check
.\ldl-windows.ps1 status
```

手动执行一次：

```powershell
.\ldl-windows.ps1 plan
.\ldl-windows.ps1 run --now
```

`run` 会实际写入账号记录。只有上传后独立回查到距离、时长和作业次数都匹配，才会标记为完成。当天已完成、服务端限额已达、存在未决回执或账号未登录时，脚本会停止，不会强制重试。

## Windows 文档

- [文档总目录](docs/README.md)
- [环境准备和 AVD 初始化](docs/WINDOWS-SETUP.md)
- [启动、登录、初始化和执行](docs/WINDOWS-OPERATIONS.md)
- [数据、备份、迁移和删除](docs/WINDOWS-DATA.md)
- [排错](docs/WINDOWS-TROUBLESHOOTING.md)
- [通用运维和回执规则](docs/OPERATIONS.md)
- [验证记录与限制](docs/VALIDATION.md)

Windows 运行组件：

- Android 11 / API 30 Google APIs x86_64 AVD：`ldl_win_x64`
- Windows Hypervisor Platform（WHPX）
- ADB 设备：`emulator-5556`
- Frida 16.7.19 Android x86_64 server
- 本地控制台：`127.0.0.1:16081`

Google Play 镜像不支持 `adb root`，Windows 方案必须使用 Google APIs x86_64 镜像。Windows ARM 主机不在当前验证范围内。

## Linux Docker 快速开始

Linux 路线保留原有 x86_64 容器部署：

```sh
cp .env.example .env
python3 deploy/fetch_apks.py
python3 deploy/fetch_apks.py --verify-only
sudo modprobe binder_linux
./ldl doctor
docker compose up -d --build
./ldl install-apks
./ldl compatibility
./ldl open-app
```

远程 Linux 主机的控制台只监听宿主回环地址，可通过 SSH 转发访问：

```sh
ssh -N -L 16080:127.0.0.1:6080 your-user@your-server
```

然后访问 <http://127.0.0.1:16080/>。Linux 详细说明见 [运维文档](docs/OPERATIONS.md) 和 [排错文档](docs/TROUBLESHOOTING.md)。

## 数据与安全

私有运行数据包括 Android 应用数据、账号凭据、Cookie、作业绑定、每日回执和日志。Windows 默认在仓库下的 `private\` 和 `runtime\`，Linux 默认在仓库旁的 `../li-dong-le-data/`。这些目录已被 Git 忽略。

不要提交以下内容：

- APK、Frida 二进制和运行日志
- `private/`、`runtime/`、`.env`
- 登录二维码、Cookie、Token、截图和服务器返回的个人数据

控制台、ADB 和 Frida 默认只监听本机回环地址。不要把 16081、6080、27042 或 ADB 端口暴露到公网。

## 执行规则

- `check` 只查询服务端资格。
- `plan` 只生成参数预览。
- `run --now` 才会提交一次记录。
- 每个北京时间日期本地最多提交一次，服务端每日和每周限制仍然有效。
- `uncertain`、`awaiting_confirmation`、`needs_review` 必须先回查，不能删除回执来重试。
- 控制器内置定时默认关闭，避免和外部调度重复。

## 开发验证

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q app deploy
git diff --check
```

当前 Windows 代码已通过 Python 编译、15 项离线测试和 Markdown 本地链接检查；尚未在实际 Windows x86_64 主机上完成登录与提交端到端验证。

## 来源与许可

项目基于上游提交 `f68b48f32f088253be648deca4528f16340f8434` 适配。Houdini、Android、Frida 和第三方 APK 保留各自许可，不属于本项目 MIT 授权范围。详见 [LICENSE](LICENSE)、[THIRD_PARTY.md](THIRD_PARTY.md) 和 [CHANGELOG.md](CHANGELOG.md)。
