from unittest.mock import patch

from src.archive_author import ArchiveAuthorOptions, archive_author
from src.nga import (
    NgaAuthorThread,
    NgaAuthorThreadsPage,
    NgaReply,
    NgaResponse,
    NgaThreadInfo,
    NgaUser,
)


def _thread_page(tid, subject, page, total_pages, replies):
    return NgaResponse(
        thread_info=NgaThreadInfo(
            tid=tid,
            subject=subject,
            authorid=21321600,
            replies=len(replies),
        ),
        users={21321600: NgaUser(uid=21321600, username="测试用户")},
        replies=replies,
        total_pages=total_pages,
        current_page=page,
    )


def test_archive_author_fetches_all_author_threads_and_thread_pages(tmp_path):
    thread_list = NgaAuthorThreadsPage(
        threads=[
            NgaAuthorThread(
                tid=1001,
                subject="第一篇",
                authorid=21321600,
                author="测试用户",
                replies=21,
            )
        ],
        total_pages=1,
        current_page=1,
    )
    page1 = _thread_page(
        1001,
        "第一篇",
        1,
        2,
        [
            NgaReply(
                pid=11,
                authorid=21321600,
                postdate="d1",
                postdatetimestamp=1,
                lou=0,
                content="主楼",
            )
        ],
    )
    page2 = _thread_page(
        1001,
        "第一篇",
        2,
        2,
        [
            NgaReply(
                pid=12,
                authorid=21321600,
                postdate="d2",
                postdatetimestamp=2,
                lou=20,
                content="回复",
            ),
            NgaReply(
                pid=13,
                authorid=999,
                postdate="d3",
                postdatetimestamp=3,
                lou=21,
                content="别人",
            ),
        ],
    )

    with (
        patch("src.archive_author.fetch_author_threads_page", return_value=thread_list),
        patch("src.archive_author.fetch_thread", side_effect=[page1, page2]) as fetch,
        patch("src.archive_author.send_webhook") as send,
    ):
        result = archive_author(
            ArchiveAuthorOptions(
                authorid=21321600,
                cookie="cookie",
                output_dir=tmp_path,
            )
        )

    assert result.changed_posts == 2
    assert fetch.call_args_list[0].args[:2] == (1001, 1)
    assert fetch.call_args_list[1].args[:2] == (1001, 2)
    send.assert_not_called()


def test_archive_author_notifies_only_when_enabled(tmp_path):
    thread_list = NgaAuthorThreadsPage(
        threads=[
            NgaAuthorThread(
                tid=1001,
                subject="第一篇",
                authorid=21321600,
                author="测试用户",
                replies=0,
            )
        ],
        total_pages=1,
        current_page=1,
    )
    page1 = _thread_page(
        1001,
        "第一篇",
        1,
        1,
        [
            NgaReply(
                pid=11,
                authorid=21321600,
                postdate="d1",
                postdatetimestamp=1,
                lou=0,
                content="主楼",
            )
        ],
    )

    with (
        patch("src.archive_author.fetch_author_threads_page", return_value=thread_list),
        patch("src.archive_author.fetch_thread", return_value=page1),
        patch("src.archive_author.send_webhook", return_value=True) as send,
    ):
        archive_author(
            ArchiveAuthorOptions(
                authorid=21321600,
                cookie="cookie",
                output_dir=tmp_path,
                notify=True,
                feishu_webhook_url="https://example.com/hook",
            )
        )

    send.assert_called_once()
