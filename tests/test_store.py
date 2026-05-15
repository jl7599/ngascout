from src.store import PostRecord, StoreData, filter_new, load, save


class TestSaveAndLoad:
    def test_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        data = StoreData(
            last_page=42,
            username="testuser",
            posts={
                "123": PostRecord(content="hello", postdate="2025-01-01 12:00", lou=5)
            },
        )
        save(1, 100, data)
        loaded = load(1, 100)
        assert loaded == data

    def test_load_nonexistent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        assert load(999, 999) is None

    def test_creates_subdirectory(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        data = StoreData(last_page=1, username="u", posts={})
        save(45905087, 557398, data)
        assert (tmp_path / "45905087" / "557398.json").exists()


class TestFilterNew:
    def test_all_new_when_no_store(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)

        class Reply:
            def __init__(self, pid):
                self.pid = pid

        replies = [Reply(1), Reply(2), Reply(3)]
        result = filter_new(None, replies)
        assert len(result) == 3

    def test_filters_existing_pids(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        stored = StoreData(
            last_page=10,
            username="u",
            posts={"1": PostRecord(content="a", postdate="d", lou=1)},
        )

        class Reply:
            def __init__(self, pid):
                self.pid = pid

        replies = [Reply(1), Reply(2), Reply(3)]
        result = filter_new(stored, replies)
        assert len(result) == 2
        assert [r.pid for r in result] == [2, 3]

    def test_none_new(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.store.DATA_DIR", tmp_path)
        stored = StoreData(
            last_page=10,
            username="u",
            posts={
                "1": PostRecord(content="a", postdate="d", lou=1),
                "2": PostRecord(content="b", postdate="d", lou=2),
            },
        )

        class Reply:
            def __init__(self, pid):
                self.pid = pid

        replies = [Reply(1), Reply(2)]
        result = filter_new(stored, replies)
        assert result == []
