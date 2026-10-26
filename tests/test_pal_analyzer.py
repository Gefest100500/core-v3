# tests/test_pal_analyzer.py
"""
Тесты для core/pal_analyzer.py.

Проверяем:
- Валидацию столбцов (_validate_columns).
- Сборку паллет из нескольких файлов.
- Расчёт отклонений и суммы.
- Обработку отсутствующих файлов / неверных столбцов.
- Создание выходного файла.
"""
import os
import pytest
import pandas as pd

from core.pal_analyzer import (
    PalAnalyzer, REQUIRED_COLUMNS, FINAL_COLUMNS, COLUMN_RENAME,
)


# =========================================================
# _validate_columns
# =========================================================
class TestValidateColumns:

    def test_all_present(self):
        df = pd.DataFrame({col: [] for col in REQUIRED_COLUMNS})
        # Не должно бросать исключение
        PalAnalyzer._validate_columns(df, "test.xlsx")

    def test_missing_column(self):
        df = pd.DataFrame({"№ паллеты": [], "Код товара": []})
        with pytest.raises(RuntimeError, match="нет столбцов"):
            PalAnalyzer._validate_columns(df, "test.xlsx")

    def test_missing_multiple(self):
        df = pd.DataFrame({"№ паллеты": []})
        with pytest.raises(RuntimeError) as exc:
            PalAnalyzer._validate_columns(df, "test.xlsx")
        # В сообщении должны быть перечислены все недостающие столбцы
        assert "Код товара" in str(exc.value)
        assert "Товар" in str(exc.value)


# =========================================================
# Вспомогательные функции для создания файлов
# =========================================================
def _make_pallet_file(path, rows):
    """Создаёт xlsx-файл с нужными столбцами и данными."""
    df = pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
    df.to_excel(path, index=False)


def _sample_rows():
    """Две строки с валидными данными."""
    return [
        {
            "№ паллеты": 1,
            "Код товара": "111",
            "Товар": "Товар А",
            "Цена": 100.0,
            "% от всех": 10.0,
            "Кол-во до": 10,
            "Кол-во после": 8,
        },
        {
            "№ паллеты": 2,
            "Код товара": "222",
            "Товар": "Товар Б",
            "Цена": 50.0,
            "% от всех": 5.0,
            "Кол-во до": 4,
            "Кол-во после": 6,
        },
    ]


# =========================================================
# run — успешный сценарий
# =========================================================
class TestRunSuccess:

    def test_single_file(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        _make_pallet_file(input_dir / "1.xlsx", _sample_rows())

        analyzer = PalAnalyzer()
        # Подменяем папку результатов, чтобы не трогать реальную
        out_dir = tmp_path / "out"
        analyzer.config = None

        # Патчим BASE_DIR через monkeypatch не нужно — просто проверим,
        # что run не падает и возвращает success.
        # Но чтобы не писать в реальную папку, сделаем так:
        import core.pal_analyzer as pal_mod
        original_base = pal_mod.BASE_DIR
        pal_mod.BASE_DIR = str(tmp_path)
        try:
            result = analyzer.run(str(input_dir))
        finally:
            pal_mod.BASE_DIR = original_base

        assert result["success"] is True
        assert "total_sum" in result
        assert os.path.isfile(result["file"])

    def test_total_sum_calculated(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Первая строка: (10-8)*100 = 200
        # Вторая строка: (4-6)*50 = -100
        # Итого: 100
        _make_pallet_file(input_dir / "1.xlsx", _sample_rows())

        analyzer = PalAnalyzer()

        import core.pal_analyzer as pal_mod
        original_base = pal_mod.BASE_DIR
        pal_mod.BASE_DIR = str(tmp_path)
        try:
            result = analyzer.run(str(input_dir))
        finally:
            pal_mod.BASE_DIR = original_base

        assert result["total_sum"] == pytest.approx(100.0)

    def test_multiple_files(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        _make_pallet_file(input_dir / "1.xlsx", _sample_rows())
        _make_pallet_file(input_dir / "2.xlsx", _sample_rows())

        analyzer = PalAnalyzer()

        import core.pal_analyzer as pal_mod
        original_base = pal_mod.BASE_DIR
        pal_mod.BASE_DIR = str(tmp_path)
        try:
            result = analyzer.run(str(input_dir))
        finally:
            pal_mod.BASE_DIR = original_base

        assert result["success"] is True
        # Сумма должна удвоиться
        assert result["total_sum"] == pytest.approx(200.0)


# =========================================================
# run — ошибки
# =========================================================
class TestRunErrors:

    def test_empty_folder(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        analyzer = PalAnalyzer()
        with pytest.raises(RuntimeError, match="нет файлов"):
            analyzer.run(str(input_dir))

    def test_nonexistent_folder(self, tmp_path):
        analyzer = PalAnalyzer()
        with pytest.raises(RuntimeError):
            analyzer.run(str(tmp_path / "nonexistent"))

    def test_none_folder(self):
        analyzer = PalAnalyzer()
        with pytest.raises(RuntimeError):
            analyzer.run(None)

    def test_missing_columns(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Файл без нужных столбцов
        df = pd.DataFrame({"Другой столбец": [1, 2]})
        df.to_excel(input_dir / "1.xlsx", index=False)

        analyzer = PalAnalyzer()

        import core.pal_analyzer as pal_mod
        original_base = pal_mod.BASE_DIR
        pal_mod.BASE_DIR = str(tmp_path)
        try:
            with pytest.raises(RuntimeError, match="нет столбцов"):
                analyzer.run(str(input_dir))
        finally:
            pal_mod.BASE_DIR = original_base

    def test_ignores_non_digit_files(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Файл с валидными данными
        _make_pallet_file(input_dir / "1.xlsx", _sample_rows())
        # Файл с нецифровым именем — должен игнорироваться
        _make_pallet_file(input_dir / "abc.xlsx", _sample_rows())
        # Файл без расширения — тоже
        (input_dir / "2.txt").write_text("не excel", encoding="utf-8")

        analyzer = PalAnalyzer()

        import core.pal_analyzer as pal_mod
        original_base = pal_mod.BASE_DIR
        pal_mod.BASE_DIR = str(tmp_path)
        try:
            result = analyzer.run(str(input_dir))
        finally:
            pal_mod.BASE_DIR = original_base

        # Должен обработать только 1.xlsx
        assert result["total_sum"] == pytest.approx(100.0)