# Windows 常见问题

## `adb root` 失败

通常是误用了 Google Play 镜像，或者当前 AVD 不是 `ldl_win_x64`。检查：

```powershell
adb -s emulator-5556 emu avd name
adb -s emulator-5556 root
```

应该看到 AVD 名称 `ldl_win_x64`，并且 `adb root` 能重启 adbd。不要在 Play 镜像上清空数据解决这个问题，应重新创建 Google APIs x86_64 AVD。

## WHPX 不可用或启动很慢

检查 BIOS 的 VT-x/AMD-V 和 Windows Hypervisor Platform。重启后运行：

```powershell
& "$env:ANDROID_SDK_ROOT\emulator\emulator.exe" -accel-check
```

如果使用了第三方虚拟机、旧版 Hyper-V 配置或关闭了 Windows 虚拟化功能，先恢复 WHPX，再启动 AVD。

## `controller_not_ready`

确认 16081 没被占用：

```powershell
Get-NetTCPConnection -LocalPort 16081 -ErrorAction SilentlyContinue
```

查看 `runtime\controller.log` 和 `runtime\emulator.log`。控制台只监听本机回环地址，不要把端口映射到公网。

## `frida_download_checksum_mismatch`

删除未完成的 `runtime\frida-server-16.7.19-android-x86_64.xz` 后重新执行 `start`。不要手动替换为其他架构的 Frida server。

## 应用打不开或 ARM 库加载失败

确认使用的是 Android 11 API 30 x86_64 Google APIs 镜像，并重新安装两个 APK：

```powershell
.\ldl-windows.ps1 install-apks
.\ldl-windows.ps1 open-app
```

Windows ARM 主机、Google Play 镜像和 Android 12+ x86_64 镜像不属于当前验证组合。

## 登录失效

不要删除 `private\state` 或 AVD 数据。先在模拟器中重新打开微信和乐动力并完成登录，再运行：

```powershell
.\ldl-windows.ps1 setup
.\ldl-windows.ps1 check
```
