from unittest.mock import patch

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
                pid=123,
                authorid=557398,
                postdate="2025-12-31 15:41",
                postdatetimestamp=1767166910,
                lou=50,
                content="hello",
            ),
        ]
    return NgaResponse(
        thread_info=NgaThreadInfo(
            tid=45905087,
            subject="测试帖子",
            authorid=557398,
            replies=100,
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

        with (
            patch("src.main.fetch_thread", return_value=_make_response()),
            patch("src.main.send_webhook", return_value=True),
        ):
            process_thread(config, item)

        from src.store import load

        stored = load(45905087, 557398)
        assert stored is not None
        assert "123" in stored.posts
        assert stored.last_page == 50

    def test_skips_already_seen(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config()
        item = WatchItem(tid=45905087, uids=[557398])

        from src.store import save

        save(
            45905087,
            557398,
            StoreData(
                last_page=50,
                username="测试用户",
                posts={
                    "123": PostRecord(
                        content="hello", postdate="2025-12-31 15:41", lou=50
                    )
                },
            ),
        )

        with (
            patch("src.main.fetch_thread", return_value=_make_response()),
            patch("src.main.send_webhook") as mock_send,
        ):
            process_thread(config, item)
            mock_send.assert_not_called()

    def test_default_op_when_no_uids(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config(watch_list=[WatchItem(tid=45905087, uids=[])])
        item = WatchItem(tid=45905087, uids=[])

        with (
            patch("src.main.fetch_thread", return_value=_make_response()),
            patch("src.main.send_webhook", return_value=True),
        ):
            process_thread(config, item)

        from src.store import load

        stored = load(45905087, 557398)
        assert stored is not None

    def test_fetch_failure_skips_thread(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config()
        item = WatchItem(tid=45905087, uids=[557398])

        with patch("src.main.fetch_thread", side_effect=Exception("network error")):
            process_thread(config, item)

    def test_send_failure_does_not_save(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config()
        item = WatchItem(tid=45905087, uids=[557398])

        with (
            patch("src.main.fetch_thread", return_value=_make_response()),
            patch("src.main.send_webhook", return_value=False),
        ):
            process_thread(config, item)

        from src.store import load

        stored = load(45905087, 557398)
        assert stored is None

    def test_fetches_intermediate_pages(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        config = _make_config()
        item = WatchItem(tid=45905087, uids=[557398])

        from src.store import save

        save(
            45905087,
            557398,
            StoreData(last_page=20, username="测试用户", posts={}),
        )

        page2_response = _make_response(
            replies=[
                NgaReply(
                    pid=200,
                    authorid=557398,
                    postdate="d1",
                    postdatetimestamp=1,
                    lou=25,
                    content="page2",
                ),
            ],
            current_page=2,
            total_pages=5,
        )
        latest_response = _make_response(
            replies=[
                NgaReply(
                    pid=300,
                    authorid=557398,
                    postdate="d2",
                    postdatetimestamp=2,
                    lou=50,
                    content="latest",
                ),
            ],
            current_page=5,
            total_pages=5,
        )

        def mock_fetch(tid, page, cookie):
            if page == 2:
                return page2_response
            return latest_response

        with (
            patch("src.main.fetch_thread", side_effect=mock_fetch),
            patch("src.main.send_webhook", return_value=True),
        ):
            process_thread(config, item)

        from src.store import load

        stored = load(45905087, 557398)
        assert stored is not None
        assert "200" in stored.posts
        assert "300" in stored.posts
        assert stored.last_page == 50
