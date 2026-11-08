# 运维与数据

## 私有状态

默认 `LDL_DATA_DIR=../li-dong-le-data`：

- `android/`：应用安装与登录数据。
- `controller/state/`：账号凭据、Cookie、作业要求及兼容层状态。
- `controller/state/automation/config.json`：本人账号与作业绑定、参数和定时开关。
- `controller/state/automation/days/`、`runs/`：每日回执、请求候选和服务端回读结果。

迁移时停止容器再备份整个数据目录。只复制源码不能迁移登录态；不要将运行目录或备份上传到公开仓库。`docker compose down` 保留这些宿主目录。

## 命令

| 命令 | 行为 |
|---|---|
| `./ldl doctor` | 本机环境检查 |
| `./ldl install-apks` | 安装乐动力和 ARM32 微信 |
| `./ldl compatibility` | 当前版本的 WebView / Ethernet 兼容设置 |
| `./ldl open-app` | 打开乐动力并等待网络兼容层 |
| `./ldl setup` | 读取本人登录态，初始化私有配置；定时默认关闭 |
| `./ldl status` | 本地配置、兼容状态和最近结果 |
| `./ldl check` | 读取服务端作业与执行资格 |
| `./ldl plan` | 生成随机参数预览，无提交 |
| `./ldl run --now` | 手动生成并提交一次，仍受所有检查约束 |
| `./ldl run` | 同上，提交前随机等待最多 20 分钟 |
| `./ldl schedule-on` / `schedule-off` | 显式开启或关闭定时 |

## 定时

首次 `setup` 不启用定时。只有本人明确需要时执行 `./ldl schedule-on`。默认北京时间 15:00 加 0–20 分钟随机延迟。配置项包括 `scheduled_hour`、`submission_jitter_seconds`、`timezone`、`distance_m`、`duration_seconds` 和 `pace_seconds_per_km`。

手动和定时使用同一个进程锁与每日回执。成功后本地每天最多一次；还会检查服务端当前限额。`--now` 只取消随机等待，不取消日期、完整运动时段或资格检查。

## 异常回执

`completed` 必须同时满足服务端距离和用时匹配、作业计数增加。`uncertain`、`awaiting_confirmation`、`needs_review` 表示结果不完整，应先回查服务端与本地回执，不要删除回执以强制重试。

HTTP 成功、进程退出码为 0 或容器健康，都不应单独当作作业完成证据。

## 更新

先备份私有数据，再更新源码、核对发行说明并重新构建。不要在已有较新微信登录数据的环境直接尝试降级；发行版的 ARM32 配置用于独立的新 Android 数据目录。

服务器重启后若 binder 模块未加载，由管理员运行 `sudo modprobe binder_linux`。项目不自动创建开机模块配置、cron 或巡检任务。
