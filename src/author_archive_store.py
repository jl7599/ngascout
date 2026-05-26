from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class ArchivedPost:
    pid: int
    lou: int
    postdate: str
    postdatetimestamp: int
    content_raw: str
    content_text: str

    @property
    def content(self) -> str:
        return self.content_raw


@dataclass
class AuthorArchive:
    authorid: int
    username: str
    tid: int
    subject: str
    thread_url: str
    posts: dict[str, ArchivedPost] = field(default_factory=dict)
    updated_at: str = ""


def safe_filename(value: str, max_length: int = 120) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" ._")
    value = re.sub(r"_+", "_", value)
    if not value:
        return "untitled"
    return value[:max_length].rstrip(" ._")


def archive_path(output_dir: Path, archive: AuthorArchive) -> Path:
    user_dir = safe_filename(f"{archive.authorid}_{archive.username}")
    file_name = safe_filename(f"{archive.tid}_{archive.subject}") + ".json"
    return output_dir / user_dir / file_name


def _post_from_raw(raw: dict) -> ArchivedPost:
    return ArchivedPost(
        pid=int(raw["pid"]),
        lou=int(raw["lou"]),
        postdate=raw["postdate"],
        postdatetimestamp=int(raw["postdatetimestamp"]),
        content_raw=raw["content_raw"],
        content_text=raw["content_text"],
    )


def _load_existing(path: Path) -> dict[str, ArchivedPost]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {pid: _post_from_raw(post) for pid, post in raw.get("posts", {}).items()}


def merge_and_save_archive(
    output_dir: Path,
    archive: AuthorArchive,
) -> list[ArchivedPost]:
    path = archive_path(output_dir, archive)
    existing = _load_existing(path)
    changed: list[ArchivedPost] = []

    for pid, post in archive.posts.items():
        old = existing.get(pid)
        if old is None or old != post:
            changed.append(post)
        existing[pid] = post

    ordered_posts = dict(
        sorted(existing.items(), key=lambda item: (item[1].lou, item[1].pid))
    )
    archive.updated_at = datetime.now(UTC).isoformat()
    raw = {
        "authorid": archive.authorid,
        "username": archive.username,
        "tid": archive.tid,
        "subject": archive.subject,
        "thread_url": archive.thread_url,
        "updated_at": archive.updated_at,
        "posts": {pid: asdict(post) for pid, post in ordered_posts.items()},
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return sorted(changed, key=lambda post: (post.lou, post.pid))
