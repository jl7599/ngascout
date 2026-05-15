# NGA Watcher 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Python cron 脚本，监控 NGA 论坛指定帖子中指定用户的发言，通过飞书 Webhook 推送通知。

**Architecture:** 模块化单进程脚本：config 解析 .env → nga 通过 lite=js API 爬取帖子 → store 用 JSON 文件去重 → notify 推飞书。main.py 编排全流程，Docker 容器内 crontab 调度。

**Tech Stack:** Python 3.12+, httpx, python-dotenv, pytest, ruff, uv, Docker

---

## 文件结构

```
dashidai/
├── src/
│   ├── __init__.py        # 空
│   ├── main.py            # 入口编排
│   ├── config.py          # .env 配置解析
│   ├── nga.py             # NGA API 请求与解析
│   ├── store.py           # JSON 文件存储/去重
│   └── notify.py          # 飞书机器人推送
├── tests/
│   ├── __init__.py        # 空
│   ├── test_config.py
│   ├── test_store.py
│   ├── test_nga.py
│   ├── test_notify.py
│   └── test_main.py
├── scripts/
│   └── entrypoint.sh      # Docker 入口，生成 crontab
├── data/                  # 运行时数据（.gitignore）
├── pyproject.toml
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

### Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `.pre-commit-config.yaml`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: 初始化 git 和项目目录**

```bash
cd /Users/jialei/Desktop/dashidai
git init
mkdir -p src tests scripts data
touch src/__init__.py tests/__init__.py
```

- [ ] **Step 2: 创建 pyproject.toml**

```toml
[project]
name = "dashidai"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.5",
    "pre-commit>=3.7",
]

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: 创建 .gitignore**

```
__pycache__/
*.py[cod]
*.egg-info/
dist/
.venv/
.env
data/
.vscode/
.idea/
.DS_Store
```

- [ ] **Step 4: 创建 .env.example**

```
# Watch list: tid1,uid1,uid2|tid2,uid3
# If no uid after tid, follows thread OP
WATCH=45905087,557398

# Feishu bot webhook URL
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your-token-here

# NGA login cookie
NGA_COOKIE=ngacn0comUserInfo=...;ngaPassportCid=...

# Cron interval in minutes (default: 5)
CRON_INTERVAL=5
```

- [ ] **Step 5: 创建 .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
```

- [ ] **Step 6: 安装依赖和 pre-commit**

```bash
uv sync
uv run pre-commit install
```

- [ ] **Step 7: 验证 pytest 可运行**

```bash
uv run pytest --co
```

Expected: 收集到 0 个测试（空项目），无报错

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore .env.example .pre-commit-config.yaml src/__init__.py tests/__init__.py uv.lock
git commit -m "chore: init project scaffolding with uv, ruff, pytest, pre-commit"
```

---

### Task 2: config.py — 配置解析

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 写测试 tests/test_config.py**

```python
import os
import pytest
from src.config import WatchItem, Config, parse_watch_list, load_config


class TestParseWatchList:
    def test_single_tid_with_users(self):
        result = parse_watch_list("45905087,557398,123456")
        assert result == [WatchItem(tid=45905087, uids=[557398, 123456])]

    def test_multiple_tids(self):
        result = parse_watch_list("45905087,557398|45974302|46272205,38906013")
        assert result == [
            WatchItem(tid=45905087, uids=[557398]),
            WatchItem(tid=45974302, uids=[]),
            WatchItem(tid=46272205, uids=[38906013]),
        ]

    def test_empty_users_means_op(self):
        result = parse_watch_list("45905087")
        assert result == [WatchItem(tid=45905087, uids=[])]

    def test_empty_string(self):
        assert parse_watch_list("") == []

    def test_whitespace_handling(self):
        result = parse_watch_list(" 45905087 , 557398 | 45974302 ")
        assert result == [
            WatchItem(tid=45905087, uids=[557398]),
            WatchItem(tid=45974302, uids=[]),
        ]


class TestLoadConfig:
    def test_success(self, monkeypatch):
        monkeypatch.setenv("WATCH", "45905087,557398")
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setenv("NGA_COOKIE", "test_cookie")
        monkeypatch.setenv("CRON_INTERVAL", "10")
        config = load_config()
        assert config.watch_list == [WatchItem(tid=45905087, uids=[557398])]
        assert config.feishu_webhook_url == "https://example.com/hook"
        assert config.nga_cookie == "test_cookie"
        assert config.cron_interval == 10

    def test_default_cron_interval(self, monkeypatch):
        monkeypatch.setenv("WATCH", "")
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setenv("NGA_COOKIE", "test_cookie")
        config = load_config()
        assert config.cron_interval == 5

    def test_missing_feishu_url(self, monkeypatch):
        monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
        monkeypatch.setenv("NGA_COOKIE", "test_cookie")
        with pytest.raises(ValueError, match="FEISHU_WEBHOOK_URL"):
            load_config()

    def test_missing_nga_cookie(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.delenv("NGA_COOKIE", raising=False)
        with pytest.raises(ValueError, match="NGA_COOKIE"):
            load_config()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL — `ImportError: cannot import name 'WatchItem' from 'src.config'`

- [ ] **Step 3: 实现 src/config.py**

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config module with .env parsing and watch list"
```

---

### Task 3: store.py — 本地存储与去重

**Files:**
- Create: `src/store.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: 写测试 tests/test_store.py**

```python
import json
from pathlib import Path

from src.store import PostRecord, StoreData, load, save, filter_new


class TestSaveAndLoad:
    def test_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        data = StoreData(
            last_page=42,
            username="testuser",
            posts={"123": PostRecord(content="hello", postdate="2025-01-01 12:00", lou=5)},
        )
        save(1, 100, data)
        loaded = load(1, 100)
        assert loaded == data

    def test_load_nonexistent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        assert load(999, 999) is None

    def test_creates_subdirectory(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        data = StoreData(last_page=1, username="u", posts={})
        save(45905087, 557398, data)
        assert (tmp_path / "45905087" / "557398.json").exists()


class TestFilterNew:
    def test_all_new_when_no_store(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)

        class Reply:
            def __init__(self, pid):
                self.pid = pid

        replies = [Reply(1), Reply(2), Reply(3)]
        result = filter_new(None, replies)
        assert len(result) == 3

    def test_filters_existing_pids(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        stored = StoreData(
            last_page=10,
            username="u",
            posts={"1": PostRecord(content="a", postdate="d", lou=1)},
        )

        class Reply:
            def __init__(self, pid):
                self.pid = pid

        replies = [Reply(1), Reply(2), Reply(3)]
        result = filter_new(stored, replies)
        assert len(result) == 2
        assert [r.pid for r in result] == [2, 3]

    def test_none_new(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        stored = StoreData(
            last_page=10,
            username="u",
            posts={
                "1": PostRecord(content="a", postdate="d", lou=1),
                "2": PostRecord(content="b", postdate="d", lou=2),
            },
        )

        class Reply:
            def __init__(self, pid):
                self.pid = pid

        replies = [Reply(1), Reply(2)]
        result = filter_new(stored, replies)
        assert result == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_store.py -v
```

Expected: FAIL — `ImportError: cannot import name 'PostRecord' from 'src.store'`

- [ ] **Step 3: 实现 src/store.py**

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PostRecord:
    content: str
    postdate: str
    lou: int


@dataclass
class StoreData:
    last_page: int  # last seen floor number (lou)
    username: str
    posts: dict[str, PostRecord] = field(default_factory=dict)


DATA_DIR = Path("data")


def _path(tid: int, uid: int) -> Path:
    return DATA_DIR / str(tid) / f"{uid}.json"


def load(tid: int, uid: int) -> StoreData | None:
    p = _path(tid, uid)
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    posts = {}
    for pid, pr in raw.get("posts", {}).items():
        posts[pid] = PostRecord(**pr)
    return StoreData(
        last_page=raw.get("last_page", 0),
        username=raw.get("username", ""),
        posts=posts,
    )


def save(tid: int, uid: int, data: StoreData) -> None:
    p = _path(tid, uid)
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "last_page": data.last_page,
        "username": data.username,
        "posts": {
            pid: {"content": pr.content, "postdate": pr.postdate, "lou": pr.lou}
            for pid, pr in data.posts.items()
        },
    }
    p.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def filter_new(stored: StoreData | None, replies: list) -> list:
    if stored is None:
        return list(replies)
    return [r for r in replies if str(r.pid) not in stored.posts]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_store.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/store.py tests/test_store.py
git commit -m "feat: add store module with JSON file storage and dedup"
```

---

### Task 4: nga.py — NGA API 交互

**Files:**
- Create: `src/nga.py`
- Create: `tests/test_nga.py`

- [ ] **Step 1: 写测试 tests/test_nga.py**

```python
import json
from unittest.mock import MagicMock, patch

import pytest

from src.nga import (
    NgaReply,
    NgaResponse,
    NgaThreadInfo,
    NgaUser,
    fetch_thread,
    page_for_lou,
)

MOCK_NGA_JSON = (
    '{"data":{"__CU":{"uid":42394984},"__GLOBAL":{},'
    '"__U":{"557398":{"uid":557398,"username":"海伯利安之歌"},'
    '"557399":{"uid":557399,"username":"测试用户"}},'
    '"__R":{"0":{"pid":0,"authorid":557398,"postdate":"2025-12-31 15:41",'
    '"postdatetimestamp":1767166910,"lou":0,"content":"主楼内容"},'
    '"1":{"pid":853070904,"authorid":557399,"postdate":"2025-12-31 15:42",'
    '"postdatetimestamp":1767166950,"lou":1,"content":"回复内容"}},'
    '"__T":{"tid":45905087,"subject":"测试帖子","authorid":557398,"replies":100},'
    '"__ROWS":100,"__PAGE":5}}'
)


class TestPageForLou:
    def test_first_page(self):
        assert page_for_lou(0) == 1

    def test_middle(self):
        assert page_for_lou(20) == 2
        assert page_for_lou(21) == 2

    def test_high_lou(self):
        assert page_for_lou(100) == 6


class TestFetchThread:
    def test_parses_response(self):
        mock_resp = MagicMock()
        mock_resp.content = (
            "window.script_muti_get_var_store=" + MOCK_NGA_JSON
        ).encode("gbk")
        mock_resp.raise_for_status = MagicMock()

        with patch("src.nga.httpx.get", return_value=mock_resp):
            result = fetch_thread(45905087, 1, "test_cookie")

        assert isinstance(result, NgaResponse)
        assert result.thread_info == NgaThreadInfo(
            tid=45905087, subject="测试帖子", authorid=557398, replies=100
        )
        assert result.users[557398] == NgaUser(uid=557398, username="海伯利安之歌")
        assert result.users[557399] == NgaUser(uid=557399, username="测试用户")
        assert len(result.replies) == 2
        assert result.replies[0] == NgaReply(
            pid=0,
            authorid=557398,
            postdate="2025-12-31 15:41",
            postdatetimestamp=1767166910,
            lou=0,
            content="主楼内容",
        )
        assert result.current_page == 5
        assert result.total_pages == 5

    def test_replies_sorted_by_lou(self):
        # Reverse the order in __R to test sorting
        reversed_json = (
            '{"data":{"__CU":{},"__GLOBAL":{},'
            '"__U":{"1":{"uid":1,"username":"a"}},'
            '"__R":{"0":{"pid":2,"authorid":1,"postdate":"d2",'
            '"postdatetimestamp":2,"lou":1,"content":"second"},'
            '"1":{"pid":1,"authorid":1,"postdate":"d1",'
            '"postdatetimestamp":1,"lou":0,"content":"first"}},'
            '"__T":{"tid":1,"subject":"s","authorid":1,"replies":1},'
            '"__ROWS":1,"__PAGE":1}}'
        )
        mock_resp = MagicMock()
        mock_resp.content = (
            "window.script_muti_get_var_store=" + reversed_json
        ).encode("gbk")
        mock_resp.raise_for_status = MagicMock()

        with patch("src.nga.httpx.get", return_value=mock_resp):
            result = fetch_thread(1, 1, "cookie")

        assert result.replies[0].lou == 0
        assert result.replies[1].lou == 1

    def test_http_error_raises(self):
        import httpx

        with patch(
            "src.nga.httpx.get", side_effect=httpx.HTTPStatusError(
                "error", request=MagicMock(), response=MagicMock(status_code=403)
            )
        ):
            with pytest.raises(httpx.HTTPStatusError):
                fetch_thread(1, 1, "cookie")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_nga.py -v
```

Expected: FAIL — `ImportError: cannot import name 'NgaReply' from 'src.nga'`

- [ ] **Step 3: 实现 src/nga.py**

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_nga.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/nga.py tests/test_nga.py
git commit -m "feat: add NGA API module with lite=js parsing"
```

---

### Task 5: notify.py — 飞书推送

**Files:**
- Create: `src/notify.py`
- Create: `tests/test_notify.py`

- [ ] **Step 1: 写测试 tests/test_notify.py**

```python
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.notify import format_message, send_webhook, strip_html


class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<b>hello</b>") == "hello"

    def test_br_to_newline(self):
        assert strip_html("line1<br/>line2") == "line1\nline2"

    def test_br_without_slash(self):
        assert strip_html("line1<br>line2") == "line1\nline2"

    def test_nested_tags(self):
        assert strip_html("<div><p>text</p></div>") == "text"


class TestFormatMessage:
    def test_single_reply(self):
        class Reply:
            def __init__(self, content, postdate, lou):
                self.content = content
                self.postdate = postdate
                self.lou = lou

        replies = [Reply("hello world", "2025-12-31 15:41", 5)]
        msg = format_message("测试帖子", "测试用户", replies)
        assert msg["msg_type"] == "text"
        text = msg["content"]["text"]
        assert "测试帖子" in text
        assert "测试用户" in text
        assert "2025-12-31 15:41" in text
        assert "5楼" in text
        assert "hello world" in text

    def test_multiple_replies(self):
        class Reply:
            def __init__(self, content, postdate, lou):
                self.content = content
                self.postdate = postdate
                self.lou = lou

        replies = [
            Reply("first", "2025-12-31 15:41", 5),
            Reply("second", "2025-12-31 15:42", 10),
        ]
        msg = format_message("帖子", "用户", replies)
        text = msg["content"]["text"]
        assert "5楼" in text
        assert "10楼" in text
        assert "first" in text
        assert "second" in text


class TestSendWebhook:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        with patch("src.notify.httpx.post", return_value=mock_resp):
            assert send_webhook("https://example.com/hook", {"msg_type": "text"}) is True

    def test_failure_returns_false(self):
        with patch(
            "src.notify.httpx.post",
            side_effect=httpx.HTTPStatusError(
                "err", request=MagicMock(), response=MagicMock(status_code=500)
            ),
        ):
            assert send_webhook("https://example.com/hook", {"msg_type": "text"}) is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_notify.py -v
```

Expected: FAIL — `ImportError: cannot import name 'strip_html' from 'src.notify'`

- [ ] **Step 3: 实现 src/notify.py**

```python
from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def format_message(
    thread_subject: str, username: str, replies: list
) -> dict:
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_notify.py -v
```

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/notify.py tests/test_notify.py
git commit -m "feat: add Feishu webhook notification module"
```

---

### Task 6: main.py — 入口编排

**Files:**
- Create: `src/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: 写测试 tests/test_main.py**

```python
from unittest.mock import MagicMock, patch, call

import pytest

from src.config import Config, WatchItem
from src.main import process_thread
from src.nga import NgaReply, NgaResponse, NgaThreadInfo, NgaUser
from src.store import PostRecord, StoreData


def _make_config(**overrides):
    defaults = dict(
        watch_list=[WatchItem(tid=45905087, uids=[557398])],
        feishu_webhook_url="https://example.com/hook",
        nga_cookie="test_cookie",
        cron_interval=5,
    )
    defaults.update(overrides)
    return Config(**defaults)


def _make_response(replies=None, current_page=5, total_pages=5):
    if replies is None:
        replies = [
            NgaReply(
                pid=123, authorid=557398,
                postdate="2025-12-31 15:41",
                postdatetimestamp=1767166910, lou=50,
                content="hello",
            ),
        ]
    return NgaResponse(
        thread_info=NgaThreadInfo(
            tid=45905087, subject="测试帖子",
            authorid=557398, replies=100,
        ),
        users={557398: NgaUser(uid=557398, username="测试用户")},
        replies=replies,
        total_pages=total_pages,
        current_page=current_page,
    )


class TestProcessThread:
    def test_first_time_sends_all(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config()
        item = WatchItem(tid=45905087, uids=[557398])

        with patch("src.main.fetch_thread", return_value=_make_response()), \
             patch("src.main.send_webhook", return_value=True):
            process_thread(config, item)

        stored = __import__("src.store", fromlist=["load"]).load(45905087, 557398)
        assert stored is not None
        assert "123" in stored.posts
        assert stored.last_page == 50

    def test_skips_already_seen(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config()
        item = WatchItem(tid=45905087, uids=[557398])

        # Pre-populate store with the same reply
        __import__("src.store", fromlist=["save"]).save(
            45905087, 557398,
            StoreData(
                last_page=50, username="测试用户",
                posts={"123": PostRecord(content="hello", postdate="2025-12-31 15:41", lou=50)},
            ),
        )

        with patch("src.main.fetch_thread", return_value=_make_response()), \
             patch("src.main.send_webhook") as mock_send:
            process_thread(config, item)
            mock_send.assert_not_called()

    def test_default_op_when_no_uids(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config(watch_list=[WatchItem(tid=45905087, uids=[])])
        item = WatchItem(tid=45905087, uids=[])

        with patch("src.main.fetch_thread", return_value=_make_response()), \
             patch("src.main.send_webhook", return_value=True):
            process_thread(config, item)

        stored = __import__("src.store", fromlist=["load"]).load(45905087, 557398)
        assert stored is not None

    def test_fetch_failure_skips_thread(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config()
        item = WatchItem(tid=45905087, uids=[557398])

        with patch("src.main.fetch_thread", side_effect=Exception("network error")):
            # Should not raise
            process_thread(config, item)

    def test_send_failure_does_not_save(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config()
        item = WatchItem(tid=45905087, uids=[557398])

        with patch("src.main.fetch_thread", return_value=_make_response()), \
             patch("src.main.send_webhook", return_value=False):
            process_thread(config, item)

        # Store should NOT be updated when send fails
        stored = __import__("src.store", fromlist=["load"]).load(45905087, 557398)
        assert stored is None

    def test_fetches_intermediate_pages(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config()
        item = WatchItem(tid=45905087, uids=[557398])

        # Pre-populate: user last seen at lou=20 (page 2)
        __import__("src.store", fromlist=["save"]).save(
            45905087, 557398,
            StoreData(last_page=20, username="测试用户", posts={}),
        )

        page2_response = _make_response(
            replies=[
                NgaReply(pid=200, authorid=557398, postdate="d1",
                         postdatetimestamp=1, lou=25, content="page2"),
            ],
            current_page=2, total_pages=5,
        )
        latest_response = _make_response(
            replies=[
                NgaReply(pid=300, authorid=557398, postdate="d2",
                         postdatetimestamp=2, lou=50, content="latest"),
            ],
            current_page=5, total_pages=5,
        )

        def mock_fetch(tid, page, cookie):
            if page == 2:
                return page2_response
            return latest_response

        with patch("src.main.fetch_thread", side_effect=mock_fetch), \
             patch("src.main.send_webhook", return_value=True):
            process_thread(config, item)

        stored = __import__("src.store", fromlist=["load"]).load(45905087, 557398)
        assert stored is not None
        assert "200" in stored.posts
        assert "300" in stored.posts
        assert stored.last_page == 50
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_main.py -v
```

Expected: FAIL — `ImportError: cannot import name 'process_thread' from 'src.main'`

- [ ] **Step 3: 实现 src/main.py**

```python
from __future__ import annotations

import logging

from src.config import Config, WatchItem
from src.nga import NgaUser, NgaReply, fetch_thread, page_for_lou
from src.notify import format_message, send_webhook
from src.store import PostRecord, StoreData, load, save

logger = logging.getLogger(__name__)


def process_thread(config: Config, item: WatchItem) -> None:
    try:
        latest_resp = fetch_thread(item.tid, "e", config.nga_cookie)
    except Exception as e:
        logger.error("Failed to fetch tid=%d: %s", item.tid, e)
        return

    uids = item.uids or [latest_resp.thread_info.authorid]

    # Determine earliest page needed across all users
    earliest_page = latest_resp.current_page
    for uid in uids:
        stored = load(item.tid, uid)
        if stored is not None:
            sp = page_for_lou(stored.last_page)
            earliest_page = min(earliest_page, sp)

    # Fetch all pages from earliest to current
    all_replies: list[NgaReply] = []
    for p in range(earliest_page, latest_resp.current_page):
        try:
            r = fetch_thread(item.tid, p, config.nga_cookie)
            all_replies.extend(r.replies)
        except Exception as e:
            logger.error("Failed to fetch tid=%d page=%d: %s", item.tid, p, e)
    all_replies.extend(latest_resp.replies)
    all_replies.sort(key=lambda x: x.lou)

    # Process each user
    for uid in uids:
        stored = load(item.tid, uid)
        user_replies = [r for r in all_replies if r.authorid == uid]

        if stored is None:
            # First time: only send replies from latest page
            new_replies = [r for r in latest_resp.replies if r.authorid == uid]
        else:
            new_replies = [r for r in user_replies if str(r.pid) not in stored.posts]

        if not new_replies:
            continue

        username_obj = latest_resp.users.get(uid)
        username_str = username_obj.username if username_obj else str(uid)

        msg = format_message(
            latest_resp.thread_info.subject, username_str, new_replies
        )
        success = send_webhook(config.feishu_webhook_url, msg)

        if success:
            if stored is None:
                stored = StoreData(last_page=0, username=username_str, posts={})
            for r in new_replies:
                stored.posts[str(r.pid)] = PostRecord(
                    content=r.content, postdate=r.postdate, lou=r.lou
                )
            stored.last_page = max(stored.last_page, max(r.lou for r in new_replies))
            stored.username = username_str
            save(item.tid, uid, stored)
            logger.info(
                "Sent %d new replies for tid=%d uid=%d",
                len(new_replies), item.tid, uid,
            )
        else:
            logger.warning(
                "Feishu send failed, will retry next run: tid=%d uid=%d",
                item.tid, uid,
            )


def main() -> None:
    from src.config import load_config

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    config = load_config()
    for item in config.watch_list:
        process_thread(config, item)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_main.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: 运行全部测试**

```bash
uv run pytest -v
```

Expected: 所有测试 PASS

- [ ] **Step 6: Commit**

```bash
git add src/main.py tests/test_main.py
git commit -m "feat: add main orchestration module with process_thread"
```

---

### Task 7: Docker 部署

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `scripts/entrypoint.sh`

- [ ] **Step 1: 创建 scripts/entrypoint.sh**

```bash
#!/bin/bash
set -e
INTERVAL=${CRON_INTERVAL:-5}
echo "*/$INTERVAL * * * * cd /app && uv run python -m src.main 2>&1" > /etc/cron.d/dashidai
chmod 0644 /etc/cron.d/dashidai
crontab /etc/cron.d/dashidai
echo "Cron job set up with interval: */$INTERVAL minutes"
exec crond -f -l 2
```

- [ ] **Step 2: 设置执行权限**

```bash
chmod +x scripts/entrypoint.sh
```

- [ ] **Step 3: 创建 Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh

RUN mkdir -p data

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
```

- [ ] **Step 4: 创建 docker-compose.yml**

```yaml
services:
  watcher:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

- [ ] **Step 5: 构建 Docker 镜像验证**

```bash
docker compose build
```

Expected: 构建成功

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml scripts/entrypoint.sh
git commit -m "feat: add Docker deployment with crontab scheduling"
```

---

### Task 8: README 和 .env 验证

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建 README.md**

```markdown
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
```

- [ ] **Step 2: 创建 .env 文件用于本地测试**

```bash
cp .env.example .env
```

然后编辑 `.env` 填写真实配置

- [ ] **Step 3: 端到端验证**

```bash
uv run python -m src.main
```

Expected: 如果配置正确，应该能爬取帖子并推送通知（或输出日志显示未发现新发言）

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup and usage instructions"
```
