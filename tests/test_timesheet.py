# tests/test_timesheet.py
"""
Тесты для core/timesheet.py.

Работаем с временным timesheet.json через monkeypatch get_data_dir.
(Раньше патчили TIMESHEET_PATH, но он заменён на _timesheet_path(),
которая вычисляет путь через get_data_dir() при каждом вызове.)
"""
import json
import os
from datetime import date

import pytest

from core import timesheet as ts


# =========================================================
# FIXTURES
# =========================================================
@pytest.fixture
def tmp_timesheet(tmp_path, monkeypatch):
    """Подменяет get_data_dir на tmp_path — путь к timesheet.json
    будет tmp_path/timesheet.json."""
    monkeypatch.setattr(
        "core.timesheet.get_data_dir",
        lambda: str(tmp_path),
    )
    return tmp_path / "timesheet.json"


# =========================================================
# load_timesheet / save_timesheet
# =========================================================
class TestLoadSave:
    def test_load_missing_file(self, tmp_timesheet):
        """Нет файла — пустой словарь."""
        assert ts.load_timesheet() == {}

    def test_save_and_load(self, tmp_timesheet):
        data = {
            "2026-10-01": {"k": 9, "d": 0, "n": 0},
            "2026-10-02": {"k": 6, "d": 7, "n": 0},
        }
        assert ts.save_timesheet(data) is True

        loaded = ts.load_timesheet()
        assert loaded == data

    def test_load_broken_json(self, tmp_timesheet):
        """Битый JSON — пустой словарь."""
        with open(tmp_timesheet, "w", encoding="utf-8") as f:
            f.write("{not valid json")

        assert ts.load_timesheet() == {}

    def test_load_not_dict(self, tmp_timesheet):
        """JSON — не словарь — пустой словарь."""
        with open(tmp_timesheet, "w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)

        assert ts.load_timesheet() == {}

    def test_save_creates_dir(self, tmp_path, monkeypatch):
        """save_timesheet создаёт папку, если её нет."""
        nested_dir = tmp_path / "sub" / "dir"
        monkeypatch.setattr(
            "core.timesheet.get_data_dir",
            lambda: str(nested_dir),
        )

        data = {"2026-10-01": {"k": 1, "d": 0, "n": 0}}
        assert ts.save_timesheet(data) is True
        assert (nested_dir / "timesheet.json").exists()


# =========================================================
# make_key
# =========================================================
class TestMakeKey:
    def test_simple(self):
        assert ts.make_key(date(2026, 10, 14)) == "2026-10-14"

    def test_single_digits(self):
        assert ts.make_key(date(2026, 1, 5)) == "2026-01-05"


# =========================================================
# get_day / set_day / clear_day
# =========================================================
class TestDayOps:
    def test_get_day_none(self):
        data = {}
        assert ts.get_day(data, date(2026, 10, 14)) is None

    def test_get_day_exists(self):
        data = {"2026-10-14": {"k": 9, "d": 0, "n": 0}}
        result = ts.get_day(data, date(2026, 10, 14))
        assert result == {"k": 9, "d": 0, "n": 0}

    def test_set_day(self):
        data = {}
        ts.set_day(data, date(2026, 10, 14), 9, 0, 0)
        assert data["2026-10-14"] == {"k": 9, "d": 0, "n": 0}

    def test_set_day_overwrite(self):
        data = {"2026-10-14": {"k": 1, "d": 1, "n": 1}}
        ts.set_day(data, date(2026, 10, 14), 9, 0, 0)
        assert data["2026-10-14"] == {"k": 9, "d": 0, "n": 0}

    def test_set_day_casts_to_int(self):
        """set_day приводит к int."""
        data = {}
        ts.set_day(data, date(2026, 10, 14), "9", "0", "0")
        assert data["2026-10-14"] == {"k": 9, "d": 0, "n": 0}

    def test_clear_day(self):
        data = {"2026-10-14": {"k": 9, "d": 0, "n": 0}}
        ts.clear_day(data, date(2026, 10, 14))
        assert "2026-10-14" not in data

    def test_clear_day_missing(self):
        """Удаление несуществующего — не падает."""
        data = {}
        ts.clear_day(data, date(2026, 10, 14))
        assert data == {}


# =========================================================
# format_for_asu
# =========================================================
class TestFormatForAsu:
    def test_all_zeros(self):
        assert ts.format_for_asu(0, 0, 0) == "К 0 Д 0 Н 0"

    def test_only_k(self):
        assert ts.format_for_asu(9, 0, 0) == "К 9 Д 0 Н 0"

    def test_all_three(self):
        assert ts.format_for_asu(6, 7, 2) == "К 6 Д 7 Н 2"

    def test_large_numbers(self):
        assert ts.format_for_asu(100, 200, 300) == "К 100 Д 200 Н 300"

    def test_string_input(self):
        """Строки приводятся к int."""
        assert ts.format_for_asu("9", "0", "0") == "К 9 Д 0 Н 0"


# =========================================================
# get_asu_string
# =========================================================
class TestGetAsuString:
    def test_missing_day(self):
        data = {}
        assert ts.get_asu_string(data, date(2026, 10, 14)) == "К 0 Д 0 Н 0"

    def test_existing_day(self):
        data = {"2026-10-14": {"k": 9, "d": 0, "n": 0}}
        assert ts.get_asu_string(data, date(2026, 10, 14)) == "К 9 Д 0 Н 0"

    def test_existing_day_all_three(self):
        data = {"2026-10-14": {"k": 6, "d": 7, "n": 2}}
        assert ts.get_asu_string(data, date(2026, 10, 14)) == "К 6 Д 7 Н 2"

    def test_partial_record(self):
        """Запись без некоторых полей — берём 0."""
        data = {"2026-10-14": {"k": 9}}
        assert ts.get_asu_string(data, date(2026, 10, 14)) == "К 9 Д 0 Н 0"