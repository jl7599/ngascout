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
