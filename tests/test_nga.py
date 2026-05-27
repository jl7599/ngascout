from unittest.mock import MagicMock, patch

import pytest

from src.nga import (
    NgaAuthorThread,
    NgaReply,
    NgaResponse,
    NgaThreadInfo,
    NgaUser,
    fetch_author_threads_page,
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
        mock_resp.status_code = 200
        mock_resp.content = (
            "window.script_muti_get_var_store=" + MOCK_NGA_JSON
        ).encode("gbk")
        mock_resp.raise_for_status = MagicMock()

        with (
            patch("src.nga.time.sleep"),
            patch("src.nga.httpx.get", return_value=mock_resp),
        ):
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
        mock_resp.status_code = 200
        mock_resp.content = (
            "window.script_muti_get_var_store=" + reversed_json
        ).encode("gbk")
        mock_resp.raise_for_status = MagicMock()

        with (
            patch("src.nga.time.sleep"),
            patch("src.nga.httpx.get", return_value=mock_resp),
        ):
            result = fetch_thread(1, 1, "cookie")

        assert result.replies[0].lou == 0
        assert result.replies[1].lou == 1

    def test_http_error_raises(self):
        import httpx

        with (
            patch("src.nga.time.sleep"),
            patch(
                "src.nga.httpx.get",
                side_effect=httpx.HTTPStatusError(
                    "error", request=MagicMock(), response=MagicMock(status_code=403)
                ),
            ),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                fetch_thread(1, 1, "cookie")


class TestFetchAuthorThreadsPage:
    def test_parses_author_thread_list(self):
        mock_json = (
            '{"data":{"__T":{"1001":{"tid":1001,"subject":"第一篇",'
            '"authorid":21321600,"author":"测试用户","replies":3},'
            '"1002":{"tid":1002,"subject":"第二篇","authorid":21321600,'
            '"author":"测试用户","replies":0}},"__ROWS":40,"__PAGE":1}}'
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = ("window.script_muti_get_var_store=" + mock_json).encode(
            "gbk"
        )
        mock_resp.raise_for_status = MagicMock()

        with (
            patch("src.nga.time.sleep"),
            patch("src.nga.httpx.get", return_value=mock_resp) as mock_get,
        ):
            result = fetch_author_threads_page(21321600, 1, "cookie")

        assert result.current_page == 1
        assert result.total_pages == 2
        assert result.threads == [
            NgaAuthorThread(
                tid=1001,
                subject="第一篇",
                authorid=21321600,
                author="测试用户",
                replies=3,
            ),
            NgaAuthorThread(
                tid=1002,
                subject="第二篇",
                authorid=21321600,
                author="测试用户",
                replies=0,
            ),
        ]
        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs["params"] == {
            "authorid": 21321600,
            "page": 1,
            "lite": "js",
        }
