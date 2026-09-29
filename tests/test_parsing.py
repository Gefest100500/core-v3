# tests/test_parsing.py
"""
Тесты для utils/parsing.py.

Проверяем:
- to_float_ru: русские числа
- to_float: простой парсинг
- norm_number: нормализация номеров
- find_column_ci: поиск столбца
- sum_values: сумма значений
"""
import pandas as pd
import pytest

from utils.parsing import (
    to_float_ru, to_float, norm_number, find_column_ci, sum_values
)


# =========================================================
# to_float_ru
# =========================================================
class TestToFloatRu:
    def test_simple_int(self):
        assert to_float_ru("1234") == 1234.0

    def test_russian_decimal(self):
        assert to_float_ru("1234,56") == 1234.56

    def test_thousands_with_space(self):
        assert to_float_ru("1 234 567,89") == 1234567.89

    def test_thousands_with_nbsp(self):
        assert to_float_ru("1\xa0234\xa0567,89") == 1234567.89

    def test_english_decimal(self):
        assert to_float_ru("1234.56") == 1234.56

    def test_negative(self):
        assert to_float_ru("-1234,56") == -1234.56

    def test_none(self):
        assert to_float_ru(None) is None

    def test_empty_string(self):
        assert to_float_ru("") is None
        assert to_float_ru("   ") is None

    def test_garbage(self):
        assert to_float_ru("abc") is None

    def test_nan(self):
        assert to_float_ru(float("nan")) is None

    def test_currency_suffix(self):
        assert to_float_ru("1234,56 руб") == 1234.56

    def test_mixed_decimal_dot_dot(self):
        # "1.234.567,89" — точки тысячи, запятая десятичная
        assert to_float_ru("1.234.567,89") == 1234567.89


# =========================================================
# to_float
# =========================================================
class TestToFloat:
    def test_simple(self):
        assert to_float("1234.56") == 1234.56

    def test_comma(self):
        assert to_float("1234,56") == 1234.56

    def test_int(self):
        assert to_float(1234) == 1234.0

    def test_none(self):
        assert to_float(None) is None

    def test_empty(self):
        assert to_float("") is None

    def test_garbage(self):
        assert to_float("abc") is None


# =========================================================
# norm_number
# =========================================================
class TestNormNumber:
    def test_simple(self):
        assert norm_number("12345") == "12345"

    def test_with_dot_zero(self):
        assert norm_number("12345.0") == "12345"

    def test_with_spaces(self):
        assert norm_number("  12345  ") == "12345"

    def test_none(self):
        assert norm_number(None) == ""

    def test_empty(self):
        assert norm_number("") == ""

    def test_int(self):
        assert norm_number(12345) == "12345"

    def test_float(self):
        # str(12345.0) = "12345.0" → "12345"
        assert norm_number(12345.0) == "12345"


# =========================================================
# find_column_ci
# =========================================================
class TestFindColumnCi:
    def test_exact_match(self):
        df = pd.DataFrame({"Код ТП": [1], "Наименование": [2]})
        assert find_column_ci(df, "Код ТП") == "Код ТП"

    def test_case_insensitive(self):
        df = pd.DataFrame({"Код ТП": [1]})
        assert find_column_ci(df, "код тп") == "Код ТП"

    def test_yo_to_e(self):
        df = pd.DataFrame({"Наименование ТП": [1]})
        assert find_column_ci(df, "Наименование ТП") == "Наименование ТП"

    def test_spaces(self):
        df = pd.DataFrame({"Код ТП": [1]})
        assert find_column_ci(df, " Код ТП ") == "Код ТП"

    def test_not_found(self):
        df = pd.DataFrame({"Код ТП": [1]})
        assert find_column_ci(df, "Нет такого") is None


# =========================================================
# sum_values
# =========================================================
class TestSumValues:
    def test_simple_sum(self):
        values = {"a": "100", "b": "200", "c": "300"}
        assert sum_values(values, ["a", "b", "c"]) == 600.0

    def test_with_comma(self):
        values = {"a": "100,5", "b": "200,5"}
        assert sum_values(values, ["a", "b"]) == 301.0

    def test_missing_key_returns_none(self):
        values = {"a": "100"}
        assert sum_values(values, ["a", "b"]) is None

    def test_invalid_value_returns_none(self):
        values = {"a": "abc"}
        assert sum_values(values, ["a"]) is None

    def test_empty_keys(self):
        values = {"a": "100"}
        assert sum_values(values, []) is None