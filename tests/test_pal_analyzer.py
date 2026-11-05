# tests/test_pal_analyzer.py
"""
Тесты для core/pal_analyzer.py.

Проверяем:
- Сборку паллет из нескольких файлов (XXXXXX.xls).
- № паллета берётся из имени файла.
- Расчёт Отклонения; Сумма всегда 0.
- Генерацию «Файл инвентаризации.txt» (сводная по Код товара).
- Обработку отсутствующих файлов / неверных столбцов.
- Игнорирование файлов, имя которых не 6 цифр.
- Наличие границ и ширины столбцов в xlsx.
"""
import os
import pytest
import pandas as pd

from core.pal_analyzer import PalAnalyzer, SOURCE_COLUMNS, FINAL_COLUMNS


# =========================================================
# Вспомогательные функции
# =========================================================
def _make_pallet_file(path, rows, extra_columns=None):
    """Создаёт xlsx-файл с нужными столбцами и данными.

    В файле есть «Ст» (лишний столбец), чтобы убедиться, что анализатор
    берёт только нужные колонки.
    """
    data = []
    for r in rows:
        row = {"Ст": 2}
        for col in SOURCE_COLUMNS:
            row[col] = r.get(col, "")
        data.append(row)

    df = pd.DataFrame(data, columns=["Ст"] + SOURCE_COLUMNS)
    if extra_columns:
        for c in extra_columns:
            df[c] = None
    df.to_excel(path, index=False)


def _sample_rows():
    return [
        {
            "Код товара": "111",
            "Товар": "Товар А",
            "Цена": 100.0,
            "% от всех": 10.0,
            "Кол-во до": 10,
            "Кол-во после": 8,
        },
        {
            "Код товара": "222",
            "Товар": "Товар Б",
            "Цена": 50.0,
            "% от всех": 5.0,
            "Кол-во до": 4,
            "Кол-во после": 6,
        },
    ]


def _run_with_tmp_base(analyzer, input_dir, tmp_path):
    """Запускает анализатор, подменяя BASE_DIR, чтобы не трогать реальную папку."""
    import core.pal_analyzer as pal_mod
    original_base = pal_mod.BASE_DIR
    pal_mod.BASE_DIR = str(tmp_path)
    try:
        return analyzer.run(str(input_dir))
    finally:
        pal_mod.BASE_DIR = original_base


# =========================================================
# run — успешный сценарий
# =========================================================
class TestRunSuccess:

    def test_single_file(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_pallet_file(input_dir / "528596.xlsx", _sample_rows())

        analyzer = PalAnalyzer()
        result = _run_with_tmp_base(analyzer, input_dir, tmp_path)

        assert result["success"] is True
        assert "file" in result
        assert "inventory_file" in result
        assert os.path.isfile(result["file"])
        assert os.path.isfile(result["inventory_file"])
        assert "total_sum" not in result

    def test_pallet_number_from_filename(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_pallet_file(input_dir / "528596.xlsx", _sample_rows())

        analyzer = PalAnalyzer()
        result = _run_with_tmp_base(analyzer, input_dir, tmp_path)

        df = pd.read_excel(result["file"])
        assert list(df.columns) == FINAL_COLUMNS
        assert set(df["№ паллета"].astype(str)) == {"528596"}

    def test_deviation_calculated_sum_is_zero(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_pallet_file(input_dir / "528596.xlsx", _sample_rows())

        analyzer = PalAnalyzer()
        result = _run_with_tmp_base(analyzer, input_dir, tmp_path)

        df = pd.read_excel(result["file"])
        deviations = df["Отклонение"].tolist()
        assert deviations == [2, -2]
        assert (df["Сумма"] == 0).all()

    def test_multiple_files_sorted(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_pallet_file(input_dir / "528596.xlsx", _sample_rows())
        _make_pallet_file(input_dir / "528573.xlsx", _sample_rows())

        analyzer = PalAnalyzer()
        result = _run_with_tmp_base(analyzer, input_dir, tmp_path)

        df = pd.read_excel(result["file"])
        # Сначала 528573 (по возрастанию), потом 528596
        first = str(df["№ паллета"].iloc[0])
        assert first == "528573"


# =========================================================
# Файл инвентаризации (.txt)
# =========================================================
class TestInventoryFile:

    def test_inventory_file_created(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_pallet_file(input_dir / "528596.xlsx", _sample_rows())

        analyzer = PalAnalyzer()
        result = _run_with_tmp_base(analyzer, input_dir, tmp_path)

        inv_path = result["inventory_file"]
        assert inv_path.endswith("Файл инвентаризации.txt")
        assert os.path.isfile(inv_path)

        with open(inv_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        # Строки вида "Код\tОтклонение", без шапки, отсортированы по коду
        assert lines == ["111\t2", "222\t-2"]

    def test_inventory_file_sums_by_code(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Один и тот же код товара в двух файлах
        rows1 = [{
            "Код товара": "111", "Товар": "А", "Цена": 10.0,
            "% от всех": 1.0, "Кол-во до": 10, "Кол-во после": 8,
        }]
        rows2 = [{
            "Код товара": "111", "Товар": "А", "Цена": 10.0,
            "% от всех": 1.0, "Кол-во до": 5, "Кол-во после": 8,
        }]
        _make_pallet_file(input_dir / "528573.xlsx", rows1)
        _make_pallet_file(input_dir / "528596.xlsx", rows2)

        analyzer = PalAnalyzer()
        result = _run_with_tmp_base(analyzer, input_dir, tmp_path)

        with open(result["inventory_file"], "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        # Сумма отклонений по коду 111: 2 + (-3) = -1
        assert lines == ["111\t-1"]

    def test_inventory_file_has_zero(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        rows = [{
            "Код товара": "111", "Товар": "А", "Цена": 10.0,
            "% от всех": 1.0, "Кол-во до": 10, "Кол-во после": 10,
        }]
        _make_pallet_file(input_dir / "528573.xlsx", rows)

        analyzer = PalAnalyzer()
        result = _run_with_tmp_base(analyzer, input_dir, tmp_path)

        with open(result["inventory_file"], "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        assert lines == ["111\t0"]


# =========================================================
# run — ошибки
# =========================================================
class TestRunErrors:

    def test_empty_folder(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        analyzer = PalAnalyzer()
        with pytest.raises(RuntimeError):
            _run_with_tmp_base(analyzer, input_dir, tmp_path)

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

        # Файл с именем из 6 цифр, но без нужных столбцов
        df = pd.DataFrame({"Другой столбец": [1, 2]})
        df.to_excel(input_dir / "528596.xlsx", index=False)

        analyzer = PalAnalyzer()
        with pytest.raises(RuntimeError, match="нет столбцов"):
            _run_with_tmp_base(analyzer, input_dir, tmp_path)

    def test_ignores_non_digit_files(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        _make_pallet_file(input_dir / "528596.xlsx", _sample_rows())
        # Имена не из 6 цифр — должны игнорироваться
        _make_pallet_file(input_dir / "1.xlsx", _sample_rows())
        _make_pallet_file(input_dir / "abcdef.xlsx", _sample_rows())
        (input_dir / "528596.txt").write_text("не excel", encoding="utf-8")

        analyzer = PalAnalyzer()
        result = _run_with_tmp_base(analyzer, input_dir, tmp_path)

        df = pd.read_excel(result["file"])
        assert set(df["№ паллета"].astype(str)) == {"528596"}

    def test_no_digit_files_raises(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_pallet_file(input_dir / "1.xlsx", _sample_rows())

        analyzer = PalAnalyzer()
        with pytest.raises(RuntimeError):
            _run_with_tmp_base(analyzer, input_dir, tmp_path)


# =========================================================
# XLSX — оформление (границы)
# =========================================================
class TestXlsxFormatting:

    def test_borders_present(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_pallet_file(input_dir / "528596.xlsx", _sample_rows())

        analyzer = PalAnalyzer()
        result = _run_with_tmp_base(analyzer, input_dir, tmp_path)

        from openpyxl import load_workbook
        wb = load_workbook(result["file"])
        ws = wb["Задания ТСД"]

        # У первой ячейки (шапка) должна быть рамка (граница)
        cell = ws.cell(row=1, column=1)
        assert cell.border is not None
        assert cell.border.left.style is not None