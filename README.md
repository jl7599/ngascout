# NgaScout

NGA 论坛帖子监控 + 归档工具。支持三种业务场景：

1. **监控推送**：定时爬取指定帖子中指定用户的发言，通过飞书机器人推送通知
2. **帖子归档**：全量归档指定帖子的所有回复，支持断点续传
3. **用户归档**：全量归档指定用户在所有帖子中的发言

## 项目结构

```text
src/
├── __init__.py
├── __main__.py              # 便捷入口：python -m src → 运行 monitor
├── jobs/                    # 可定时运行的任务
│   ├── monitor.py           # 监控帖子 + 飞书推送
│   ├── archive_thread.py    # 归档帖子
│   └── archive_author.py    # 归档用户发言
└── core/                    # 共享业务逻辑
    ├── config.py            # 配置解析
    ├── nga.py               # NGA API 客户端
    ├── notify.py            # 飞书推送 + 内容清洗
    ├── store.py             # 监控数据存储
    └── author_archive_store.py  # 用户归档存储
```

## 配置

复制 `.env.example` 为 `.env`，填写以下配置：

### 监控推送（默认启用）

| 变量 | 说明 | 示例 |
|------|------|------|
| `WATCH` | 关注列表，格式：`tid,uid1,uid2\|tid2,uid3` | `45905087,557398\|45974302` |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook 地址 | `https://open.feishu.cn/...` |
| `NGA_COOKIE` | NGA 登录 Cookie | `ngacn0comUserInfo=...` |
| `CRON_INTERVAL` | 检查间隔（分钟，默认 5） | `5` |

- `WATCH` 中帖子间用 `|` 分隔，帖子内用户 uid 用 `,` 分隔
- 如果帖子后不指定 uid，默认关注楼主

### 帖子归档（需手动启用）

| 变量 | 说明 | 示例 |
|------|------|------|
| `ARCHIVE_THREAD_TID` | 要归档的帖子 ID 或 URL | `45905087` |

### 用户归档（需手动启用）

| 变量 | 说明 | 示例 |
|------|------|------|
| `ARCHIVE_AUTHOR_ID` | 要归档的用户 ID | `557398` |
| `ARCHIVE_AUTHOR_NOTIFY` | 是否推送新增/变更内容 | `true` |

## 本地运行

```bash
uv sync

# 监控推送
uv run python -m src.jobs.monitor
# 或使用便捷入口
uv run python -m src

# 帖子归档
uv run python -m src.jobs.archive_thread 45905087
# 也可从 URL 中提取 tid
uv run python -m src.jobs.archive_thread "https://bbs.nga.cn/read.php?tid=45905087"

# 用户归档
uv run python -m src.jobs.archive_author --authorid 21321600
# 限制作业主题数量（调试用）
uv run python -m src.jobs.archive_author --authorid 21321600 --limit-threads 5
# 推送新增或变更内容
uv run python -m src.jobs.archive_author --authorid 21321600 --notify
```

帖子归档和用户归档也支持通过环境变量配置参数（Docker 部署时有用）：

```bash
# 使用环境变量替代 CLI 参数
ARCHIVE_THREAD_TID=45905087 uv run python -m src.jobs.archive_thread
ARCHIVE_AUTHOR_ID=557398 uv run python -m src.jobs.archive_author
```

用户归档输出到：

```text
data/authors/{用户id}_{用户名}/{主题id}_{文章标题}.json
```

多次执行会按 `pid` 去重；如果同一楼层内容变化，会更新 JSON 内的最新内容。

## 测试

```bash
uv run pytest -v
uv run ruff check .
```

## Docker 部署

```bash
cp .env.example .env
# 编辑 .env 填写真实配置
docker compose up -d
```

查看日志：

```bash
docker compose logs -f
```

### 启用归档任务

归档任务默认未启用。编辑 `cron.template` 取消注释对应行：

```text
# 帖子归档：取消下面这行注释，并在 .env 中设置 ARCHIVE_THREAD_TID
# 0 */6 * * * cd /app && uv run python -m src.jobs.archive_thread >> /proc/1/fd/1 2>> /proc/1/fd/2

# 用户归档：取消下面这行注释，并在 .env 中设置 ARCHIVE_AUTHOR_ID
# 0 */6 * * * cd /app && uv run python -m src.jobs.archive_author >> /proc/1/fd/1 2>> /proc/1/fd/2
```

同时在 `.env` 中取消注释并填写对应变量：

```env
ARCHIVE_THREAD_TID=45905087
# 或
ARCHIVE_AUTHOR_ID=557398
ARCHIVE_AUTHOR_NOTIFY=false
```

修改后重新部署：

```bash
docker compose up -d --build
```

## 工作原理

1. 每隔 N 分钟运行一次监控脚本
2. 爬取关注帖子的最新页面（通过 NGA `?lite=js` API）
3. 过滤出关注用户的发言
4. 与本地记录对比，找出新发言
5. 通过飞书 Webhook 推送新发言内容
6. 更新本地记录（JSON 文件，存储在 `data/` 目录）
