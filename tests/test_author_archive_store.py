import json

from src.author_archive_store import (
    ArchivedPost,
    AuthorArchive,
    merge_and_save_archive,
    safe_filename,
)


def test_safe_filename_removes_path_characters():
    assert safe_filename('100_标题/含\\非法:*?"<>|字符') == "100_标题_含_非法_字符"


def test_merge_and_save_archive_creates_file_and_reports_new_posts(tmp_path):
    archive = AuthorArchive(
        authorid=21321600,
        username="测试用户",
        tid=1001,
        subject="第一篇",
        thread_url="https://bbs.nga.cn/read.php?tid=1001",
        posts={
            "11": ArchivedPost(
                pid=11,
                lou=1,
                postdate="2026-01-01 12:00",
                postdatetimestamp=1767268800,
                content_raw="<b>hello</b>",
                content_text="hello",
            )
        },
    )

    changed = merge_and_save_archive(tmp_path, archive)

    assert [p.pid for p in changed] == [11]
    saved = json.loads(
        (tmp_path / "21321600_测试用户" / "1001_第一篇.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["authorid"] == 21321600
    assert saved["username"] == "测试用户"
    assert saved["posts"]["11"]["content_text"] == "hello"


def test_merge_and_save_archive_dedupes_and_updates_changed_posts(tmp_path):
    first = AuthorArchive(
        authorid=21321600,
        username="测试用户",
        tid=1001,
        subject="第一篇",
        thread_url="https://bbs.nga.cn/read.php?tid=1001",
        posts={
            "11": ArchivedPost(
                pid=11,
                lou=1,
                postdate="2026-01-01 12:00",
                postdatetimestamp=1767268800,
                content_raw="old",
                content_text="old",
            )
        },
    )
    merge_and_save_archive(tmp_path, first)

    second = AuthorArchive(
        authorid=21321600,
        username="测试用户",
        tid=1001,
        subject="第一篇",
        thread_url="https://bbs.nga.cn/read.php?tid=1001",
        posts={
            "11": ArchivedPost(
                pid=11,
                lou=1,
                postdate="2026-01-01 12:00",
                postdatetimestamp=1767268800,
                content_raw="new",
                content_text="new",
            ),
            "12": ArchivedPost(
                pid=12,
                lou=2,
                postdate="2026-01-01 12:01",
                postdatetimestamp=1767268860,
                content_raw="added",
                content_text="added",
            ),
        },
    )

    changed = merge_and_save_archive(tmp_path, second)

    assert [p.pid for p in changed] == [11, 12]
    saved = json.loads(
        (tmp_path / "21321600_测试用户" / "1001_第一篇.json").read_text(
            encoding="utf-8"
        )
    )
    assert list(saved["posts"]) == ["11", "12"]
    assert saved["posts"]["11"]["content_raw"] == "new"
