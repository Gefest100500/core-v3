# tests/test_brak_util_analyzer_run.py
"""
Тесты для BrakUtilAnalyzer.run() — полный процесс.

Создаём временные Excel-файлы, запускаем run(), проверяем результат.
"""
import os
import zipfile

import pandas as pd
import pytest

from core.brak_util_analyzer import (
    BrakUtilAnalyzer,
    COL_NUMBER_F1,
    COL_SUM_F1,
    COL_NUMBER_F2,
    COL_SUM_F2,
    COL_NO_CHANGES,
    COL_NOTE,
)


# =========================================================
# FIXTURES
# =========================================================
@pytest.fixture
def analyzer():
    return BrakUtilAnalyzer()


@pytest.fixture
def tmp_output(tmp_path, monkeypatch):
    """Подменяет FOLDERS['brak_util'] на временную папку."""
    out_dir = tmp_path / "brak_output"
    out_dir.mkdir()

    monkeypatch.setattr(
        "core.brak_util_analyzer.FOLDERS",
        {"brak_util": str(out_dir)},
        raising=False,
    )
    return out_dir


def _make_file1(tmp_path, rows):
    """Создаёт файл «Выборочная проверка...»."""
    path = tmp_path / "file1.xlsx"
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return str(path)


def _make_file2(tmp_path, rows):
    """Создаёт файл «Операции списания»."""
    path = tmp_path / "file2.xlsx"
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return str(path)


def _make_valid_file1(tmp_path, numbers_sums):
    """Создаёт файл 1 с нужными колонками.

    numbers_sums: список (номер, сумма).
    """
    rows = []
    for num, s in numbers_sums:
        rows.append({
            COL_NUMBER_F1: num,
            COL_SUM_F1: s,
            COL_NO_CHANGES: None,
            COL_NOTE: None,
        })
    return _make_file1(tmp_path, rows)


def _make_valid_file2(tmp_path, numbers_sums):
    """Создаёт файл 2 с нужными колонками."""
    rows = []
    for num, s in numbers_sums:
        rows.append({
            COL_NUMBER_F2: num,
            COL_SUM_F2: s,
        })
    return _make_file2(tmp_path, rows)


# =========================================================
# БАЗОВЫЕ ТЕСТЫ
# =========================================================
class TestRunBasic:
    def test_run_ok(self, analyzer, tmp_path, tmp_output):
        """Простой случай: одна строка, всё совпадает."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])
        f2 = _make_valid_file2(tmp_path, [("001", 1000.0)])

        result = analyzer.run(f1, f2, "Тестовый ГМ")

        assert result["success"] is True
        assert result["total"] == 1
        assert len(result["discrepancies"]) == 0
        assert os.path.isfile(result["file"])

    def test_run_missing_file(self, analyzer, tmp_path, tmp_output):
        """Несуществующий файл — исключение."""
        f2 = _make_valid_file2(tmp_path, [("001", 1000.0)])

        with pytest.raises(RuntimeError, match="Не удалось прочитать файл 1"):
            analyzer.run("nonexistent.xlsx", f2, "ГМ")

    def test_run_missing_file2(self, analyzer, tmp_path, tmp_output):
        """Несуществующий файл 2 — исключение."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])

        with pytest.raises(RuntimeError, match="Не удалось прочитать файл 2"):
            analyzer.run(f1, "nonexistent.xlsx", "ГМ")

    def test_run_missing_columns_f1(self, analyzer, tmp_path, tmp_output):
        """В файле 1 нет нужных колонок — исключение."""
        # Файл 1 без колонки COL_NO_CHANGES
        path = tmp_path / "bad1.xlsx"
        pd.DataFrame([{COL_NUMBER_F1: "001", COL_SUM_F1: 1000.0}]).to_excel(
            path, index=False
        )

        f2 = _make_valid_file2(tmp_path, [("001", 1000.0)])

        with pytest.raises(RuntimeError, match="нет столбцов"):
            analyzer.run(str(path), f2, "ГМ")

    def test_run_missing_columns_f2(self, analyzer, tmp_path, tmp_output):
        """В файле 2 нет нужных колонок — исключение."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])

        path = tmp_path / "bad2.xlsx"
        pd.DataFrame([{COL_NUMBER_F2: "001"}]).to_excel(path, index=False)

        with pytest.raises(RuntimeError, match="нет столбцов"):
            analyzer.run(f1, str(path), "ГМ")


# =========================================================
# СВЕРКА СУММ
# =========================================================
class TestSumComparison:
    def test_exact_match(self, analyzer, tmp_path, tmp_output):
        """Точное совпадение — нет расхождений."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])
        f2 = _make_valid_file2(tmp_path, [("001", 1000.0)])

        result = analyzer.run(f1, f2, "ГМ")
        assert len(result["discrepancies"]) == 0

    def test_within_tolerance(self, analyzer, tmp_path, tmp_output):
        """Разница < BRAK_UTIL_TOLERANCE — ок."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])
        # Разница 0.01 руб — обычно в пределах допуска
        f2 = _make_valid_file2(tmp_path, [("001", 1000.01)])

        result = analyzer.run(f1, f2, "ГМ")
        assert len(result["discrepancies"]) == 0

    def test_mismatch(self, analyzer, tmp_path, tmp_output):
        """Большая разница — расхождение."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])
        f2 = _make_valid_file2(tmp_path, [("001", 5000.0)])

        result = analyzer.run(f1, f2, "ГМ")
        assert len(result["discrepancies"]) == 1
        assert result["discrepancies"][0]["number"] == "001"
        assert "Расхождение" in result["discrepancies"][0]["reason"]

    def test_no_in_operations(self, analyzer, tmp_path, tmp_output):
        """Номер есть в файле 1, но нет в файле 2."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])
        f2 = _make_valid_file2(tmp_path, [("002", 1000.0)])

        result = analyzer.run(f1, f2, "ГМ")
        assert len(result["discrepancies"]) == 1
        assert result["discrepancies"][0]["reason"] == "Нет в операциях"

    def test_multiple_operations_sum(self, analyzer, tmp_path, tmp_output):
        """Несколько операций с одним номером — суммы складываются."""
        f1 = _make_valid_file1(tmp_path, [("001", 300.0)])
        f2 = _make_valid_file2(tmp_path, [
            ("001", 100.0),
            ("001", 200.0),
        ])

        result = analyzer.run(f1, f2, "ГМ")
        # 100 + 200 = 300 — совпадает
        assert len(result["discrepancies"]) == 0


# =========================================================
# FILL COLUMNS
# =========================================================
class TestFillColumns:
    def test_fill_ok(self, analyzer, tmp_path, tmp_output):
        """Проверяем, что после run() в файле появились Да/Нет."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])
        f2 = _make_valid_file2(tmp_path, [("001", 1000.0)])

        result = analyzer.run(f1, f2, "ГМ")

        # Читаем результат
        df = pd.read_excel(result["file"])
        assert df[COL_NO_CHANGES].iloc[0] == "Да"
        assert df[COL_NOTE].iloc[0] == "Нет"

    def test_fill_mismatch(self, analyzer, tmp_path, tmp_output):
        """Расхождение — в файле 'Нет' и 'Есть расхождения'."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])
        f2 = _make_valid_file2(tmp_path, [("001", 5000.0)])

        result = analyzer.run(f1, f2, "ГМ")
        df = pd.read_excel(result["file"])

        assert df[COL_NO_CHANGES].iloc[0] == "Нет"
        assert df[COL_NOTE].iloc[0] == "Есть расхождения"

    def test_fill_no_in_ops(self, analyzer, tmp_path, tmp_output):
        """Нет в операциях — 'Нет' и 'Нет в операциях'."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])
        f2 = _make_valid_file2(tmp_path, [("002", 1000.0)])

        result = analyzer.run(f1, f2, "ГМ")
        df = pd.read_excel(result["file"])

        assert df[COL_NO_CHANGES].iloc[0] == "Нет"
        assert df[COL_NOTE].iloc[0] == "Нет в операциях"


# =========================================================
# ПРОЧЕЕ
# =========================================================
class TestMisc:
    def test_progress_callback(self, analyzer, tmp_path, tmp_output):
        """Progress callback вызывается."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])
        f2 = _make_valid_file2(tmp_path, [("001", 1000.0)])

        calls = []

        def callback(value, message=None):
            calls.append((value, message))

        analyzer.run(f1, f2, "ГМ", progress_callback=callback)
        assert len(calls) > 0
        # Проверяем, что callback доходит до 1.0
        values = [c[0] for c in calls]
        assert max(values) == 1.0

    def test_zip_created(self, analyzer, tmp_path, tmp_output):
        """Архив .zip создаётся."""
        f1 = _make_valid_file1(tmp_path, [("001", 1000.0)])
        f2 = _make_valid_file2(tmp_path, [("001", 1000.0)])

        result = analyzer.run(f1, f2, "ГМ")
        assert result["zip"] is not None
        assert os.path.isfile(result["zip"])
        assert zipfile.is_zipfile(result["zip"])

    def test_empty_number_skipped(self, analyzer, tmp_path, tmp_output):
        """Пустой номер в файле 1 — пропускаем."""
        f1 = _make_valid_file1(tmp_path, [("", 1000.0)])
        f2 = _make_valid_file2(tmp_path, [("001", 1000.0)])

        result = analyzer.run(f1, f2, "ГМ")
        # Пустой номер не считается расхождением
        assert len(result["discrepancies"]) == 0

    def test_total_count(self, analyzer, tmp_path, tmp_output):
        """total = число строк в файле 1."""
        f1 = _make_valid_file1(tmp_path, [
            ("001", 1000.0),
            ("002", 2000.0),
            ("003", 3000.0),
        ])
        f2 = _make_valid_file2(tmp_path, [("001", 1000.0)])

        result = analyzer.run(f1, f2, "ГМ")
        assert result["total"] == 3