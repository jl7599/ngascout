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