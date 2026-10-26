# tests/test_excel_utils.py
"""
Тесты для utils/excel_utils.py.

Проверяем:
- safe_filename: очистка имени от запрещённых символов
- autofit_columns: подгонка ширины колонок (через реальный файл)

Раньше эти тесты жили в test_brak_util_analyzer.py — теперь здесь,
потому что функции переехали в utils/excel_utils.py.
"""
import os

import pytest

from utils.excel_utils import safe_filename, autofit_columns


# =========================================================
# safe_filename
# =========================================================
class TestSafeFilename:
    def test_simple(self):
        assert safe_filename("Волжск 1") == "Волжск 1"

    def test_bad_chars(self):
        result = safe_filename('ГМ/Волжск:1*')
        assert "/" not in result
        assert ":" not in result
        assert "*" not in result

    def test_all_bad_chars(self):
        # Windows запрещает: \ / : * ? " < > |
        result = safe_filename('a\\b/c:d*e?f"g<h>i|j')
        for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
            assert ch not in result

    def test_empty(self):
        assert safe_filename("") == "без_названия"

    def test_only_spaces(self):
        assert safe_filename("   ") == "без_названия"

    def test_only_bad_chars(self):
        # Все символы заменятся на _, но .strip() не уберёт _
        # → результат "_________"
        result = safe_filename('\\\\/:*?"<>|')
        assert result != ""
        assert "\\" not in result
        assert "/" not in result

    def test_strip_spaces(self):
        assert safe_filename("  Волжск 1  ") == "Волжск 1"

    def test_none_like(self):
        # str(None) → "None", не пустая строка
        assert safe_filename(None) == "None"

    def test_int(self):
        assert safe_filename(12345) == "12345"


# =========================================================
# autofit_columns
# =========================================================
class TestAutofitColumns:
    """Тесты на реальном Excel-файле (создаём через pandas)."""

    def test_file_not_exists(self, tmp_path):
        """Если файла нет — функция тихо выходит, не падая."""
        missing = tmp_path / "no_such_file.xlsx"
        # Не должно быть исключения
        autofit_columns(str(missing))

    def test_basic_file(self, tmp_path):
        """Простой файл — ширина колонок выставляется."""
        import pandas as pd
        from openpyxl import load_workbook

        path = tmp_path / "test.xlsx"
        df = pd.DataFrame({
            "Короткий": ["a", "b", "c"],
            "Очень длинное название колонки": [1, 2, 3],
        })
        df.to_excel(path, index=False)

        autofit_columns(str(path))

        wb = load_workbook(str(path))
        ws = wb.active

        # Проверяем, что ширины установлены
        for col_letter in ("A", "B"):
            assert ws.column_dimensions[col_letter].width > 0

    def test_min_width(self, tmp_path):
        """Минимальная ширина — 8."""
        import pandas as pd
        from openpyxl import load_workbook

        path = tmp_path / "test_min.xlsx"
        df = pd.DataFrame({"A": ["x"]})
        df.to_excel(path, index=False)

        autofit_columns(str(path), min_width=20)

        wb = load_workbook(str(path))
        ws = wb.active
        assert ws.column_dimensions["A"].width == 20

    def test_max_width(self, tmp_path):
        """Максимальная ширина — обрезает длинный текст."""
        import pandas as pd
        from openpyxl import load_workbook

        path = tmp_path / "test_max.xlsx"
        long_text = "a" * 200
        df = pd.DataFrame({"A": [long_text]})
        df.to_excel(path, index=False)

        autofit_columns(str(path), max_width=30)

        wb = load_workbook(str(path))
        ws = wb.active
        assert ws.column_dimensions["A"].width == 30