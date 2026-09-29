# tests/test_brak_util_analyzer.py
"""
Тесты для core/brak_util_analyzer.py.

Проверяем чистые функции через прямой вызов.
"""
import pytest

from core.brak_util_analyzer import BrakUtilAnalyzer


class TestSafeFilename:
    def test_simple(self):
        assert BrakUtilAnalyzer._safe_filename("Волжск 1") == "Волжск 1"

    def test_bad_chars(self):
        result = BrakUtilAnalyzer._safe_filename('ГМ/Волжск:1*')
        assert "/" not in result
        assert ":" not in result
        assert "*" not in result

    def test_empty(self):
        assert BrakUtilAnalyzer._safe_filename("") == "без_названия"


class TestFillColumns:
    def test_fill_ok(self):
        import pandas as pd
        df = pd.DataFrame({
            "Номер": ["111"],
            "Сумма операции": [100],
            "Необоснованных изменений в Акте списания нет": [None],
            "Примечание": [None],
        })

        results = [("ok", 0, None)]
        BrakUtilAnalyzer._fill_columns(df, results)

        assert df.at[0, "Необоснованных изменений в Акте списания нет"] == "Да"
        assert df.at[0, "Примечание"] == "Нет"

    def test_fill_mismatch(self):
        import pandas as pd
        df = pd.DataFrame({
            "Номер": ["111"],
            "Сумма операции": [100],
            "Необоснованных изменений в Акте списания нет": [None],
            "Примечание": [None],
        })

        results = [("mismatch", 0, 50.0)]
        BrakUtilAnalyzer._fill_columns(df, results)

        assert df.at[0, "Необоснованных изменений в Акте списания нет"] == "Нет"
        assert df.at[0, "Примечание"] == "Есть расхождения"

    def test_fill_no_in_ops(self):
        import pandas as pd
        df = pd.DataFrame({
            "Номер": ["111"],
            "Сумма операции": [100],
            "Необоснованных изменений в Акте списания нет": [None],
            "Примечание": [None],
        })

        results = [("no_in_ops", 0, None)]
        BrakUtilAnalyzer._fill_columns(df, results)

        assert df.at[0, "Примечание"] == "Нет в операциях"