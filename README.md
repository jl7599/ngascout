# dashidai

监控 NGA 论坛指定帖子中指定用户的发言，通过飞书机器人推送通知。

## 配置

复制 `.env.example` 为 `.env`，填写以下配置：

| 变量 | 说明 | 示例 |
|------|------|------|
| `WATCH` | 关注列表，格式：`tid,uid1,uid2\|tid2,uid3` | `45905087,557398\|45974302` |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook 地址 | `https://open.feishu.cn/...` |
| `NGA_COOKIE` | NGA 登录 Cookie | `ngacn0comUserInfo=...` |
| `CRON_INTERVAL` | 检查间隔（分钟，默认 5） | `5` |

- `WATCH` 中帖子间用 `|` 分隔，帖子内用户 uid 用 `,` 分隔
- 如果帖子后不指定 uid，默认关注楼主

## 本地运行

```bash
uv sync
uv run python -m src.main
```

## 归档某用户所有文章发言

按用户 id 抓取该用户发表过的主题，并遍历每个主题从第一页到最后一页的所有楼层，只保留该用户自己的发言：

```bash
uv run python -m src.archive_author --authorid 21321600
```

默认输出到：

```text
data/authors/{用户id}_{用户名}/{主题id}_{文章标题}.json
```

多次执行会按 `pid` 去重；如果同一楼层内容变化，会更新 JSON 内的最新内容。

默认不会发送飞书。需要推送本次新增或变更内容时，显式加 `--notify`：

```bash
uv run python -m src.archive_author --authorid 21321600 --notify
```

调试时可以限制主题数量：

```bash
uv run python -m src.archive_author --authorid 21321600 --limit-threads 5
```

## 测试

```bash
uv run pytest -v
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

## 工作原理

1. 每隔 N 分钟运行一次脚本
2. 爬取关注帖子的最新页面（通过 NGA `?lite=js` API）
3. 过滤出关注用户的发言
4. 与本地记录对比，找出新发言
5. 通过飞书 Webhook 推送新发言内容
6. 更新本地记录（JSON 文件，存储在 `data/` 目录）
