# LDL Automation

基于原版乐动力客户端的容器化自动化工具。Docker Compose 同时管理 Android 和控制服务；浏览器提供首次登录和日常查看入口，Python 通过原生 MTOP SDK 读取作业、提交运动摘要并回读结果。

当前适配乐动力 **10.14.2 / versionCode 10092**。自动作业流程使用 Activity、`WEB_URL` 和原生桥接，不依赖屏幕坐标。浏览器中的点击只是供用户手动操作 Android 界面。

## 运行条件

- Linux Docker Engine 与 Docker Compose v2。
- 宿主内核：4KiB 页、binderfs、memfd、IPv6、DMA-BUF heap。
- 当前发布包支持ARM64 Linux，推荐至少4GB内存。AMD64不在本版本适配范围内。
- Android 服务需要 `privileged`；容器共享宿主内核，Docker无法替代缺失的内核功能。
- Git LFS、用户自己的可用账号和网络。仓库通过Git LFS提供原版乐动力10.14.2和微信8.0.79 APK。

先运行检查：

```sh
./ldl doctor
```

Redroid 的宿主要求和安装说明见[官方部署文档](https://github.com/remote-android/redroid-doc/tree/master/deploy)。本项目不会自动修改宿主内核、页大小或加载内核模块。

## 启动

默认数据保存在仓库旁边的 `../ldl-automation-data/`，不进入仓库或镜像。

使用`git clone`获取仓库，并在仓库目录拉取、校验APK：

```sh
git lfs install --local
git lfs pull
sha256sum -c apks/SHA256SUMS
```

APK由Compose从仓库的`apks/`目录只读挂载，不进入Docker构建上下文。需要使用自己的APK目录时，可修改`.env`中的`LDL_APK_DIR`；乐动力版本仍需符合当前适配要求。

```sh
cp .env.example .env
# 软件源连接有问题时，可在.env中选择可达的DEBIAN_MIRROR镜像域名。
docker compose up -d --build
./ldl install-apks
./ldl compatibility
./ldl open-app
```

在Docker宿主机浏览器访问 `http://127.0.0.1:6080`，自行完成首次登录。

控制台不设置额外口令，默认仅绑定宿主回环地址；ADB端口不对宿主发布。HTTP服务检查Host和Origin，并且不会记录屏幕和输入内容。

登录后初始化本人作业配置：

```sh
./ldl setup
./ldl check
./ldl plan
```

`setup` 从当前 Android 实例读取本人的登录态，并动态发现任务ID、班级作业ID和乐动力用户ID。该命令只读取数据和生成私有配置，不提交运动记录，也不会默认启用定时任务。

## 手动与定时

```sh
# 手动执行；默认随机等待最多20分钟
./ldl run
# 立即执行；距离、用时仍随机
./ldl run --now
# 启用或关闭定时
./ldl schedule-on
./ldl schedule-off
./ldl status
```

也可以在初始化时显式启用：`./ldl setup --enable-schedule`。

当天漏跑时，先执行 `./ldl check`。确认返回 `eligible` 后，用 `./ldl run --now` 立即补交，再用 `./ldl status` 查看结果。补交仍受当日名额和有效时段限制；该命令使用当前日期。

默认每日北京时间15:00加0–20分钟随机延迟，距离3050–3300米，总用时1050–1110秒，同时满足配速330–420秒/公里。参数位于数据目录中的 `controller/state/automation/config.json`。与本人作业要求不兼容时停止执行，需要自行调整参数。

脚本会检查服务端每日限额、班级作业、用户ID、作业日期和完整运动时段。同一份班级作业的任务ID变动时使用服务端返回的当前ID；班级作业变更时停止，请核对后重新执行 `./ldl setup`。手动和定时共用锁，每次写入前保留私有日志；丢失响应时不会自动重发。只有回执中的任务、距离和用时与当次提交一致，且同一份作业的计数增加，才标记完成。

首次登录需要本人操作，登录失效后也可能需要重新登录。容器化不会绕过第三方应用的账号授权或服务端规则。

## 数据和更新

已有部署获取新版代码后，沿用原来的 `.env` 和 `LDL_DATA_DIR`，重建并启动服务：

```sh
docker compose up -d --build
./ldl check
```

同一份班级作业的任务ID更新会在运行时自动识别，已有登录态、配置和定时设置可以继续使用。

- Android数据、登录凭据、Cookie、作业ID、任务响应、记录、截图均留在外部数据目录。
- `.env`、镜像、运行数据、测试和测试结果均不纳入Git和Docker构建上下文。仓库仅纳入`apks/`下指定的两个原版APK及校验文件，APK通过Git LFS保存，仍排除在Docker构建上下文之外。
- `docker compose down` 停止容器并保留数据；重新启动可复用当前登录状态。
- 迁移自己的部署时需保留整个数据目录，包括`android/`和`controller/`；不要把自己的数据目录提供给其他用户。
- Android基础镜像按摘要固定。`Dockerfile.android` 在构建时禁用Android init对宿主全局sysctl的写操作；不会修改宿主配置。

## 适配边界

已在ARM64 Linux上使用全新数据目录验证两个镜像的构建、Android启动、健康检查、APK安装、浏览器画面/输入，以及乐动力微信登录入口跳转至微信登录页。在Waydroid环境中验证了同一班级作业变更任务ID后的补交，服务端回读确认作业计数增加。容器版尚未完成登录后的端到端提交验证。微信账号授权、其他设备及后续APK版本不在已验证范围内。版本、原生桥接或登录不匹配时会停止。

Redroid默认网络是Ethernet，乐动力微信授权前置检查对此存在误判。`compatibility`会启用一个仅针对当前乐动力进程的网络兼容层：系统报告Ethernet已连接时，修正`NetStatus.isNetworkEnable`的结果。该适配使用固定版本Frida，不修改APK；不是定位模拟或环境隐匿功能。是否能完成最终账号授权仍由微信和应用服务端决定。

## 许可

自有控制代码采用[MIT](LICENSE)。第三方Android运行时、系统工具和应用不受本项目MIT许可证覆盖，详见[第三方说明](THIRD_PARTY.md)。仓库内的第三方APK为原始安装包，不包含个人登录态或作业运行数据。
