from src.core.store import PostRecord, StoreData, load, save


class TestSaveAndLoad:
    def test_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.core.store.DATA_DIR", tmp_path)
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
        monkeypatch.setattr("src.core.store.DATA_DIR", tmp_path)
        assert load(999, 999) is None

    def test_creates_subdirectory(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.core.store.DATA_DIR", tmp_path)
        data = StoreData(last_page=1, username="u", posts={})
        save(45905087, 557398, data)
        assert (tmp_path / "45905087" / "557398.json").exists()
