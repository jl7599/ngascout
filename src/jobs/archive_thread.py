from __future__ import annotations

import argparse
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from src.core.nga import NgaReply, fetch_thread, page_for_lou
from src.core.notify import strip_html

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "archive"
CHECKPOINT_PAGES = 5


@dataclass
class ArchiveThreadOptions:
    tid: int
    cookie: str
    output_dir: Path = DEFAULT_OUTPUT_DIR


@dataclass
class ArchiveThreadResult:
    new_posts: int
    pages_fetched: int


def parse_tid_input(input_str: str) -> int:
    s = input_str.strip()
    if s.isdigit():
        return int(s)
    m = re.search(r"tid=(\d+)", s)
    if m:
        return int(m.group(1))
    raise ValueError(f"Cannot parse tid from input: {input_str!r}")


def extract_quote_lou(content_raw: str | int, pid_to_lou: dict[int, int]) -> int | None:
    m = re.search(r"\[pid=(\d+),", str(content_raw))
    if not m:
        return None
    return pid_to_lou.get(int(m.group(1)))


def format_post_line(reply: NgaReply, quote_lou: int | None, cleaned: str) -> str:
    escaped = cleaned.replace("\\", "\\\\").replace("\n", "\\n").replace("|", "\\|")
    parts = [
        f"楼层:{reply.lou}",
        f"时间:{reply.postdate}",
        f"用户:{reply.authorid}",
        f"内容:{escaped}",
    ]
    if quote_lou is not None:
        parts.append(f"引用:{quote_lou}")
    return "|".join(parts)


def _load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_meta(archive_dir: Path) -> dict | None:
    return _load_json(archive_dir / "meta.json", None)


def save_meta(archive_dir: Path, meta: dict) -> None:
    path = archive_dir / "meta.json"
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_pid_map(archive_dir: Path) -> dict[int, int]:
    raw = _load_json(archive_dir / "pid_map.json", {})
    return {int(k): v for k, v in raw.items()}


def save_pid_map(archive_dir: Path, pid_map: dict[int, int]) -> None:
    path = archive_dir / "pid_map.json"
    data = {str(k): v for k, v in pid_map.items()}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_users(archive_dir: Path) -> dict[str, str]:
    return _load_json(archive_dir / "users.json", {})


def save_users(archive_dir: Path, users: dict[str, str]) -> None:
    path = archive_dir / "users.json"
    path.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def append_posts_txt(archive_dir: Path, lines: list[str]) -> None:
    path = archive_dir / "posts.txt"
    with path.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def append_user_txt(archive_dir: Path, uid: int, lines: list[str]) -> None:
    users_dir = archive_dir / "users"
    users_dir.mkdir(parents=True, exist_ok=True)
    path = users_dir / f"{uid}.txt"
    with path.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def archive_thread(options: ArchiveThreadOptions) -> ArchiveThreadResult:
    archive_dir = options.output_dir / str(options.tid)
    archive_dir.mkdir(parents=True, exist_ok=True)

    pid_to_lou = load_pid_map(archive_dir)
    existing_users = load_users(archive_dir)
    meta = load_meta(archive_dir)

    if meta is None:
        first = fetch_thread(options.tid, 1, options.cookie)
        if first.thread_info is None:
            raise ValueError(f"No thread info returned for tid={options.tid}")
        total_pages = first.total_pages
        start_page = 1
        last_lou = -1
        total_replies = first.thread_info.replies
        subject = first.thread_info.subject
        pages_fetched = 1
        initial_replies = first.replies
        initial_users = first.users
    else:
        latest = fetch_thread(options.tid, "e", options.cookie)
        if latest.thread_info is None:
            raise ValueError(f"No thread info returned for tid={options.tid}")
        pages_fetched = 0
        if latest.thread_info.replies <= meta["total_replies"]:
            logger.info("No new posts for tid=%d", options.tid)
            return ArchiveThreadResult(new_posts=0, pages_fetched=pages_fetched)
        total_pages = latest.total_pages
        start_page = page_for_lou(meta["last_lou"])
        last_lou = meta["last_lou"]
        total_replies = latest.thread_info.replies
        subject = meta.get("subject", "")

    total_new = 0

    def process_batch(replies: list[NgaReply], users: dict) -> None:
        nonlocal last_lou, total_new

        new_replies = sorted(
            [r for r in replies if r.lou > last_lou],
            key=lambda r: r.lou,
        )
        if not new_replies:
            return

        for r in new_replies:
            pid_to_lou[r.pid] = r.lou

        for uid, u in users.items():
            existing_users[str(uid)] = u.username

        all_lines: list[str] = []
        user_lines: dict[int, list[str]] = {}

        for r in new_replies:
            quote_lou = extract_quote_lou(r.content, pid_to_lou)
            cleaned = strip_html(str(r.content))
            line = format_post_line(r, quote_lou, cleaned)
            all_lines.append(line)
            user_lines.setdefault(r.authorid, []).append(line)

        append_posts_txt(archive_dir, all_lines)
        for uid, lines in user_lines.items():
            append_user_txt(archive_dir, uid, lines)

        save_users(archive_dir, existing_users)
        save_pid_map(archive_dir, pid_to_lou)

        last_lou = max(r.lou for r in new_replies)
        total_new += len(new_replies)

        save_meta(
            archive_dir,
            {
                "tid": options.tid,
                "subject": subject,
                "last_lou": last_lou,
                "total_replies": total_replies,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )

    if meta is None:
        process_batch(initial_replies, initial_users)
        page_range = range(2, total_pages + 1)
    else:
        page_range = range(start_page, total_pages + 1)

    for i, page_num in enumerate(page_range, start=1):
        resp = fetch_thread(options.tid, page_num, options.cookie)
        pages_fetched += 1
        process_batch(resp.replies, resp.users)

        if i % CHECKPOINT_PAGES == 0:
            logger.info(
                "Checkpoint: tid=%d fetched page %d/%d",
                options.tid,
                page_num,
                total_pages,
            )

    logger.info(
        "Archived tid=%d new_posts=%d pages_fetched=%d",
        options.tid,
        total_new,
        pages_fetched,
    )
    return ArchiveThreadResult(new_posts=total_new, pages_fetched=pages_fetched)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive all posts in an NGA thread.",
    )
    parser.add_argument("tid_input", nargs="?", help="Thread URL or tid number")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    load_dotenv()
    args = parse_args()
    tid_input = args.tid_input or os.getenv("ARCHIVE_THREAD_TID", "")
    if not tid_input:
        raise ValueError(
            "tid is required: provide as CLI argument or set ARCHIVE_THREAD_TID"
        )
    tid = parse_tid_input(tid_input)
    cookie = os.getenv("NGA_COOKIE", "")
    if not cookie:
        raise ValueError("NGA_COOKIE is required")

    archive_thread(
        ArchiveThreadOptions(tid=tid, cookie=cookie, output_dir=args.output_dir),
    )


if __name__ == "__main__":
    main()
