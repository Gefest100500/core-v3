# tests/test_os_mbp_analyzer.py
"""
Тесты для core/os_mbp_analyzer.py.

Проверяем парсинг ИНВ-1 (инвентаризационная опись):
- _detect_category: определение категории по имени файла
- _find_header_row: поиск строки-шапки по маркеру «количество, шт.»
- _find_column: поиск столбца по ключевым словам в 2 уровнях шапки
- _find_qty_columns: поиск ВСЕХ столбцов «количество, шт.»
- _clean_name: чистка наименования
- _filter_unwanted: фильтр мусорных позиций
- _parse_inv1: полный парсинг реального Excel-файла
- _build_svod: сборка свода из нескольких файлов

ВАЖНО:
- _find_header_row / _find_column / _find_qty_columns принимают pd.DataFrame.
  Это позволяет тестировать их без создания Excel-файлов.
- Для _parse_inv1 / _build_svod создаётся реальный .xlsx через tmp_path.
- unwanted.json подменяется через monkeypatch, чтобы тесты
  не зависели от реального списка в data/.
"""
import json
import os

import pandas as pd
import pytest

from core import os_mbp_analyzer as om


# =========================================================
# ФИКСТУРЫ
# =========================================================
@pytest.fixture
def patch_unwanted_path(tmp_path, monkeypatch):
    """Подменяет UNWANTED_PATH на временный файл с тестовым списком."""
    path = tmp_path / "unwanted.json"

    # По умолчанию — пустой список
    with open(path, "w", encoding="utf-8") as f:
        json.dump([], f)

    monkeypatch.setattr(om, "UNWANTED_PATH", str(path))
    return str(path)


@pytest.fixture
def patch_unwanted_with_data(tmp_path, monkeypatch):
    """Подменяет UNWANTED_PATH на файл с тестовыми позициями."""
    path = tmp_path / "unwanted.json"
    data = [
        "Специализированная одежда сотрудников ГМ",
        "Средства индивидуальной защиты",
        "Стремянка",
        "Урна стационарная",
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    monkeypatch.setattr(om, "UNWANTED_PATH", str(path))
    return str(path)


@pytest.fixture
def analyzer_no_unwanted(patch_unwanted_path):
    """Анализатор с пустым unwanted.json."""
    return om.OsMbpAnalyzer()


@pytest.fixture
def analyzer_with_unwanted(patch_unwanted_with_data):
    """Анализатор с непустым unwanted.json."""
    return om.OsMbpAnalyzer()


# =========================================================
# _detect_category
# =========================================================
class TestDetectCategory:
    def test_os_default(self, analyzer_no_unwanted):
        result = analyzer_no_unwanted._detect_category("file.xlsx", "ОС")
        assert result == "ОС"

    def test_mbp_by_name(self, analyzer_no_unwanted):
        result = analyzer_no_unwanted._detect_category("ИНВ-1 по МБП.xls", "ОС")
        assert result == "МБП"

    def test_mbp_by_name_lower(self, analyzer_no_unwanted):
        result = analyzer_no_unwanted._detect_category("ведомость_мбп_2026.xlsx", "ОС")
        assert result == "МБП"

    def test_zabalans(self, analyzer_no_unwanted):
        result = analyzer_no_unwanted._detect_category("ИНВ-5 забаланс.xls", "МБП")
        assert result == "Забаланс"

    def test_full_path(self, analyzer_no_unwanted):
        result = analyzer_no_unwanted._detect_category(
            "C:\\path\\to\\ИНВ-1 по МБП.xls", "ОС"
        )
        assert result == "МБП"


# =========================================================
# _find_header_row
# =========================================================
class TestFindHeaderRow:
    def test_finds_marker(self, analyzer_no_unwanted):
        """Шапка на 3-й строке (индекс 2)."""
        df = pd.DataFrame([
            ["какая-то шапка", None, None],
            [None, None, None],
            ["Наименование", "Код", "количество, шт."],
            ["Данные 1", "001", 5],
        ])
        result = analyzer_no_unwanted._find_header_row(df)
        assert result == 2

    def test_marker_case_insensitive(self, analyzer_no_unwanted):
        df = pd.DataFrame([
            ["Наименование", "Количество, ШТ."],
            ["Данные", 5],
        ])
        result = analyzer_no_unwanted._find_header_row(df)
        assert result == 0

    def test_marker_with_newline(self, analyzer_no_unwanted):
        df = pd.DataFrame([
            ["Наименование", "количество,\nшт."],
            ["Данные", 5],
        ])
        result = analyzer_no_unwanted._find_header_row(df)
        assert result == 0

    def test_not_found(self, analyzer_no_unwanted):
        df = pd.DataFrame([
            ["Наименование", "Что-то другое"],
            ["Данные", 5],
        ])
        result = analyzer_no_unwanted._find_header_row(df)
        assert result is None

    def test_empty_df(self, analyzer_no_unwanted):
        df = pd.DataFrame()
        result = analyzer_no_unwanted._find_header_row(df)
        assert result is None

    def test_deep_limit(self, analyzer_no_unwanted):
        """Ищем только в первых 100 строках."""
        rows = [["мусор"] * 3 for _ in range(150)]
        rows[120] = ["Наименование", "Код", "количество, шт."]
        df = pd.DataFrame(rows)
        result = analyzer_no_unwanted._find_header_row(df)
        assert result is None  # за пределами 100 строк


# =========================================================
# _find_column
# =========================================================
class TestFindColumn:
    def test_exact(self, analyzer_no_unwanted):
        df = pd.DataFrame([
            ["Наименование, назначение", "Код", "Количество"],
            ["Товар", "001", 5],
        ])
        result = analyzer_no_unwanted._find_column(
            df, header_row_idx=0,
            keywords=["наименование, назначение", "наименование"],
            label="Наименование",
        )
        assert result == 0

    def test_case_insensitive(self, analyzer_no_unwanted):
        df = pd.DataFrame([
            ["НАИМЕНОВАНИЕ, НАЗНАЧЕНИЕ", "Код"],
            ["Товар", "001"],
        ])
        result = analyzer_no_unwanted._find_column(
            df, header_row_idx=0,
            keywords=["наименование"],
            label="Наименование",
        )
        assert result == 0

    def test_looks_around_header(self, analyzer_no_unwanted):
        """Маркер в строке выше индекса шапки."""
        df = pd.DataFrame([
            ["Наименование, назначение", "Код"],  # -1 от header
            ["подшапка", "подшапка"],               # header_row_idx
            ["данные", "данные"],
        ])
        result = analyzer_no_unwanted._find_column(
            df, header_row_idx=1,
            keywords=["наименование"],
            label="Наименование",
        )
        assert result == 0

    def test_not_found(self, analyzer_no_unwanted):
        df = pd.DataFrame([
            ["Что-то", "Другое"],
            ["данные", "данные"],
        ])
        result = analyzer_no_unwanted._find_column(
            df, header_row_idx=0,
            keywords=["наименование"],
            label="Наименование",
        )
        assert result is None

    def test_partial_match(self, analyzer_no_unwanted):
        df = pd.DataFrame([
            ["Наименование, назначение и краткая характеристика объекта"],
            ["данные"],
        ])
        result = analyzer_no_unwanted._find_column(
            df, header_row_idx=0,
            keywords=["наименование"],
            label="Наименование",
        )
        assert result == 0


# =========================================================
# _find_qty_columns
# =========================================================
class TestFindQtyColumns:
    def test_one_column(self, analyzer_no_unwanted):
        df = pd.DataFrame([
            ["Наименование", "Количество, шт."],
            ["Данные", 5],
        ])
        result = analyzer_no_unwanted._find_qty_columns(df, header_row_idx=0)
        assert result == [1]

    def test_two_columns(self, analyzer_no_unwanted):
        """ИНВ-1: два столбца «количество, шт.» (факт и по учёту)."""
        df = pd.DataFrame([
            ["Наименование", "Количество, шт.", "Количество, шт."],
            ["Данные", 5, 0],
        ])
        result = analyzer_no_unwanted._find_qty_columns(df, header_row_idx=0)
        assert result == [1, 2]

    def test_none(self, analyzer_no_unwanted):
        df = pd.DataFrame([
            ["Наименование", "Что-то"],
            ["Данные", 5],
        ])
        result = analyzer_no_unwanted._find_qty_columns(df, header_row_idx=0)
        assert result == []

    def test_looks_above_and_below(self, analyzer_no_unwanted):
        """Маркер в строке ВЫШЕ header_row_idx."""
        df = pd.DataFrame([
            ["Количество, шт."],  # -1
            ["подшапка"],          # header_row_idx
            ["данные"],
        ])
        result = analyzer_no_unwanted._find_qty_columns(df, header_row_idx=1)
        assert result == [0]

    def test_with_newline(self, analyzer_no_unwanted):
        df = pd.DataFrame([
            ["Наименование", "Количество,\nшт."],
            ["Данные", 5],
        ])
        result = analyzer_no_unwanted._find_qty_columns(df, header_row_idx=0)
        assert result == [1]


# =========================================================
# _clean_name
# =========================================================
class TestCleanName:
    def test_simple(self, analyzer_no_unwanted):
        assert analyzer_no_unwanted._clean_name("Товар") == "Товар"

    def test_strip_spaces(self, analyzer_no_unwanted):
        assert analyzer_no_unwanted._clean_name("  Товар  ") == "Товар"

    def test_newlines(self, analyzer_no_unwanted):
        assert analyzer_no_unwanted._clean_name("Товар\nстрока 2") == "Товар строка 2"

    def test_multiple_spaces(self, analyzer_no_unwanted):
        assert analyzer_no_unwanted._clean_name("Товар   с   пробелами") == "Товар с пробелами"

    def test_carriage_return(self, analyzer_no_unwanted):
        assert analyzer_no_unwanted._clean_name("Товар\r\nвторая") == "Товар вторая"

    def test_empty(self, analyzer_no_unwanted):
        assert analyzer_no_unwanted._clean_name("") == ""

    def test_none_like(self, analyzer_no_unwanted):
        assert analyzer_no_unwanted._clean_name(None) == ""


# =========================================================
# _filter_unwanted
# =========================================================
class TestFilterUnwanted:
    def test_keeps_good(self, analyzer_with_unwanted):
        df = pd.DataFrame({
            "Наименование": ["Товар 1", "Товар 2"],
            "Количество": [5, 10],
        })
        result = analyzer_with_unwanted._filter_unwanted(df)
        assert len(result) == 2

    def test_removes_unwanted(self, analyzer_with_unwanted):
        df = pd.DataFrame({
            "Наименование": [
                "Товар 1",
                "Стремянка складская",
                "Товар 2",
                "Урна стационарная",
            ],
            "Количество": [5, 1, 10, 2],
        })
        result = analyzer_with_unwanted._filter_unwanted(df)
        assert len(result) == 2
        assert "Товар 1" in result["Наименование"].values
        assert "Товар 2" in result["Наименование"].values

    def test_case_insensitive(self, analyzer_with_unwanted):
        df = pd.DataFrame({
            "Наименование": ["СТРЕМЯНКА складская"],
            "Количество": [1],
        })
        result = analyzer_with_unwanted._filter_unwanted(df)
        assert len(result) == 0

    def test_empty_unwanted(self, analyzer_no_unwanted):
        df = pd.DataFrame({
            "Наименование": ["Товар 1", "Стремянка"],
            "Количество": [5, 1],
        })
        result = analyzer_no_unwanted._filter_unwanted(df)
        assert len(result) == 2  # ничего не фильтруется

    def test_empty_df(self, analyzer_with_unwanted):
        df = pd.DataFrame({
            "Наименование": [],
            "Количество": [],
        })
        result = analyzer_with_unwanted._filter_unwanted(df)
        assert len(result) == 0


# =========================================================
# _parse_inv1 — интеграционные через реальный .xlsx
# =========================================================
def _make_inv1_file(path, header_row_idx=2, data_rows=None, qty_cols=None):
    """Создаёт тестовый .xlsx с шапкой ИНВ-1.

    Args:
        path: путь
        header_row_idx: индекс строки-шапки (0-based)
        data_rows: список (наименование, количество_1, количество_2) или
                   (наименование, количество_1)
        qty_cols: сколько столбцов «количество, шт.» (1 или 2)
    """
    if data_rows is None:
        data_rows = [
            ("Товар 1", 5),
            ("Товар 2", 10),
        ]
    if qty_cols is None:
        qty_cols = 1

    # Строим строки: до шапки — мусор
    rows = [["мусор"]] * header_row_idx

    # Строка шапки (подшапка ИНВ-1)
    header = ["Наименование, назначение и краткая характеристика объекта"]
    for _ in range(qty_cols):
        header.append("количество, шт.")
    rows.append(header)

    # Нумерация столбцов
    rows.append([str(i + 1) for i in range(len(header))])

    # Данные
    for row in data_rows:
        if len(row) == 2 and qty_cols == 2:
            # количество_2 = 0
            rows.append([row[0], row[1], 0])
        else:
            rows.append(list(row))

    # Итоговая строка
    rows.append(["Итого", sum(r[1] for r in data_rows if len(r) >= 2)])

    df = pd.DataFrame(rows)
    df.to_excel(path, index=False, header=False)
    return str(path)


class TestParseInv1:
    def test_basic(self, analyzer_no_unwanted, tmp_path):
        path = _make_inv1_file(tmp_path / "test.xlsx")
        df = analyzer_no_unwanted._parse_inv1(path, "ОС")
        assert len(df) == 2
        assert set(df.columns) == {"Категория", "Наименование", "Количество"}
        assert df["Категория"].iloc[0] == "ОС"
        assert df["Количество"].sum() == 15

    def test_picks_filled_qty_column(self, analyzer_no_unwanted, tmp_path):
        """
        ВАЖНО: два столбца «количество, шт.».
        Заполнен только второй. Должен выбраться он.
        """
        rows = [
            ["мусор"],
            ["мусор"],
            ["Наименование, назначение", "количество, шт.", "количество, шт."],
            ["1", "2", "3"],
            ["Товар 1", 0, 5],
            ["Товар 2", 0, 10],
            ["Итого", 0, 15],
        ]
        df = pd.DataFrame(rows)
        path = tmp_path / "two_cols.xlsx"
        df.to_excel(path, index=False, header=False)

        result = analyzer_no_unwanted._parse_inv1(str(path), "ОС")
        # Должно взяться 5+10=15, а не 0+0=0
        assert result["Количество"].sum() == 15

    def test_skips_total_rows(self, analyzer_no_unwanted, tmp_path):
        path = _make_inv1_file(tmp_path / "test.xlsx")
        df = analyzer_no_unwanted._parse_inv1(path, "ОС")
        # «Итого» не должно попасть
        assert not any("Итого" in str(n) for n in df["Наименование"].values)

    def test_skips_numbered_rows(self, analyzer_no_unwanted, tmp_path):
        path = _make_inv1_file(tmp_path / "test.xlsx")
        df = analyzer_no_unwanted._parse_inv1(path, "ОС")
        # Строки с «1», «2», «3» не должны попасть
        for name in df["Наименование"].values:
            assert not str(name).isdigit()

    def test_no_header_raises(self, analyzer_no_unwanted, tmp_path):
        rows = [["мусор"], ["мусор"], ["мусор"]]
        df = pd.DataFrame(rows)
        path = tmp_path / "no_header.xlsx"
        df.to_excel(path, index=False, header=False)

        with pytest.raises(RuntimeError, match="шапка"):
            analyzer_no_unwanted._parse_inv1(str(path), "ОС")

    def test_no_name_column_raises(self, analyzer_no_unwanted, tmp_path):
        rows = [
            ["мусор"],
            ["количество, шт."],
            ["1"],
            ["5"],
        ]
        df = pd.DataFrame(rows)
        path = tmp_path / "no_name.xlsx"
        df.to_excel(path, index=False, header=False)

        with pytest.raises(RuntimeError):
            analyzer_no_unwanted._parse_inv1(str(path), "ОС")


# =========================================================
# _build_svod
# =========================================================
class TestBuildSvod:
    def test_single_file(self, analyzer_no_unwanted, tmp_path):
        path = _make_inv1_file(tmp_path / "file1.xlsx")
        df = analyzer_no_unwanted._build_svod([path], "ОС", remove_unwanted=False)
        assert len(df) == 2
        assert df["Количество"].sum() == 15

    def test_two_files_sum(self, analyzer_no_unwanted, tmp_path):
        path1 = _make_inv1_file(tmp_path / "file1.xlsx")
        path2 = _make_inv1_file(
            tmp_path / "file2.xlsx",
            data_rows=[("Товар 1", 3), ("Товар 3", 7)],
        )
        df = analyzer_no_unwanted._build_svod(
            [path1, path2], "ОС", remove_unwanted=False
        )
        # Товар 1: 5 + 3 = 8, Товар 2: 10, Товар 3: 7
        assert len(df) == 3
        t1 = df[df["Наименование"] == "Товар 1"]["Количество"].iloc[0]
        assert t1 == 8
        assert df["Количество"].sum() == 25

    def test_group_by_name(self, analyzer_no_unwanted, tmp_path):
        path1 = _make_inv1_file(
            tmp_path / "f1.xlsx",
            data_rows=[("Одинаковый товар", 5)],
        )
        path2 = _make_inv1_file(
            tmp_path / "f2.xlsx",
            data_rows=[("Одинаковый товар", 7)],
        )
        df = analyzer_no_unwanted._build_svod(
            [path1, path2], "ОС", remove_unwanted=False
        )
        assert len(df) == 1
        assert df["Количество"].iloc[0] == 12

    def test_filter_unwanted(self, analyzer_with_unwanted, tmp_path):
        path = _make_inv1_file(
            tmp_path / "file.xlsx",
            data_rows=[
                ("Товар 1", 5),
                ("Стремянка складская", 2),
                ("Товар 2", 3),
            ],
        )
        df = analyzer_with_unwanted._build_svod(
            [path], "ОС", remove_unwanted=True
        )
        # «Стремянка» отфильтрована
        assert "Стремянка складская" not in df["Наименование"].values
        assert len(df) == 2

    def test_no_filter_when_flag_false(self, analyzer_with_unwanted, tmp_path):
        path = _make_inv1_file(
            tmp_path / "file.xlsx",
            data_rows=[
                ("Товар 1", 5),
                ("Стремянка складская", 2),
            ],
        )
        df = analyzer_with_unwanted._build_svod(
            [path], "ОС", remove_unwanted=False
        )
        # «Стремянка» НЕ отфильтрована
        assert "Стремянка складская" in df["Наименование"].values

    def test_missing_file_skipped(self, analyzer_no_unwanted, tmp_path):
        df = analyzer_no_unwanted._build_svod(
            [str(tmp_path / "no_file.xlsx")], "ОС", remove_unwanted=False
        )
        # Пустой DataFrame с правильными колонками
        assert len(df) == 0
        assert set(df.columns) == {"Категория", "Наименование", "Количество"}

    def test_empty_files_list(self, analyzer_no_unwanted):
        df = analyzer_no_unwanted._build_svod([], "ОС", remove_unwanted=False)
        assert len(df) == 0