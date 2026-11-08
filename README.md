# Li-Dong-Le · x86_64

在 **x86_64 Linux** 上运行乐动力 Android 客户端和浏览器控制台。基于 [wkj2333666/Li-Dong-Le](https://github.com/wkj2333666/Li-Dong-Le) 的 x86 适配版本，使用 Android 12 + Houdini，提供登录、账号初始化、作业读取与手动执行入口。

**v0.1.0：已在一台 AMD x86_64 Linux 主机上验证构建、安装、本人登录、账号初始化，以及一次手动上传、作业关联和服务端回查。** 这是特定版本组合的兼容性结果，不代表所有设备和账号都适用。

## 工作方式

```text
浏览器 → SSH 转发 → 127.0.0.1:6080 控制台
                          ↓ ADB / Frida（私有容器网络）
                  Android 12 x86_64 + Houdini
                     ├─ 乐动力 10.14.2 ARM64
                     └─ 微信 8.0.42 ARM32
```

Android 和 Python 控制服务原生运行在 x86_64 上，APK 中的 ARM 库通过 Houdini 执行。APK 保持原样；此仓库没有第三方应用源码，也没有将 APK 重新编译或签名。

`run` 按配置生成运动摘要并上传，再关联到当前账号的作业，**会实际写入账号记录**。`check` 只查询资格，`plan` 只生成预览。默认不启用定时执行。

## 运行条件

- x86_64 Linux，Docker Engine、Docker Compose v2，Python 3.10+。
- 4 KiB 内核页，`binderfs`、`memfd`、IPv6、`/dev/dma_heap/system`。
- 建议至少 8 GiB 可用内存和 15 GiB 磁盘空间。默认 Android 上限 6 GiB / 4 CPU，控制器上限 1 GiB / 2 CPU，可在 `.env` 调整 Android 限额。
- Docker 需能运行 `privileged` Android 容器；首次登录需要用户本人操作。

Mac 可用于浏览器操作和 SSH 转发；本版本的 Android 宿主要求 Linux。ARM64 部署请参考上游仓库。

## 快速开始

### 1. 获取代码与安装包

```sh
git clone https://github.com/lijiemingjimmy/Li-Dong-Le.git
cd Li-Dong-Le
cp .env.example .env
python3 deploy/fetch_apks.py
python3 deploy/fetch_apks.py --verify-only
```

也可以解压 Release 的源码包。**本版本无需 Git LFS**；仓库和 Release 不附带 APK、转译库、账号状态或运行数据。下载脚本使用 [固定来源与 SHA256](apks/manifest.json)，校验失败时不会替换原有文件。乐动力包来自上游固定提交，微信兼容包来自腾讯官方 CDN。

### 2. 检查宿主并启动

```sh
# 内核已提供 binder_linux 模块时，由管理员加载：
sudo modprobe binder_linux
./ldl doctor
docker compose up -d --build
docker compose ps
./ldl install-apks
./ldl compatibility
./ldl open-app
```

`doctor` 只检查，不安装内核模块或修改系统配置。缺少内核功能时先处理宿主环境，参见 [故障排查](docs/TROUBLESHOOTING.md)。项目会在 Android 镜像构建时移除 init 对宿主全局 sysctl 的写入。

### 3. 打开控制台并本人登录

服务器本机访问 `http://127.0.0.1:6080`。远程服务器可从自己的电脑运行：

```sh
ssh -N -L 16080:127.0.0.1:6080 your-user@your-server
```

然后在这台电脑打开 `http://127.0.0.1:16080`：

1. 点击 **打开微信**，本人完成登录。可以在微信右上角选择简体中文。
2. 点击 **打开乐动力**，本人确认首次协议，选择微信登录并授权。
3. 点击 Android 画面的输入框后，可用网页底部输入栏发送英文、数字和符号；中文可用 Android 键盘。

控制台只监听宿主回环地址并校验 Host/Origin。ADB 和 Frida 端口不对宿主发布。首次安装页面、控制台健康状态都不能代表账号登录成功。

### 4. 初始化并只读检查

```sh
./ldl setup
./ldl status
./ldl check
./ldl plan
```

`setup` 从本人刚登录的 Android 实例读取登录态，发现用户、班级和任务绑定，写入私有配置。`check` 返回当前服务端资格；今天已完成时会跳过。`plan` 输出的随机预览与随后实际执行的随机值可能不同。

### 5. 手动执行一次

```sh
./ldl run --now
./ldl status
```

该命令会提交记录。默认距离 3050–3300 米、用时 1050–1110 秒，并校验配速、作业日期、完整时段和服务端限额。配置不符合当前作业要求会停止。

不带 `--now` 的 `./ldl run` 会在执行前随机等待最多 20 分钟。每次写入前保存本地回执；出现响应丢失或不确定结果时停止重发。只有服务端距离、用时匹配并且作业计数增加，才标记 `completed`。

本地同一北京时间日期最多完成一次；服务端的每日、每周和任务限制仍以当前账号的作业规则为准。遇到 `uncertain` 或 `needs_review` 应先回查记录，不要删除当日回执来重试。

## 数据、定时与维护

数据默认在仓库旁的 `../li-dong-le-data/`，包括 Android 数据、凭据、Cookie、账号绑定和私有回执；不要把此目录、`.env` 或运行截图上传到仓库。

```sh
docker compose down             # 停止，保留数据
docker compose up -d --no-build  # 使用现有镜像启动
```

定时执行默认关闭；只有显式执行 `./ldl schedule-on` 或 `./ldl setup --enable-schedule` 才开启。`./ldl schedule-off` 关闭。默认时间为北京时间 15:00，加 0–20 分钟随机延迟；具体要求和配置见 [运维说明](docs/OPERATIONS.md)。

## 为什么使用这个版本组合

| 组件 | 固定版本 |
|---|---|
| Android / 转译 | Android 12 + Houdini WSA，固定镜像摘要 |
| 乐动力 | 10.14.2 / versionCode 10092 / ARM64 |
| 微信 | 腾讯官方兼容包 8.0.42 / versionCode 2460 / ARM32 |
| Frida | 16.7.19 / Android x86_64 |

实测原 Android 13 NDK 转译层无法稳定运行仓库附带的 ARM64 微信；匹配 Android 12 的 Houdini 配合 ARM32 微信通过了本次验证。微信兼容包版本较旧，后续登录可用性取决于应用服务端。详见 [验证记录与限制](docs/VALIDATION.md)。

## 开发与发行

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q app deploy
sh -n ldl deploy/doctor.sh
docker compose config --quiet
```

仓库包含 15 项离线测试，以及 [可选 GitHub Actions 模板](docs/ci.example.yml)。模板覆盖单元测试、语法、Compose 配置和发行文件检查，不登录账号或提交记录；需要时可复制到 `.github/workflows/ci.yml`。本次发布通过本地及 Linux 主机验证，未启用 GitHub Actions。Release 附源码包及 `SHA256SUMS`，不提供含个人状态的镜像。

## 来源与许可

保留上游 MIT 许可和署名，基于提交 `f68b48f32f088253be648deca4528f16340f8434` 适配。Houdini、Android、Frida、APK 等保留各自许可，不属于本项目 MIT 授权范围。见 [LICENSE](LICENSE)、[THIRD_PARTY.md](THIRD_PARTY.md) 和 [CHANGELOG.md](CHANGELOG.md)。
