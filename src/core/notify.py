from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)


NGA_IMG_BASE = "https://img.nga.178.com/attachments/"


def _clean_nga(text: str) -> str:
    # Save [img] tags as placeholders before catch-all cleanup
    images: list[str] = []

    def replace_img(m):
        url = m.group(1).strip()
        if url.startswith("./"):
            url = NGA_IMG_BASE + url[2:]
        idx = len(images)
        images.append(f"[查看图片]({url})")
        return f"\x00IMG{idx}\x00"

    text = re.sub(r"\[img\](.*?)\[/img\]", replace_img, text, flags=re.DOTALL)

    text = re.sub(r"\[pid=\d+,\d+,\d+\]Reply\[/pid\]", "", text)
    text = re.sub(r"\[uid=\d+\](.*?)\[/uid\]", r"\1", text)
    text = re.sub(r"\[b\](.*?)\[/b\]", r"\1", text)
    text = re.sub(r"\[s:\w+:[^\]]+\]", "", text)
    text = re.sub(r"\[/?\w+[^\]]*\]", "", text)

    for i, img in enumerate(images):
        text = text.replace(f"\x00IMG{i}\x00", img)

    return text


def _clean_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text


def strip_html(text: str) -> str:
    quotes: list[str] = []

    def save_quote(m):
        content = m.group(1)
        content = re.sub(r"Post by ", "", content)
        content = _clean_nga(content)
        content = _clean_html(content)
        content = content.strip()
        content = re.sub(r"\n{2,}", "\n", content)
        idx = len(quotes)
        quotes.append(f"<font color='grey'>{content}</font>")
        return f"\x00Q{idx}\x00\n"

    # Process quotes from inside out (handles nesting)
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\[quote\](.*?)\[/quote\]", save_quote, text, flags=re.DOTALL)

    text = _clean_nga(text)
    text = _clean_html(text)

    # Restore quotes with grey font
    for i, q in enumerate(quotes):
        text = text.replace(f"\x00Q{i}\x00", q)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_message(thread_subject: str, username: str, replies: list) -> dict:
    parts = []
    for r in replies:
        content = strip_html(r.content)
        parts.append(f"**{r.postdate} | {r.lou}楼**\n{content}")
    body = "\n\n---\n\n".join(parts)
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"【{thread_subject}】{username} 新发言",
                },
                "template": "blue",
            },
            "elements": [{"tag": "markdown", "content": body}],
        },
    }


def send_webhook(url: str, message: dict) -> bool:
    try:
        resp = httpx.post(url, json=message, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            logger.error(
                "Feishu webhook error: code=%s msg=%s",
                data.get("code"),
                data.get("msg"),
            )
            return False
        return True
    except httpx.HTTPError as e:
        logger.error("Feishu webhook failed: %s", e)
        return False
