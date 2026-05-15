# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NGA 论坛帖子监控 + 飞书推送工具。定时爬取 NGA 指定帖子中指定用户的发言，通过飞书 Webhook 推送新发言通知。

## Commands

```bash
uv sync                    # 安装依赖
uv run pytest -v           # 运行测试
uv run pytest tests/test_config.py -v  # 运行单个模块测试
uv run python -m src.main  # 本地运行
uv run ruff check .        # lint
uv run ruff format .       # 格式化
docker compose build       # 构建 Docker 镜像
docker compose up -d       # 启动服务
```

## Architecture

```
src/main.py     → 入口编排，process_thread() 串联全流程
src/config.py   → 解析 .env（WATCH 列表、飞书 URL、NGA Cookie）
src/nga.py      → 请求 NGA ?lite=js API，GBK→JSON 解析
src/store.py    → JSON 文件存储（data/{tid}/{uid}.json），pid 去重
src/notify.py   → 飞书 Webhook 推送，HTML 清理
```

**核心流程**: 加载配置 → 爬最新页(及中间页) → 过滤关注用户 → pid 去重 → 飞书推送 → 更新本地记录

**关键设计**:
- `last_page` 存储楼层号(lou)，通过 `page_for_lou(lou) = lou // 20 + 1` 转换为页码
- 首次运行只推送最新页内容，后续从 `last_page` 对应页往后爬
- 推送失败不保存记录，下次重试
- `DATA_DIR` 使用 `Path(__file__).resolve().parent.parent / "data"` 确保路径正确

## Config Format

`WATCH=45905087,557398|45974302` — 帖子间 `|` 分隔，用户 uid 间 `,` 分隔，无 uid 则关注楼主
