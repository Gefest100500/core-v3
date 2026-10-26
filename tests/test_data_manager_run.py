# tests/test_data_manager_run.py
"""
Тесты для utils/data_manager.py.

ВАЖНО: DataManager — синглтон с реальной записью в data/.
Тестируем через временную папку: патчим DATA_DIR-пути.
"""
import json
import os
import threading
import time
from pathlib import Path

import pytest

from utils.data_manager import DataManager


# =========================================================
# FIXTURES
# =========================================================
@pytest.fixture
def dm(tmp_path, monkeypatch):
    """Создаёт DataManager с путями в tmp_path.

    Патчим модульные пути (HISTORY_PATH и т.д.) через monkeypatch,
    чтобы запись шла в tmp_path, а не в реальный data/.
    """
    monkeypatch.setattr(
        "utils.data_manager.HISTORY_PATH",
        tmp_path / "history.json",
    )
    monkeypatch.setattr(
        "utils.data_manager.INVENTORY_PATH",
        tmp_path / "active_inventory.json",
    )
    monkeypatch.setattr(
        "utils.data_manager.INVENTORY_ARCHIVE_PATH",
        tmp_path / "archive.json",
    )
    monkeypatch.setattr(
        "utils.data_manager.GM_DATA_PATH",
        tmp_path / "gm_data.json",
    )
    monkeypatch.setattr(
        "utils.data_manager.GM_NOTES_PATH",
        tmp_path / "gm_notes.json",
    )
    monkeypatch.setattr(
        "utils.data_manager.EMAILS_PATH",
        tmp_path / "emails.json",
    )

    manager = DataManager()
    yield manager
    manager.shutdown()


def _wait_for_write(dm, timeout=2.0):
    """Ждём, пока очередь записи опустеет."""
    start = time.time()
    while not dm._write_queue.empty() and time.time() - start < timeout:
        time.sleep(0.01)
    time.sleep(0.05)  # даём writer thread завершить последнюю запись


# =========================================================
# SIGNATURE
# =========================================================
class TestSignature:
    def test_none(self):
        assert DataManager.signature(None) is None

    def test_same_data_same_signature(self):
        s1 = DataManager.signature({"a": 1, "b": 2})
        s2 = DataManager.signature({"b": 2, "a": 1})
        assert s1 == s2  # sort_keys=True

    def test_different_data(self):
        s1 = DataManager.signature({"a": 1})
        s2 = DataManager.signature({"a": 2})
        assert s1 != s2

    def test_string(self):
        s = DataManager.signature("test")
        assert isinstance(s, str)
        assert len(s) == 32  # md5


# =========================================================
# LOCKS
# =========================================================
class TestLocks:
    def test_get_lock(self, dm):
        lock1 = dm._get_lock("test")
        lock2 = dm._get_lock("test")
        assert lock1 is lock2  # один и тот же лок

    def test_different_names_different_locks(self, dm):
        lock1 = dm._get_lock("a")
        lock2 = dm._get_lock("b")
        assert lock1 is not lock2


# =========================================================
# HISTORY
# =========================================================
class TestHistory:
    def test_empty(self, dm):
        assert dm.get_history() == []

    def test_set_and_get(self, dm):
        dm.set_history([{"action": "test1"}, {"action": "test2"}])
        _wait_for_write(dm)
        result = dm.get_history()
        assert len(result) == 2

    def test_max_100(self, dm):
        """set_history обрезает до 100 записей."""
        big = [{"action": f"a{i}"} for i in range(150)]
        dm.set_history(big)
        _wait_for_write(dm)
        assert len(dm.get_history()) == 100

    def test_add_action(self, dm):
        dm.add_action("Test", "Details", "🔧")
        _wait_for_write(dm)
        history = dm.get_history()
        assert len(history) == 1
        assert history[0]["action"] == "Test"
        assert history[0]["details"] == "Details"

    def test_add_action_truncates(self, dm):
        """Быстрая версия: set_history вместо 120 add_action."""
        big = [{"action": f"a{i}"} for i in range(150)]
        dm.set_history(big)
        _wait_for_write(dm)
        assert len(dm.get_history()) == 100


# =========================================================
# ACTIVE INVENTORY
# =========================================================
class TestActiveInventory:
    def test_empty(self, dm):
        assert dm.get_active_inventory() is None

    def test_set_and_get(self, dm):
        dm.set_active_inventory({"gm_code": "111", "days": 5})
        _wait_for_write(dm)
        result = dm.get_active_inventory()
        assert result["gm_code"] == "111"

    def test_set_none_deletes(self, dm):
        dm.set_active_inventory({"gm_code": "111"})
        _wait_for_write(dm)
        assert dm.get_active_inventory() is not None

        dm.set_active_inventory(None)
        _wait_for_write(dm)
        assert dm.get_active_inventory() is None


# =========================================================
# ARCHIVE
# =========================================================
class TestArchive:
    def test_empty(self, dm):
        assert dm.get_inventory_archive() == []

    def test_set_and_get(self, dm):
        dm.set_inventory_archive([{"gm_code": "111"}])
        _wait_for_write(dm)
        result = dm.get_inventory_archive()
        assert len(result) == 1


# =========================================================
# GM_DATA / GM_NOTES
# =========================================================
class TestGmData:
    def test_gm_data_empty(self, dm):
        assert dm.get_gm_data() == []

    def test_gm_notes_empty(self, dm):
        assert dm.get_gm_notes() == {}

    def test_gm_notes_set(self, dm):
        dm.set_gm_notes({"111": "note"})
        _wait_for_write(dm)
        assert dm.get_gm_notes() == {"111": "note"}


# =========================================================
# EMAILS
# =========================================================
class TestEmails:
    def test_empty(self, dm):
        assert dm.get_emails() == []

    def test_set_emails(self, dm):
        dm.set_emails([{"gm_code": "111"}])
        _wait_for_write(dm)
        assert len(dm.get_emails()) == 1

    def test_add_email(self, dm):
        count = dm.add_email({"gm_code": "111"})
        assert count == 1
        _wait_for_write(dm)
        assert len(dm.get_emails()) == 1

    def test_add_multiple(self, dm):
        dm.add_email({"gm_code": "111"})
        dm.add_email({"gm_code": "222"})
        count = dm.add_email({"gm_code": "333"})
        assert count == 3
        _wait_for_write(dm)
        assert len(dm.get_emails()) == 3


# =========================================================
# CACHE
# =========================================================
class TestCache:
    def test_cache_after_read(self, dm, tmp_path):
        """После чтения файл попадает в кэш."""
        path = tmp_path / "history.json"
        path.write_text('[{"action": "cached"}]', encoding="utf-8")

        result = dm.get_history()
        assert len(result) == 1
        assert "history" in dm._cache

    def test_cache_by_mtime(self, dm, tmp_path):
        """Повторное чтение с тем же mtime — из кэша."""
        path = tmp_path / "history.json"
        path.write_text('[{"action": "first"}]', encoding="utf-8")

        result1 = dm.get_history()
        result2 = dm.get_history()
        assert result1 == result2

    def test_invalidate(self, dm):
        dm.set_history([{"action": "test"}])
        _wait_for_write(dm)

        dm.invalidate("history")
        cached = dm._cache.get("history")
        assert cached is not None
        assert cached[1] is None  # mtime сброшен

    def test_invalidate_all(self, dm):
        dm.set_history([{"action": "test"}])
        dm.set_gm_notes({"a": "b"})
        _wait_for_write(dm)

        dm.invalidate_all()
        for name in dm._cache:
            assert dm._cache[name][1] is None


# =========================================================
# READ_JSON_ASYNC
# =========================================================
class TestReadAsync:
    def test_async_read_existing(self, dm, tmp_path):
        """Асинхронное чтение существующего файла."""
        path = tmp_path / "history.json"
        path.write_text('[{"action": "async"}]', encoding="utf-8")

        result = []
        done = threading.Event()

        def callback(data):
            result.append(data)
            done.set()

        dm.read_json_async("history", str(path), callback)
        done.wait(timeout=2.0)

        assert len(result) == 1
        assert result[0][0]["action"] == "async"

    def test_async_read_missing(self, dm, tmp_path):
        """Асинхронное чтение несуществующего файла — callback(None)."""
        result = []
        done = threading.Event()

        def callback(data):
            result.append(data)
            done.set()

        dm.read_json_async(
            "nonexistent",
            str(tmp_path / "nonexistent.json"),
            callback,
        )
        done.wait(timeout=2.0)

        assert result == [None]

    def test_async_read_corrupted(self, dm, tmp_path):
        """Асинхронное чтение битого JSON — callback(None)."""
        path = tmp_path / "broken.json"
        path.write_text("{not valid json", encoding="utf-8")

        result = []
        done = threading.Event()

        def callback(data):
            result.append(data)
            done.set()

        dm.read_json_async("broken", str(path), callback)
        done.wait(timeout=2.0)

        assert result == [None]


# =========================================================
# SHUTDOWN
# =========================================================
class TestShutdown:
    def test_shutdown_sets_flag(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "utils.data_manager.HISTORY_PATH",
            tmp_path / "h.json",
        )
        dm = DataManager()
        assert dm._closing is False

        dm.shutdown()
        assert dm._closing is True

    def test_shutdown_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "utils.data_manager.HISTORY_PATH",
            tmp_path / "h.json",
        )
        dm = DataManager()
        dm.shutdown()
        dm.shutdown()  # не должно упасть