from unittest.mock import patch

from src.archive_thread import (
    ArchiveThreadOptions,
    extract_quote_lou,
    format_post_line,
    parse_tid_input,
)
from src.nga import NgaReply, NgaResponse, NgaThreadInfo, NgaUser


def _reply(lou, authorid=100, pid=None, content="hello"):
    return NgaReply(
        pid=pid or lou * 10,
        authorid=authorid,
        postdate="2026-01-01 12:00",
        postdatetimestamp=1735729200 + lou,
        lou=lou,
        content=content,
    )


def _response(tid, replies, total_pages=1, page=1, total_replies=None):
    users = {}
    for r in replies:
        if r.authorid not in users:
            users[r.authorid] = NgaUser(uid=r.authorid, username=f"user{r.authorid}")
    return NgaResponse(
        thread_info=NgaThreadInfo(
            tid=tid,
            subject="测试帖子",
            authorid=100,
            replies=total_replies if total_replies is not None else len(replies),
        ),
        users=users,
        replies=replies,
        total_pages=total_pages,
        current_page=page,
    )


# --- parse_tid_input ---


def test_parse_tid_input_number():
    assert parse_tid_input("45974302") == 45974302


def test_parse_tid_input_url():
    assert parse_tid_input("https://bbs.nga.cn/read.php?tid=45974302") == 45974302


def test_parse_tid_input_url_with_extra_params():
    url = "https://bbs.nga.cn/read.php?tid=45974302&page=2"
    assert parse_tid_input(url) == 45974302


def test_parse_tid_input_invalid():
    import pytest

    with pytest.raises(ValueError):
        parse_tid_input("not_a_tid")


# --- extract_quote_lou ---


def test_extract_quote_lou_with_pid():
    content = "[quote][pid=100,45974302,1]Reply[/pid] some quote[/quote] reply"
    pid_map = {100: 5}
    assert extract_quote_lou(content, pid_map) == 5


def test_extract_quote_lou_missing_pid():
    content = "[quote][pid=999,45974302,1]Reply[/pid] some quote[/quote] reply"
    pid_map = {100: 5}
    assert extract_quote_lou(content, pid_map) is None


def test_extract_quote_lou_no_quote():
    content = "just a normal post"
    assert extract_quote_lou(content, {}) is None


# --- format_post_line ---


def test_format_post_line_basic():
    r = _reply(1)
    line = format_post_line(r, None, "hello")
    assert line == "楼层:1|时间:2026-01-01 12:00|用户:100|内容:hello"


def test_format_post_line_with_quote():
    r = _reply(1)
    line = format_post_line(r, 5, "hello")
    assert line == "楼层:1|时间:2026-01-01 12:00|用户:100|内容:hello|引用:5"


def test_format_post_line_escapes_newlines():
    r = _reply(1)
    line = format_post_line(r, None, "line1\nline2")
    assert "内容:line1\\nline2" in line


def test_format_post_line_escapes_pipe():
    r = _reply(1)
    line = format_post_line(r, None, "a|b")
    assert "内容:a\\|b" in line


def test_format_post_line_escapes_backslash():
    r = _reply(1)
    line = format_post_line(r, None, "a\\b")
    assert "内容:a\\\\b" in line


# --- archive_thread ---


def test_archive_thread_first_run(tmp_path):
    page1 = _response(1001, [_reply(0), _reply(1)], total_pages=1)

    with patch("src.archive_thread.fetch_thread", return_value=page1):
        from src.archive_thread import archive_thread

        result = archive_thread(
            ArchiveThreadOptions(tid=1001, cookie="c", output_dir=tmp_path),
        )

    assert result.new_posts == 2
    assert result.pages_fetched == 1

    archive_dir = tmp_path / "1001"
    posts_txt = (archive_dir / "posts.txt").read_text(encoding="utf-8")
    assert "楼层:0|" in posts_txt
    assert "楼层:1|" in posts_txt

    users_json = (archive_dir / "users.json").read_text(encoding="utf-8")
    assert '"100"' in users_json

    user_txt = (archive_dir / "users" / "100.txt").read_text(encoding="utf-8")
    assert "楼层:0|" in user_txt
    assert "楼层:1|" in user_txt

    meta = __import__("json").loads(
        (archive_dir / "meta.json").read_text(encoding="utf-8")
    )
    assert meta["last_lou"] == 1


def test_archive_thread_incremental_no_new(tmp_path):
    archive_dir = tmp_path / "1001"
    archive_dir.mkdir(parents=True)

    from src.archive_thread import save_meta

    save_meta(
        archive_dir,
        {
            "tid": 1001,
            "subject": "test",
            "last_lou": 5,
            "total_replies": 10,
            "updated_at": "2026-01-01T00:00:00+00:00",
        },
    )

    latest = _response(1001, [_reply(5)], total_replies=10)

    with patch("src.archive_thread.fetch_thread", return_value=latest):
        from src.archive_thread import archive_thread

        result = archive_thread(
            ArchiveThreadOptions(tid=1001, cookie="c", output_dir=tmp_path),
        )

    assert result.new_posts == 0
    assert result.pages_fetched == 0


def test_archive_thread_incremental_with_new(tmp_path):
    archive_dir = tmp_path / "1001"
    archive_dir.mkdir(parents=True)

    from src.archive_thread import save_meta, save_pid_map

    save_meta(
        archive_dir,
        {
            "tid": 1001,
            "subject": "test",
            "last_lou": 1,
            "total_replies": 2,
            "updated_at": "2026-01-01T00:00:00+00:00",
        },
    )
    save_pid_map(archive_dir, {0: 0, 10: 1})

    latest = _response(1001, [_reply(1), _reply(2)], total_pages=1, total_replies=3)
    new_page = _response(1001, [_reply(1), _reply(2)], total_pages=1, total_replies=3)

    with patch("src.archive_thread.fetch_thread", side_effect=[latest, new_page]):
        from src.archive_thread import archive_thread

        result = archive_thread(
            ArchiveThreadOptions(tid=1001, cookie="c", output_dir=tmp_path),
        )

    assert result.new_posts == 1

    posts_txt = (archive_dir / "posts.txt").read_text(encoding="utf-8")
    assert "楼层:2|" in posts_txt
    assert "楼层:1|" not in posts_txt


def test_archive_thread_multi_page(tmp_path):
    page1 = _response(
        1001,
        [_reply(0, pid=1), _reply(1, pid=2)],
        total_pages=2,
        page=1,
        total_replies=3,
    )
    page2 = _response(
        1001,
        [_reply(2, pid=3)],
        total_pages=2,
        page=2,
        total_replies=3,
    )

    with patch("src.archive_thread.fetch_thread", side_effect=[page1, page2]):
        from src.archive_thread import archive_thread

        result = archive_thread(
            ArchiveThreadOptions(tid=1001, cookie="c", output_dir=tmp_path),
        )

    assert result.new_posts == 3
    assert result.pages_fetched == 2

    posts_txt = (tmp_path / "1001" / "posts.txt").read_text(encoding="utf-8")
    lines = [line for line in posts_txt.strip().split("\n") if line]
    assert len(lines) == 3
