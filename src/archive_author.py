from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.author_archive_store import (
    ArchivedPost,
    AuthorArchive,
    merge_and_save_archive,
)
from src.nga import (
    NGA_BASE_URL,
    NgaAuthorThread,
    NgaReply,
    fetch_author_threads_page,
    fetch_thread,
)
from src.notify import format_message, send_webhook, strip_html

logger = logging.getLogger(__name__)


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "authors"


@dataclass
class ArchiveAuthorOptions:
    authorid: int
    cookie: str
    output_dir: Path = DEFAULT_OUTPUT_DIR
    notify: bool = False
    feishu_webhook_url: str = ""
    limit_threads: int | None = None


@dataclass
class ArchiveAuthorResult:
    threads: int
    posts: int
    changed_posts: int


def _fetch_all_author_threads(options: ArchiveAuthorOptions) -> list[NgaAuthorThread]:
    first = fetch_author_threads_page(options.authorid, 1, options.cookie)
    pages = [first]
    for page in range(2, first.total_pages + 1):
        pages.append(fetch_author_threads_page(options.authorid, page, options.cookie))

    threads_by_tid: dict[int, NgaAuthorThread] = {}
    for page in pages:
        for thread in page.threads:
            threads_by_tid.setdefault(thread.tid, thread)

    threads = list(threads_by_tid.values())
    if options.limit_threads is not None:
        return threads[: options.limit_threads]
    return threads


def _fetch_author_posts(
    thread: NgaAuthorThread,
    options: ArchiveAuthorOptions,
) -> AuthorArchive:
    first = fetch_thread(thread.tid, 1, options.cookie)
    if first.thread_info is None:
        raise ValueError(f"No thread info returned for tid={thread.tid}")
    replies = list(first.replies)
    for page in range(2, first.total_pages + 1):
        replies.extend(fetch_thread(thread.tid, page, options.cookie).replies)

    username = thread.author
    if options.authorid in first.users:
        username = first.users[options.authorid].username

    posts: dict[str, ArchivedPost] = {}
    for reply in sorted(replies, key=lambda item: item.lou):
        if reply.authorid != options.authorid:
            continue
        posts[str(reply.pid)] = _to_archived_post(reply)

    return AuthorArchive(
        authorid=options.authorid,
        username=username,
        tid=thread.tid,
        subject=first.thread_info.subject or thread.subject,
        thread_url=f"{NGA_BASE_URL}/read.php?tid={thread.tid}",
        posts=posts,
    )


def _to_archived_post(reply: NgaReply) -> ArchivedPost:
    return ArchivedPost(
        pid=reply.pid,
        lou=reply.lou,
        postdate=reply.postdate,
        postdatetimestamp=reply.postdatetimestamp,
        content_raw=reply.content,
        content_text=strip_html(reply.content),
    )


def _notify_changes(
    webhook_url: str,
    archive: AuthorArchive,
    changed_posts: list[ArchivedPost],
) -> None:
    if not changed_posts:
        return
    message = format_message(archive.subject, archive.username, changed_posts)
    send_webhook(webhook_url, message)


def archive_author(options: ArchiveAuthorOptions) -> ArchiveAuthorResult:
    if options.notify and not options.feishu_webhook_url:
        raise ValueError("feishu_webhook_url is required when notify is enabled")

    threads = _fetch_all_author_threads(options)
    total_posts = 0
    total_changed = 0

    for thread in threads:
        try:
            archive = _fetch_author_posts(thread, options)
        except Exception as e:
            logger.error(
                "Failed to fetch authorid=%d tid=%d: %s",
                options.authorid,
                thread.tid,
                e,
            )
            continue
        changed = merge_and_save_archive(options.output_dir, archive)
        total_posts += len(archive.posts)
        total_changed += len(changed)
        if options.notify:
            _notify_changes(options.feishu_webhook_url, archive, changed)

    return ArchiveAuthorResult(
        threads=len(threads),
        posts=total_posts,
        changed_posts=total_changed,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive all NGA posts by author.")
    parser.add_argument("--authorid", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--limit-threads", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    load_dotenv()
    args = parse_args()
    cookie = os.getenv("NGA_COOKIE", "")
    if not cookie:
        raise ValueError("NGA_COOKIE is required")
    feishu_webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "")
    if args.notify and not feishu_webhook_url:
        raise ValueError("FEISHU_WEBHOOK_URL is required when --notify is enabled")

    result = archive_author(
        ArchiveAuthorOptions(
            authorid=args.authorid,
            cookie=cookie,
            output_dir=args.output_dir,
            notify=args.notify,
            feishu_webhook_url=feishu_webhook_url,
            limit_threads=args.limit_threads,
        )
    )
    logger.info(
        "Archived authorid=%d threads=%d posts=%d changed=%d",
        args.authorid,
        result.threads,
        result.posts,
        result.changed_posts,
    )


if __name__ == "__main__":
    main()
