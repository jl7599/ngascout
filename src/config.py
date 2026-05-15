from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class WatchItem:
    tid: int
    uids: list[int]


@dataclass
class Config:
    watch_list: list[WatchItem]
    feishu_webhook_url: str
    nga_cookie: str
    cron_interval: int


def parse_watch_list(watch_str: str) -> list[WatchItem]:
    if not watch_str:
        return []
    items = []
    for part in watch_str.split("|"):
        part = part.strip()
        if not part:
            continue
        segments = [s.strip() for s in part.split(",")]
        tid = int(segments[0])
        uids = [int(s) for s in segments[1:] if s]
        items.append(WatchItem(tid=tid, uids=uids))
    return items


def load_config() -> Config:
    load_dotenv()
    watch_str = os.getenv("WATCH", "")
    feishu_url = os.getenv("FEISHU_WEBHOOK_URL", "")
    nga_cookie = os.getenv("NGA_COOKIE", "")
    cron_interval = int(os.getenv("CRON_INTERVAL", "5"))
    if not feishu_url:
        raise ValueError("FEISHU_WEBHOOK_URL is required")
    if not nga_cookie:
        raise ValueError("NGA_COOKIE is required")
    return Config(
        watch_list=parse_watch_list(watch_str),
        feishu_webhook_url=feishu_url,
        nga_cookie=nga_cookie,
        cron_interval=cron_interval,
    )
