import pytest

from src.core.config import WatchItem, load_config, parse_watch_list


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr("src.core.config.load_dotenv", lambda: None)


class TestParseWatchList:
    def test_single_tid_with_users(self):
        result = parse_watch_list("45905087,557398,123456")
        assert result == [WatchItem(tid=45905087, uids=[557398, 123456])]

    def test_multiple_tids(self):
        result = parse_watch_list("45905087,557398|45974302|46272205,38906013")
        assert result == [
            WatchItem(tid=45905087, uids=[557398]),
            WatchItem(tid=45974302, uids=[]),
            WatchItem(tid=46272205, uids=[38906013]),
        ]

    def test_empty_users_means_op(self):
        result = parse_watch_list("45905087")
        assert result == [WatchItem(tid=45905087, uids=[])]

    def test_empty_string(self):
        assert parse_watch_list("") == []

    def test_whitespace_handling(self):
        result = parse_watch_list(" 45905087 , 557398 | 45974302 ")
        assert result == [
            WatchItem(tid=45905087, uids=[557398]),
            WatchItem(tid=45974302, uids=[]),
        ]


class TestLoadConfig:
    def test_success(self, monkeypatch):
        monkeypatch.setenv("WATCH", "45905087,557398")
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setenv("NGA_COOKIE", "test_cookie")
        monkeypatch.setenv("CRON_INTERVAL", "10")
        config = load_config()
        assert config.watch_list == [WatchItem(tid=45905087, uids=[557398])]
        assert config.feishu_webhook_url == "https://example.com/hook"
        assert config.nga_cookie == "test_cookie"
        assert config.cron_interval == 10

    def test_default_cron_interval(self, monkeypatch):
        monkeypatch.setenv("WATCH", "")
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.setenv("NGA_COOKIE", "test_cookie")
        config = load_config()
        assert config.cron_interval == 5

    def test_missing_feishu_url(self, monkeypatch):
        monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
        monkeypatch.setenv("NGA_COOKIE", "test_cookie")
        with pytest.raises(ValueError, match="FEISHU_WEBHOOK_URL"):
            load_config()

    def test_missing_nga_cookie(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/hook")
        monkeypatch.delenv("NGA_COOKIE", raising=False)
        with pytest.raises(ValueError, match="NGA_COOKIE"):
            load_config()
