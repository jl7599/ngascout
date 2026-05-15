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


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


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
