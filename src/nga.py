from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

NGA_BASE_URL = "https://bbs.nga.cn"


@dataclass
class NgaReply:
    pid: int
    authorid: int
    postdate: str
    postdatetimestamp: int
    lou: int
    content: str


@dataclass
class NgaUser:
    uid: int
    username: str


@dataclass
class NgaThreadInfo:
    tid: int
    subject: str
    authorid: int
    replies: int


@dataclass
class NgaResponse:
    thread_info: NgaThreadInfo
    users: dict[int, NgaUser]
    replies: list[NgaReply]
    total_pages: int
    current_page: int


def page_for_lou(lou: int) -> int:
    return lou // 20 + 1


def fetch_thread(tid: int, page: int | str, cookie: str) -> NgaResponse:
    url = f"{NGA_BASE_URL}/read.php"
    params = {"tid": tid, "page": page, "lite": "js"}
    headers = {
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    resp = httpx.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()

    raw = resp.content.decode("gbk", errors="replace")
    json_str = raw.replace("window.script_muti_get_var_store=", "")
    json_str = re.sub(r"[\x00-\x1f]", " ", json_str)
    data = json.loads(json_str)["data"]

    t = data["__T"]
    thread_info = NgaThreadInfo(
        tid=t["tid"],
        subject=t["subject"],
        authorid=t["authorid"],
        replies=t["replies"],
    )

    users = {}
    for uid_str, u in data.get("__U", {}).items():
        uid = int(uid_str)
        users[uid] = NgaUser(uid=uid, username=u["username"])

    replies = []
    for rid, r in data.get("__R", {}).items():
        replies.append(
            NgaReply(
                pid=r["pid"],
                authorid=r["authorid"],
                postdate=r["postdate"],
                postdatetimestamp=r["postdatetimestamp"],
                lou=r["lou"],
                content=r["content"],
            )
        )
    replies.sort(key=lambda x: x.lou)

    total_rows = data.get("__ROWS", 0)
    total_pages = (total_rows + 19) // 20 if total_rows else 1
    current_page = data.get("__PAGE", 1)

    return NgaResponse(
        thread_info=thread_info,
        users=users,
        replies=replies,
        total_pages=total_pages,
        current_page=current_page,
    )
