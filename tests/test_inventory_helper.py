# tests/test_inventory_helper.py
"""
Тесты для core/inventory_helper.py.

Проверяем:
- Поиск ГМ по коду.
- Работу с вариантами планов.
- Формирование пустого чек-листа.
- Расчёт даты окончания и текущего дня.
- Расчёт прогресса.
- Форматирование дат.
- Получение данных дня.
"""
from datetime import date, timedelta
import pytest

from core.inventory_helper import (
    find_gm_by_code,
    get_variant_values,
    get_variant_key_from_title,
    build_empty_checklist,
    calculate_end_date,
    calculate_days_passed,
    calculate_progress,
    format_date_ru,
    get_day_data,
)


# =========================================================
# ПОИСК ГМ
# =========================================================
@pytest.fixture
def gm_data():
    return [
        {"Код": "996411", "Название": "Балаково 3 Саратовское шоссе"},
        {"Код": "992320", "Название": "Абинск 1 Колхозная"},
    ]


class TestFindGmByCode:

    def test_found(self, gm_data):
        result = find_gm_by_code("996411", gm_data)
        assert result is not None
        assert result["Название"] == "Балаково 3 Саратовское шоссе"

    def test_found_with_spaces(self, gm_data):
        result = find_gm_by_code("  996411  ", gm_data)
        assert result is not None

    def test_not_found(self, gm_data):
        assert find_gm_by_code("000000", gm_data) is None

    def test_empty_data(self):
        assert find_gm_by_code("996411", []) is None


# =========================================================
# ВАРИАНТЫ ПЛАНОВ
# =========================================================
@pytest.fixture
def plans():
    return {
        "А": {"title": "Вариант А", "days_total": 3},
        "Б": {"title": "Вариант Б", "days_total": 4},
        "Ж": {"title": "Вариант Ж", "days_total": 5},
    }


class TestVariantValues:

    def test_returns_titles_sorted(self, plans):
        values = get_variant_values(plans)
        assert values == ["Вариант А", "Вариант Б", "Вариант Ж"]

    def test_empty_plans(self):
        values = get_variant_values({})
        assert values == ["(нет доступных вариантов)"]


class TestVariantKeyFromTitle:

    def test_found(self, plans):
        assert get_variant_key_from_title("Вариант Б", plans) == "Б"

    def test_not_found(self, plans):
        assert get_variant_key_from_title("Вариант Я", plans) is None

    def test_empty_plans(self):
        assert get_variant_key_from_title("Вариант А", {}) is None


# =========================================================
# ЧЕК-ЛИСТ
# =========================================================
class TestBuildEmptyChecklist:

    def test_structure(self):
        plan = {
            "days": [
                {"day_num": 1, "shifts": [
                    {"tasks": ["a", "b"]},
                    {"tasks": ["c"]},
                ]},
                {"day_num": 2, "shifts": [
                    {"tasks": ["d"]},
                ]},
            ]
        }
        result = build_empty_checklist(plan)
        assert result == {
            "day_1": {
                "shift_1": {"0": False, "1": False},
                "shift_2": {"0": False},
            },
            "day_2": {
                "shift_1": {"0": False},
            },
        }

    def test_empty_plan(self):
        assert build_empty_checklist({}) == {}


# =========================================================
# РАСЧЁТ ДАТ
# =========================================================
class TestCalculateEndDate:

    def test_simple(self):
        start = date(2026, 10, 20)
        end = calculate_end_date(start, 5)
        assert end == date(2026, 10, 24)

    def test_one_day(self):
        start = date(2026, 10, 20)
        end = calculate_end_date(start, 1)
        assert end == start

    def test_zero_days(self):
        start = date(2026, 10, 20)
        end = calculate_end_date(start, 0)
        assert end == start

    def test_negative_days(self):
        start = date(2026, 10, 20)
        end = calculate_end_date(start, -3)
        assert end == start


class TestCalculateDaysPassed:

    def test_today_is_start(self):
        start = date.today()
        assert calculate_days_passed(start, 5) == 1

    def test_yesterday_is_day_2(self):
        start = date.today() - timedelta(days=1)
        assert calculate_days_passed(start, 5) == 2

    def test_past_end_capped(self):
        start = date.today() - timedelta(days=10)
        assert calculate_days_passed(start, 5) == 5

    def test_zero_days_total(self):
        start = date.today()
        assert calculate_days_passed(start, 0) == 1


# =========================================================
# ПРОГРЕСС
# =========================================================
class TestCalculateProgress:

    def test_all_done(self):
        plan = {"days": [{"day_num": 1, "shifts": [{"tasks": ["a", "b"]}]}]}
        checklist = {"day_1": {"shift_1": {"0": True, "1": True}}}
        result = calculate_progress(checklist, plan)
        assert result == {"done": 2, "total": 2, "percent": 100}

    def test_half_done(self):
        plan = {"days": [{"day_num": 1, "shifts": [{"tasks": ["a", "b"]}]}]}
        checklist = {"day_1": {"shift_1": {"0": True, "1": False}}}
        result = calculate_progress(checklist, plan)
        assert result == {"done": 1, "total": 2, "percent": 50}

    def test_none_done(self):
        plan = {"days": [{"day_num": 1, "shifts": [{"tasks": ["a", "b"]}]}]}
        checklist = {}
        result = calculate_progress(checklist, plan)
        assert result == {"done": 0, "total": 2, "percent": 0}

    def test_empty_plan(self):
        result = calculate_progress({}, {})
        assert result == {"done": 0, "total": 0, "percent": 0}


# =========================================================
# ФОРМАТИРОВАНИЕ ДАТ
# =========================================================
class TestFormatDateRu:

    def test_iso_date(self):
        assert format_date_ru("2026-10-20") == "20.10.2026"

    def test_empty(self):
        assert format_date_ru("") == "—"

    def test_garbage(self):
        assert format_date_ru("not-a-date") == "not-a-date"


# =========================================================
# ДАННЫЕ ДНЯ
# =========================================================
class TestGetDayData:

    def test_found(self):
        plan = {"days": [
            {"day_num": 1, "day_name": "Первый"},
            {"day_num": 2, "day_name": "Второй"},
        ]}
        result = get_day_data(plan, 2)
        assert result["day_name"] == "Второй"

    def test_not_found(self):
        plan = {"days": [{"day_num": 1}]}
        assert get_day_data(plan, 5) is None

    def test_empty_plan(self):
        assert get_day_data({}, 1) is None