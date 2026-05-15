# NGA 帖子监控 + 飞书推送 设计文档

## 概述

定时监控 NGA 论坛指定帖子中指定用户的发言，发现新发言后通过飞书机器人 Webhook 推送到群聊。

## 核心流程

每次 cron 触发 `main.py`：

1. 加载 `.env` 配置，解析 WATCH 列表
2. 遍历每个关注帖子：
   a. 读取本地记录的 `last_page`
   b. 从 `last_page` 所在页往后爬到最新页（NGA `?lite=js` API）
   c. 过滤出关注用户的发言
   d. 对比本地 JSON 记录去重（用 `pid` 做唯一标识）
   e. 有新发言 → 飞书推送，更新本地 JSON
3. 首次执行（无本地记录）→ 爬最新页，推送所有关注用户发言

## 配置格式

`.env` 文件：

```
WATCH=45905087,557398|45974302|46272205,38906013,64226018
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
NGA_COOKIE=ngacn0comUserInfo=...;ngaPassportCid=...
CRON_INTERVAL=5
```

- `WATCH`：帖子间用 `|` 分隔，帖子内用户 uid 用 `,` 分隔
- 如果帖子后没有 uid → 默认关注楼主（首次爬取时从 `__T.authorid` 获取）
- `CRON_INTERVAL`：分钟，默认 5

## 模块设计

### config.py — 配置解析

- `python-dotenv` 加载 `.env`
- `parse_watch_list(watch_str) -> list[WatchItem]`，`WatchItem = (tid: int, uids: list[int])`
- 空 uids 列表表示关注楼主，首次爬取时填充
- 读取 `FEISHU_WEBHOOK_URL`、`NGA_COOKIE`、`CRON_INTERVAL`

### nga.py — NGA API 交互

- `fetch_thread(tid, page, cookie) -> NgaResponse`
  - 请求 `https://bbs.nga.cn/read.php?tid={tid}&page={page}&lite=js`
  - 响应 GBK 编码，解析为 JSON
  - 返回 `NgaResponse(thread_info, users, replies, total_pages, current_page)`
- `page_for_lou(lou) -> int`：`lou // 20 + 1`
- 回复结构：`authorid`, `postdate`, `postdatetimestamp`, `lou`, `pid`, `content`
- 用户结构：`uid`, `username`
- 帖子结构：`tid`, `subject`, `authorid`, `replies`

### store.py — 本地存储与去重

- 存储路径：`data/{tid}/{uid}.json`
- 文件结构：
  ```json
  {
    "last_page": 100,
    "username": "海伯利安之歌",
    "posts": {
      "pid123": {"content": "...", "postdate": "2025-12-31 15:41", "lou": 50}
    }
  }
  ```
- `load(tid, uid) -> StoreData | None`
- `save(tid, uid, data)`
- `filter_new(tid, uid, replies) -> list[Reply]`：返回本地不存在的回复

### notify.py — 飞书推送

- 飞书 Webhook POST JSON
- 同一帖子同一用户的多条新发言合并为一条富文本消息
- 消息格式：
  ```
  【帖子名】用户名 新发言
  时间：2025-12-31 15:41 | N楼
  内容：发言内容（纯文本，去除 HTML 标签）
  ```
- 发送失败时记录错误日志，不中断流程

### main.py — 入口编排

- 被 crontab 调用
- 流程：
  1. `config` 加载配置
  2. 遍历 watch 列表
  3. 每个 tid：爬取 → 过滤 → 去重 → 推送 → 存储
  4. 日志输出到 stdout（docker logs 可查看）
- 处理楼主默认关注的逻辑：空 uids → 从 `__T.authorid` 获取

## 项目结构

```
dashidai/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── nga.py
│   ├── store.py
│   └── notify.py
├── tests/
│   ├── test_config.py
│   ├── test_nga.py
│   ├── test_store.py
│   └── test_notify.py
├── data/              # 运行时数据（.gitignore）
├── pyproject.toml
├── .env.example
├── .pre-commit-config.yaml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 技术选型

- **Python 3.12+**
- **HTTP 请求**：`httpx`（比 requests 更现代，支持 async 但本项目用同步即可）
- **配置**：`python-dotenv`
- **格式化/Lint**：`ruff`（行宽 88）
- **测试**：`pytest`
- **pre-commit**：ruff + pytest
- **调度**：Docker 容器内 crontab
- **包管理**：uv

## 爬取策略

- 记录每个帖子的 `last_page`（最后看到的楼层号）
- 爬取时计算 `start_page = last_page // 20 + 1`，从该页爬到最新页
- 首次执行：爬最新页（`page=e`）
- NGA `?lite=js` API 返回结构化 JSON，避免解析 HTML
- 每页 20 条回复，通常只需爬 1-2 页

## Docker 部署

- `Dockerfile`：Python 基础镜像，安装 uv + 依赖，复制代码
- `docker-compose.yml`：挂载 `.env` 和 `data/` 目录，crontab 定时执行 `python -m src.main`
- 容器内用 crontab 调度，间隔由 `CRON_INTERVAL` 控制

## 错误处理

- NGA 请求失败 → 记录日志，跳过该帖子，继续处理其他帖子
- 飞书推送失败 → 记录日志，不中断流程（下次仍会尝试推送同一内容）
- 配置缺失 → 启动时报错退出
- 本地存储读写失败 → 记录日志，跳过该帖子

## 开发规范

- TDD：先写测试再写实现
- pre-commit：ruff 格式化 + lint
- 所有模块函数式设计，便于测试时 mock 外部依赖
