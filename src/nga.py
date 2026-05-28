from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass

import httpx

NGA_BASE_URL = "https://bbs.nga.cn"
MAX_RETRIES = 5
RETRY_BACKOFF = 5  # base seconds, exponential
REQUEST_INTERVAL = 3.0  # seconds between requests


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


@dataclass
class NgaAuthorThread:
    tid: int
    subject: str
    authorid: int
    author: str
    replies: int


@dataclass
class NgaAuthorThreadsPage:
    threads: list[NgaAuthorThread]
    total_pages: int
    current_page: int


def page_for_lou(lou: int) -> int:
    return lou // 20 + 1


def _headers(cookie: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def _request_with_retry(
    url: str, params: dict, cookie: str, timeout: int = 30
) -> httpx.Response:
    time.sleep(REQUEST_INTERVAL)
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        resp = httpx.get(url, params=params, headers=_headers(cookie), timeout=timeout)
        if resp.status_code < 500:
            resp.raise_for_status()
            return resp
        last_exc = httpx.HTTPStatusError(
            f"Server error '{resp.status_code} "
            f"{resp.reason_phrase}' for url '{resp.url}'",
            request=resp.request,
            response=resp,
        )
        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0, 2)
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]


def _decode_nga_json(content: bytes) -> dict:
    raw = content.decode("gbk", errors="replace")
    json_str = raw.replace("window.script_muti_get_var_store=", "")
    json_str = re.sub(r"[\x00-\x1f]", " ", json_str)
    return json.loads(json_str)["data"]


def fetch_thread(tid: int, page: int | str, cookie: str) -> NgaResponse:
    url = f"{NGA_BASE_URL}/read.php"
    params = {"tid": tid, "page": page, "lite": "js"}
    resp = _request_with_retry(url, params, cookie)

    data = _decode_nga_json(resp.content)

    t = data["__T"]
    thread_info = NgaThreadInfo(
        tid=t["tid"],
        subject=t["subject"],
        authorid=t["authorid"],
        replies=t["replies"],
    )

    users = {}
    for uid_str, u in data.get("__U", {}).items():
        if not uid_str.isdigit():
            continue
        uid = int(uid_str)
        users[uid] = NgaUser(uid=uid, username=u["username"])

    replies = []
    for rid, r in data.get("__R", {}).items():
        if not rid.isdigit():
            continue
        replies.append(
            NgaReply(
                pid=r["pid"],
                authorid=r["authorid"],
                postdate=r["postdate"],
                postdatetimestamp=r.get("postdatetimestamp", 0),
                lou=r["lou"],
                content=r.get("content", ""),
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


def fetch_author_threads_page(
    authorid: int, page: int, cookie: str
) -> NgaAuthorThreadsPage:
    url = f"{NGA_BASE_URL}/thread.php"
    params = {"authorid": authorid, "page": page, "lite": "js"}
    resp = _request_with_retry(url, params, cookie)

    data = _decode_nga_json(resp.content)
    users = data.get("__U", {})
    threads = []
    for tid_str, t in data.get("__T", {}).items():
        if not str(tid_str).isdigit():
            continue
        tid = int(t.get("tid", tid_str))
        thread_authorid = int(t.get("authorid", authorid))
        user = users.get(str(thread_authorid), {})
        author = t.get("author") or user.get("username") or str(thread_authorid)
        threads.append(
            NgaAuthorThread(
                tid=tid,
                subject=t.get("subject", ""),
                authorid=thread_authorid,
                author=author,
                replies=int(t.get("replies", 0)),
            )
        )
    total_rows = int(data.get("__ROWS", len(threads)))
    total_pages = (total_rows + 34) // 35 if total_rows else 1
    current_page = int(data.get("__PAGE", page))
    return NgaAuthorThreadsPage(
        threads=threads,
        total_pages=total_pages,
        current_page=current_page,
    )
