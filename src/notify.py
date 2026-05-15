from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def format_message(thread_subject: str, username: str, replies: list) -> dict:
    parts = []
    for r in replies:
        content = strip_html(r.content)
        parts.append(f"时间：{r.postdate} | {r.lou}楼\n内容：{content}")
    body = "\n\n".join(parts)
    text = f"【{thread_subject}】{username} 新发言\n{body}"
    return {"msg_type": "text", "content": {"text": text}}


def send_webhook(url: str, message: dict) -> bool:
    try:
        resp = httpx.post(url, json=message, timeout=10)
        resp.raise_for_status()
        return True
    except httpx.HTTPError as e:
        logger.error("Feishu webhook failed: %s", e)
        return False
