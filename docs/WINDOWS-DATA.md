# Windows 数据、备份和迁移

## 数据位置

| 数据 | 位置 |
|---|---|
| Android 应用和登录态 | `%USERPROFILE%\.android\avd\ldl_win_x64.avd` |
| 账号凭据、Cookie、作业配置 | 仓库 `private\state\` |
| 每日回执和运行记录 | `private\state\automation\` |
| Frida 与启动日志 | `runtime\` |

这些目录全部属于私有运行数据，已经被 Git 忽略。

## 备份

停止模拟器后再复制数据：

```powershell
adb -s emulator-5556 emu kill
Copy-Item -Recurse -Force private\state private-state-backup
Copy-Item -Recurse -Force "$env:USERPROFILE\.android\avd\ldl_win_x64.avd" avd-backup
```

备份目录不要上传到 GitHub、网盘或 Issue。凭据文件等同于登录态。

## 迁移

先复制 `private\state\`，再复制 AVD 数据。迁移后执行：

```powershell
.\ldl-windows.ps1 start
.\ldl-windows.ps1 status
.\ldl-windows.ps1 check
```

不要在已有登录态的 AVD 上降级微信或清空数据。服务端回执保存在本机状态中，不能通过删除回执来绕过每日限制。

## 删除

确认不再需要 Windows 环境后：

```powershell
adb -s emulator-5556 emu kill
avdmanager delete avd -n ldl_win_x64
Remove-Item -Recurse -Force private\state
```

删除前先确认已经完成数据备份；删除账号状态后需要重新登录。
