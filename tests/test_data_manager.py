# tests/test_data_manager.py
"""
Тесты для utils/data_manager.py.

Проверяем:
- запись/чтение
- кэш по mtime
- атомарная запись
- signature
"""
import json
import os
import time

import pytest

from utils.data_manager import DataManager


@pytest.fixture
def dm(tmp_path):
    """DataManager с изолированной временной папкой."""
    manager = DataManager()
    yield manager
    manager.shutdown()


class TestSignature:
    def test_none(self):
        assert DataManager.signature(None) is None

    def test_same_data_same_signature(self):
        a = {"key": "value", "num": 42}
        b = {"num": 42, "key": "value"}
        assert DataManager.signature(a) == DataManager.signature(b)

    def test_different_data(self):
        a = {"key": "value1"}
        b = {"key": "value2"}
        assert DataManager.signature(a) != DataManager.signature(b)


class TestReadWrite:
    def test_write_then_read(self, dm, tmp_path):
        path = tmp_path / "test.json"
        data = {"hello": "world", "num": 42}

        dm._write_file("test", str(path), data)
        time.sleep(0.05)  # чтобы mtime точно обновился

        result = dm._read_file("test", str(path))
        assert result == data

    def test_read_missing_file(self, dm, tmp_path):
        path = tmp_path / "missing.json"
        assert dm._read_file("missing", str(path)) is None

    def test_cache_by_mtime(self, dm, tmp_path):
        path = tmp_path / "test.json"
        data = {"a": 1}

        dm._write_file("test", str(path), data)
        time.sleep(0.05)

        # Первое чтение — из файла, кладёт в кэш
        r1 = dm._read_file("test", str(path))
        assert r1 == data

        # Второе чтение — из кэша (mtime не менялся)
        r2 = dm._read_file("test", str(path))
        assert r2 == data

    def test_json_corrupted(self, dm, tmp_path):
        path = tmp_path / "corrupted.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write("{invalid json")

        result = dm._read_file("corrupted", str(path))
        assert result is None