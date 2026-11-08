# v0.1.0 · x86_64 首个发行版

把上游 ARM64 部署方案适配为默认可在 x86_64 Linux 构建的 Android 12 / Houdini 方案，提供浏览器操作、本人登录、账号初始化、作业读取和手动执行入口。

## 主要内容

- 固定 Android 12 / Houdini WSA 镜像和 Frida x86_64 版本及校验。
- 配套乐动力 10.14.2 ARM64、腾讯官方微信 8.0.42 ARM32 兼容包。
- 控制台可直接打开微信和乐动力，并提供输入与登录指引。
- APK 单独按固定来源和 SHA256 下载；源码包不包含 APK、登录态、Cookie、运行回执或个人部署信息。
- README、排错、运维、来源与许可、验证记录及 15 项离线测试。

## 验证

- 特定 AMD x86_64 Linux 环境：登录、账号初始化、一次手动上传和作业关联、独立服务端回查通过。
- 发行配置的独立无账号环境：构建、Android 启动、两个 APK 安装和乐动力兼容层就绪通过。
- 15 项离线测试通过，覆盖校验失败保留旧文件、请求来源检查、应用启动白名单、完整运动时段和重复提交保护。
- 定时执行默认关闭。本次没有启用 GitHub Actions，提供可选工作流模板。

## 使用

解压源码包后：

```sh
cp .env.example .env
python3 deploy/fetch_apks.py
sudo modprobe binder_linux
./ldl doctor
docker compose up -d --build
./ldl install-apks
./ldl compatibility
./ldl open-app
```

浏览器登录步骤与远程 SSH 转发见 README。本人登录后先执行 `setup`、`check`、`plan`；`run` 会生成并提交运动摘要，实际写入账号记录。

## 边界

只验证了特定 AMD 主机和版本组合。旧版微信的后续登录可用性受服务端影响；其他设备与长期稳定性未覆盖。宿主必须满足内核要求，Mac 仅作为浏览器和 SSH 客户端。

本项目保留上游 MIT 署名；第三方应用及转译运行时仍遵循各自许可。附件为源码 `.tar.gz`、`.zip` 和 `SHA256SUMS`，不包含预置账号或第三方二进制。
