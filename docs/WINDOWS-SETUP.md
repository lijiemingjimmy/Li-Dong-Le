# Windows 环境准备

## 适用机器

- 64 位 Windows 10/11。
- Intel VT-x 或 AMD-V 已在 BIOS 开启。
- 建议至少 16 GB 内存和 20 GB 可用 SSD 空间。
- 当前适配目标是 Intel/AMD x86_64 Windows；Windows ARM 不在验证范围内。

## 安装软件

安装以下组件：

1. 64 位 Python 3.11 或更高版本，并确认 `py -3` 可用。
2. Android Studio。
3. Android SDK Command-line Tools。

在 Windows 功能中启用 **Windows Hypervisor Platform**，然后重启。Android Emulator 在 Windows 上使用 WHPX 加速；不要同时关闭 Hyper-V 又依赖 WHPX。

## 创建 AVD

在仓库根目录打开 PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-windows.ps1
```

脚本安装以下 SDK 包：

- `platform-tools`
- `emulator`
- `platforms;android-30`
- `system-images;android-30;google_apis;x86_64`

然后创建名为 `ldl_win_x64` 的 AVD。不要在 AVD Manager 中改成 Google Play 镜像；Play 镜像没有 `adb root`，脚本无法注入 Frida。

## 准备 APK

将已获得的两个 APK 放在：

```text
apks\ledongli.apk
apks\wechat.apk
```

仓库忽略 APK 文件。不要把 APK、登录态、Cookie 或 `private\` 目录提交到 Git。
