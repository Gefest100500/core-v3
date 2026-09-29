# tests/test_formatting.py
"""
Тесты для utils/formatting.py.
"""
import pytest

from utils.formatting import format_number_ru, format_percent_ru


class TestFormatNumberRu:
    def test_simple_int(self):
        assert format_number_ru(1234) == "1 234,00"

    def test_thousands(self):
        assert format_number_ru(1234567) == "1 234 567,00"

    def test_with_kopecks(self):
        assert format_number_ru(1234.56) == "1 234,56"

    def test_negative(self):
        assert format_number_ru(-1234.56) == "-1 234,56"

    def test_zero(self):
        assert format_number_ru(0) == "0,00"

    def test_round_up(self):
        # 1234.999 → 1235.00
        assert format_number_ru(1234.999) == "1 235,00"

    def test_invalid(self):
        # не число — возвращаем str
        assert format_number_ru("abc") == "abc"


class TestFormatPercentRu:
    def test_simple(self):
        assert format_percent_ru(12.3456) == "12,35"

    def test_zero_decimals(self):
        assert format_percent_ru(12.3456, decimals=0) == "12"

    def test_negative(self):
        assert format_percent_ru(-5.5) == "-5,50"

    def test_invalid(self):
        assert format_percent_ru("abc") == "abc"