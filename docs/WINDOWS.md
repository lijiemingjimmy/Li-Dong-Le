# Windows 本机运行

Windows 版本使用 Android Emulator 的 **Android 11（API 30）Google APIs x86_64** 镜像。Android Emulator 的 API 30 x86_64 镜像包含 ARMv7 和 ARM64 ABI 支持，因此 LDL 和微信的 ARM 库可以在 x86_64 模拟器中运行；Windows 主机使用 WHPX 加速。Google Play 镜像不能 `adb root`，所以这里使用 Google APIs 镜像，不使用 Play Store 镜像。

## 一次性安装

1. 安装 64 位 Python 3.11+、Android Studio 和 Android SDK Command-line Tools。
2. 在 PowerShell 中执行：

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\setup-windows.ps1
   ```

3. 在“启用或关闭 Windows 功能”中启用 **Windows Hypervisor Platform**，重启 Windows。Android 官方文档说明 Windows Emulator 使用 WHPX；较新的 Android Emulator 应优先使用 WHPX。
4. 将 `apks\ledongli.apk` 和 `apks\wechat.apk` 放入本地目录。不要把 APK、账号数据或 Cookie 提交到 Git。

## 启动与登录

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\ldl-windows.ps1 start
.\ldl-windows.ps1 install-apks
.\ldl-windows.ps1 compatibility
.\ldl-windows.ps1 open-app
```

控制台监听 `127.0.0.1:16081`：<http://127.0.0.1:16081/>。首次登录微信和乐动力后执行：

```powershell
.\ldl-windows.ps1 setup
.\ldl-windows.ps1 check
.\ldl-windows.ps1 run --now
```

脚本会在上传后独立回查服务端距离、时长和完成次数；只有回查匹配才报告完成。控制台内置定时默认关闭，避免和 Codex 的每日随机调度重复。

## 数据与排错

- AVD：`%USERPROFILE%\.android\avd\ldl_win_x64.avd`。
- 登录凭据、Cookie、运行回执：仓库下 `private\state\`，已被 Git 忽略。
- Frida x86_64 server：首次 `start` 自动下载并校验 Frida 16.7.19，保存到 `runtime\`，不会提交到 Git。
- ADB 固定设备：`emulator-5556`。
- 本机控制台和 Frida 转发只监听回环地址，不暴露到局域网。

如果 `adb root` 失败，说明使用了 Google Play 镜像或 AVD 不是 `ldl_win_x64`。删除并重建 AVD 前先备份 `private\state\`；不要清空 AVD 数据来绕过登录问题。

Windows 运行需要主机保持开机、联网和不休眠。该适配需要 Windows x86_64；Windows ARM 主机不在验证范围内。

参考：

- [Android Emulator 加速与 WHPX](https://developer.android.com/studio/run/emulator-acceleration)
- [Android Emulator API 30 x86_64 的 ARM ABI 支持](https://developer.android.com/studio/releases/emulator)
- [创建和管理 AVD](https://developer.android.com/studio/run/managing-avds)
