# Windows 本机运行

Windows 适配使用 Android 11（API 30）Google APIs x86_64 模拟器。这个镜像能运行 LDL 和微信的 ARM 库，Windows 主机使用 WHPX 加速。Google Play 镜像不能 `adb root`，所以必须使用 Google APIs 镜像。

按下面顺序操作：

1. [准备 Windows 环境](WINDOWS-SETUP.md)
2. [启动、登录和初始化](WINDOWS-OPERATIONS.md)
3. [执行和核对任务](OPERATIONS.md)
4. [保存、迁移和清理数据](WINDOWS-DATA.md)
5. [排查常见问题](WINDOWS-TROUBLESHOOTING.md)

入口文件：

- `setup-windows.ps1`：安装 SDK 包并创建 `ldl_win_x64` AVD。
- `ldl-windows.ps1`：PowerShell 入口。
- `ldl-windows.cmd`：命令提示符入口。
- `deploy/windows_runtime.py`：启动 AVD、Frida、控制台和 Python 控制器。

Windows 版本使用固定设备 `emulator-5556`，控制台监听 `127.0.0.1:16081`。控制台定时默认关闭，日常随机调度由当前自动任务负责。

## 目前的验证范围

Windows 代码完成静态检查和现有 15 项离线测试；尚未在实际 Windows x86_64 主机上做完整登录和提交验证。Windows ARM 主机不在验证范围内。

官方参考：[WHPX 加速](https://developer.android.com/studio/run/emulator-acceleration)、[API 30 x86_64 的 ARM ABI 支持](https://developer.android.com/studio/releases/emulator)、[AVD 管理](https://developer.android.com/studio/run/managing-avds)。
