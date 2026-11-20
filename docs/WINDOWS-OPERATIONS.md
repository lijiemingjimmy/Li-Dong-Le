# Windows 启动、登录和初始化

## 启动运行环境

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\ldl-windows.ps1 start
```

`start` 会启动或复用 `ldl_win_x64`、推送并启动 Frida server、建立 ADB/Frida 回环转发，并启动本地控制台。重复执行不会创建第二个 AVD。

控制台地址：<http://127.0.0.1:16081/>

## 安装和打开应用

```powershell
.\ldl-windows.ps1 install-apks
.\ldl-windows.ps1 compatibility
.\ldl-windows.ps1 open-app
```

## 登录和初始化

在 Android 模拟器或控制台中登录微信和乐动力，然后执行：

```powershell
.\ldl-windows.ps1 setup
.\ldl-windows.ps1 check
.\ldl-windows.ps1 status
```

`setup` 读取当前 Android 登录态、验证账号、读取作业要求并写入本机私有配置。首次初始化不会开启控制台内置定时。

## 每次执行

预览参数但不提交：

```powershell
.\ldl-windows.ps1 plan
```

手动提交一次：

```powershell
.\ldl-windows.ps1 run --now
```

只在服务端资格、日期、时段、本地每日回执都允许时提交。上传成功后还会回查服务端的距离、用时和完成次数；只有回查一致才标记完成。

## 日常检查

```powershell
.\ldl-windows.ps1 check
.\ldl-windows.ps1 status
```

如果出现 `uncertain`、`awaiting_confirmation` 或 `needs_review`，先回查，不要删除回执，也不要强制重试。
