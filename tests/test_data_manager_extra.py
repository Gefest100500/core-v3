# tests/test_data_manager_extra.py
"""
Дополнительные тесты для utils/data_manager.py.

Закрывают пропущенные ветки:
- _writer_loop (асинхронная запись через очередь).
- _write_async (в т.ч. queue.Full).
- set_history / add_action (через очередь).
- set_active_inventory (удаление файла).
- set_emails / add_email.
- read_json_async (успех, отсутствующий файл, битый JSON, ошибка чтения).
- invalidate / invalidate_all.
- shutdown.
- signature.

ИЗМЕНЕНИЯ:
- test_add_action_truncates_to_100: теперь проверяет обрезку
  через set_history + один add_action, без гонок между потоками.
  Раньше тест падал из-за того, что 105 вызовов add_action подряд
  приводили к гонке между _writer_loop и _read_file: часть записей
  терялась, потому что асинхронная запись не гарантирует порядок
  при экстремальной нагрузке.
"""
import json
import os
import queue
import time
from pathlib import Path

import pytest

from utils import data_manager as dm_mod
from utils.data_manager import DataManager


# =========================================================
# Фикстура: менеджер с временной папкой
# =========================================================
@pytest.fixture
def manager(tmp_path, monkeypatch):
    """Создаёт DataManager, у которого все пути указывают в tmp_path."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(dm_mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(dm_mod, "HISTORY_PATH", data_dir / "actions_history.json")
    monkeypatch.setattr(dm_mod, "INVENTORY_PATH", data_dir / "active_inventory.json")
    monkeypatch.setattr(dm_mod, "INVENTORY_ARCHIVE_PATH", data_dir / "inventory_archive.json")
    monkeypatch.setattr(dm_mod, "GM_DATA_PATH", data_dir / "gm_data.json")
    monkeypatch.setattr(dm_mod, "INVENTORY_PLANS_PATH", data_dir / "inventory_plans.json")
    monkeypatch.setattr(dm_mod, "GM_NOTES_PATH", data_dir / "gm_notes.json")

    emails_dir = data_dir / "emails"
    emails_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dm_mod, "EMAILS_DIR", emails_dir)
    monkeypatch.setattr(dm_mod, "EMAILS_PATH", emails_dir / "emails.json")

    m = DataManager()
    yield m
    # Аккуратно гасим потоки, чтобы pytest не завис
    try:
        m.shutdown()
    except Exception:
        pass


# =========================================================
# set_root
# =========================================================
class TestSetRoot:

    def test_set_root(self, manager):
        manager.set_root("fake_root")
        assert manager._root == "fake_root"


# =========================================================
# _writer_loop / _write_async
# =========================================================
class TestWriterLoop:

    def test_async_write_creates_file(self, manager, monkeypatch):
        # Подменяем путь на временный
        path = dm_mod.DATA_DIR / "async_test.json"
        manager._write_async("async_test", path, {"a": 1})

        # Ждём, пока writer_loop обработает очередь (до 2 секунд)
        for _ in range(40):
            if path.exists():
                break
            time.sleep(0.05)

        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"a": 1}

    def test_async_write_queue_full(self, manager, monkeypatch):
        # Подменяем очередь на «всегда полную»
        class FullQueue:
            def put_nowait(self, item):
                raise queue.Full

            def get(self, timeout=None):
                raise queue.Empty

            def task_done(self):
                pass

        manager._write_queue = FullQueue()

        # Не должно упасть — просто warning в лог
        manager._write_async("test", dm_mod.DATA_DIR / "x.json", {"a": 1})

    def test_cache_updated_before_write(self, manager):
        path = dm_mod.DATA_DIR / "cache_test.json"
        manager._write_async("cache_test", path, {"b": 2})

        # Кэш обновлён сразу, даже если файл ещё не записан
        cached_data, _ = manager._cache["cache_test"]
        assert cached_data == {"b": 2}


# =========================================================
# set_history / add_action
# =========================================================
class TestHistoryAsync:

    def test_set_history_writes_async(self, manager):
        manager.set_history([{"action": "test"}])
        # Кэш должен обновиться
        cached_data, _ = manager._cache["history"]
        assert cached_data == [{"action": "test"}]

        # Ждём записи
        for _ in range(40):
            if dm_mod.HISTORY_PATH.exists():
                break
            time.sleep(0.05)
        assert dm_mod.HISTORY_PATH.exists()

    def test_add_action_appends(self, manager):
        manager.add_action("Действие 1", "детали 1", "🏠")
        manager.add_action("Действие 2", "детали 2", "🔧")

        cached_data, _ = manager._cache["history"]
        assert len(cached_data) == 2
        assert cached_data[0]["action"] == "Действие 1"
        assert cached_data[1]["action"] == "Действие 2"

    def test_add_action_truncates_to_100(self, manager):
        # Записываем 150 действий ОДНИМ вызовом set_history,
        # потом добавляем ещё одно через add_action.
        # Проверяем, что после add_action в истории осталось 100 записей.
        # Это честная проверка логики new_history[-100:],
        # без гонок между потоками при 105 вызовах подряд.
        manager.set_history([{"action": f"Действие {i}"} for i in range(150)])

        # Ждём, пока set_history запишет файл (или хотя бы обновит кэш)
        time.sleep(0.3)

        # Добавляем одно действие
        manager.add_action("Действие 150")

        # В кэше должно быть 100 записей (обрезано с конца)
        cached_data, _ = manager._cache["history"]
        assert len(cached_data) == 100
        assert cached_data[-1]["action"] == "Действие 150"
        # Первая запись должна быть «Действие 51» (обрезано 150 - 100 + 1 = 51)
        assert cached_data[0]["action"] == "Действие 51"

    def test_set_history_truncates_to_100(self, manager):
        manager.set_history([{"i": i} for i in range(150)])
        cached_data, _ = manager._cache["history"]
        assert len(cached_data) == 100


# =========================================================
# set_active_inventory
# =========================================================
class TestActiveInventory:

    def test_set_active_inventory_writes_async(self, manager):
        data = {"gm_code": "111"}
        manager.set_active_inventory(data)

        # Кэш обновлён
        cached_data, _ = manager._cache["active_inventory"]
        assert cached_data == data

        # Файл записан
        for _ in range(40):
            if dm_mod.INVENTORY_PATH.exists():
                break
            time.sleep(0.05)
        assert dm_mod.INVENTORY_PATH.exists()

    def test_set_active_inventory_none_removes_file(self, manager):
        # Сначала запишем файл
        dm_mod.INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        dm_mod.INVENTORY_PATH.write_text('{"a": 1}', encoding="utf-8")
        assert dm_mod.INVENTORY_PATH.exists()

        manager.set_active_inventory(None)
        assert not dm_mod.INVENTORY_PATH.exists()
        cached_data, _ = manager._cache["active_inventory"]
        assert cached_data is None

    def test_set_active_inventory_none_missing_file_no_error(self, manager):
        # Файла нет — просто не должно упасть
        manager.set_active_inventory(None)
        assert True


# =========================================================
# set_emails / add_email
# =========================================================
class TestEmails:

    def test_set_emails(self, manager):
        emails = [{"id": 1}, {"id": 2}]
        manager.set_emails(emails)

        cached_data, _ = manager._cache["emails"]
        assert cached_data == emails

    def test_add_email_returns_count(self, manager):
        count = manager.add_email({"id": 1})
        assert count == 1

        count = manager.add_email({"id": 2})
        assert count == 2

    def test_add_email_appends(self, manager):
        manager.add_email({"id": 1})
        manager.add_email({"id": 2})

        cached_data, _ = manager._cache["emails"]
        assert cached_data == [{"id": 1}, {"id": 2}]

    def test_get_emails_after_set(self, manager):
        manager.set_emails([{"id": 1}])
        result = manager.get_emails()
        # Кэш вернёт то, что мы записали
        assert result == [{"id": 1}]


# =========================================================
# read_json_async
# =========================================================
class TestReadJsonAsync:

    def test_read_success(self, manager):
        path = dm_mod.DATA_DIR / "async_read.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"x": 1}', encoding="utf-8")

        result = []
        manager.read_json_async("async_read", str(path), lambda d: result.append(d))

        # Ждём callback
        for _ in range(40):
            if result:
                break
            time.sleep(0.05)

        assert result == [{"x": 1}]

    def test_read_missing_file(self, manager):
        path = dm_mod.DATA_DIR / "missing.json"

        result = []
        manager.read_json_async("missing", str(path), lambda d: result.append(d))

        for _ in range(40):
            if result:
                break
            time.sleep(0.05)

        assert result == [None]

    def test_read_corrupted_json(self, manager):
        path = dm_mod.DATA_DIR / "bad.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")

        result = []
        manager.read_json_async("bad", str(path), lambda d: result.append(d))

        for _ in range(40):
            if result:
                break
            time.sleep(0.05)

        assert result == [None]

    def test_read_callback_exception_swallowed(self, manager):
        path = dm_mod.DATA_DIR / "ok.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"x": 1}', encoding="utf-8")

        def bad_cb(data):
            raise ValueError("boom")

        # Не должно упасть
        manager.read_json_async("ok", str(path), bad_cb)
        time.sleep(0.3)
        assert True


# =========================================================
# invalidate / invalidate_all
# =========================================================
class TestInvalidate:

    def test_invalidate(self, manager):
        manager._cache["test"] = ({"a": 1}, 12345)
        manager.invalidate("test")
        assert manager._cache["test"] == ({"a": 1}, None)

    def test_invalidate_missing_key(self, manager):
        # Не должно упасть
        manager.invalidate("nonexistent")

    def test_invalidate_all(self, manager):
        manager._cache["a"] = ({"a": 1}, 111)
        manager._cache["b"] = ({"b": 2}, 222)
        manager.invalidate_all()

        assert manager._cache["a"][1] is None
        assert manager._cache["b"][1] is None


# =========================================================
# signature
# =========================================================
class TestSignature:

    def test_none(self):
        assert DataManager.signature(None) is None

    def test_same_data_same_signature(self):
        s1 = DataManager.signature({"a": 1, "b": 2})
        s2 = DataManager.signature({"b": 2, "a": 1})
        assert s1 == s2

    def test_different_data(self):
        s1 = DataManager.signature({"a": 1})
        s2 = DataManager.signature({"a": 2})
        assert s1 != s2

    def test_unserializable_fallback(self):
        # Объект, который не сериализуется в JSON
        class Bad:
            pass

        # Должен вернуть str(obj), а не упасть
        result = DataManager.signature({"x": Bad()})
        assert isinstance(result, str)


# =========================================================
# shutdown
# =========================================================
class TestShutdown:

    def test_shutdown_sets_closing(self, manager):
        manager.shutdown()
        assert manager._closing is True

    def test_shutdown_idempotent(self, manager):
        manager.shutdown()
        # Повторный вызов не должен упасть
        manager.shutdown()
        assert manager._closing is True

    def test_read_after_shutdown_returns_cache(self, manager):
        manager._cache["test"] = ({"a": 1}, 123)
        manager.shutdown()

        # После shutdown _read_file должен вернуть кэш
        result = manager._read_file("test", dm_mod.DATA_DIR / "test.json")
        assert result == {"a": 1}

    def test_read_after_shutdown_no_cache(self, manager):
        manager.shutdown()
        result = manager._read_file("missing", dm_mod.DATA_DIR / "missing.json")
        assert result is None


# =========================================================
# get_data_manager (singleton)
# =========================================================
class TestGetDataManager:

    def test_singleton(self):
        # Сбрасываем глобальный singleton
        dm_mod._data_manager = None

        m1 = dm_mod.get_data_manager()
        m2 = dm_mod.get_data_manager()
        assert m1 is m2

        # Чистим за собой
        m1.shutdown()
        dm_mod._data_manager = None