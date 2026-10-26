# core/timesheet.py
"""
Табель ревизора.

Логика работы с табелем:
- загрузка/сохранение из data/timesheet.json (через get_data_dir())
- формат строки для АСУЗ: "К X Д Y Н Z"
- ключ: "YYYY-MM-DD"

Формат JSON:
{
    "2026-10-01": {"k": 9, "d": 0, "n": 0},
    "2026-10-02": {"k": 6, "d": 7, "n": 0}
}

ИЗМЕНЕНИЯ:
- TIMESHEET_PATH больше не константа на уровне модуля. Путь вычисляется
  функцией _timesheet_path() через get_data_dir() — данные лежат в
  %LOCALAPPDATA%/Core_V3_0/data, а не в корне проекта. Это нужно для
  работы из Program Files и для тестов через monkeypatch.
"""
import json
import os
from datetime import date, datetime
from typing import Optional

from utils.file_utils import get_data_dir
from utils.logger import log


# =========================================================
# ПУТЬ К ФАЙЛУ
# =========================================================
def _timesheet_path() -> str:
    """Путь к timesheet.json в папке данных (%LOCALAPPDATA%)."""
    return os.path.join(get_data_dir(), "timesheet.json")


# =========================================================
# ЗАГРУЗКА / СОХРАНЕНИЕ
# =========================================================
def load_timesheet() -> dict:
    """Загружает табель из JSON. Если файла нет — пустой словарь."""
    path = _timesheet_path()
    if not os.path.isfile(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            log.warning("timesheet.json должен быть словарём — игнорирую")
            return {}
        return data
    except (json.JSONDecodeError, IOError) as e:
        log.error(f"Ошибка чтения timesheet.json: {e}")
        return {}


def save_timesheet(data: dict) -> bool:
    """Сохраняет табель в JSON. Атомарно (tmp + replace)."""
    path = _timesheet_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)

        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        os.replace(tmp_path, path)
        return True
    except Exception as e:
        log.exception(f"Ошибка записи timesheet.json: {e}")
        return False


# =========================================================
# РАБОТА С ДНЯМИ
# =========================================================
def make_key(d: date) -> str:
    """Ключ дня: 'YYYY-MM-DD'."""
    return d.strftime("%Y-%m-%d")


def get_day(data: dict, d: date) -> Optional[dict]:
    """Возвращает запись за день или None."""
    return data.get(make_key(d))


def set_day(data: dict, d: date, k: int, d_val: int, n: int) -> dict:
    """Устанавливает значения за день. Возвращает обновлённый словарь."""
    data[make_key(d)] = {"k": int(k), "d": int(d_val), "n": int(n)}
    return data


def clear_day(data: dict, d: date) -> dict:
    """Удаляет запись за день."""
    data.pop(make_key(d), None)
    return data


# =========================================================
# ФОРМАТ ДЛЯ АСУЗ
# =========================================================
def format_for_asu(k: int, d: int, n: int) -> str:
    """Строка для АСУЗ: 'К 9 Д 0 Н 0'.

    Всегда три части. Нули пишутся явно.
    """
    return f"К {int(k)} Д {int(d)} Н {int(n)}"


def get_asu_string(data: dict, d: date) -> str:
    """Строка для АСУЗ за конкретный день.

    Если дня нет в табеле — 'К 0 Д 0 Н 0'.
    """
    rec = get_day(data, d)
    if rec is None:
        return format_for_asu(0, 0, 0)
    return format_for_asu(rec.get("k", 0), rec.get("d", 0), rec.get("n", 0))