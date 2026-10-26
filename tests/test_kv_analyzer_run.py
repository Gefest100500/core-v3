# tests/test_kv_analyzer_run.py
"""
Тесты для KvAnalyzer.run() — полный процесс анализа.

Создаём временные Excel-файлы (РТП + Кванты), запускаем run(),
проверяем результат.
"""
import os
import tempfile

import pandas as pd
import pytest

from core.kv_analyzer import KvAnalyzer


# =========================================================
# FIXTURES
# =========================================================
@pytest.fixture
def kv_analyzer():
    """Создаёт экземпляр анализатора."""
    return KvAnalyzer()


@pytest.fixture
def tmp_folders(tmp_path, monkeypatch):
    """Подменяет FOLDERS['kv'] на временную папку."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Патчим config.FOLDERS — чтобы run() писал в tmp_path
    import config
    original_folders = config.FOLDERS.copy() if hasattr(config, "FOLDERS") else {}
    monkeypatch.setattr(
        "core.kv_analyzer.FOLDERS",
        {"kv": str(output_dir)},
        raising=False,
    )
    return output_dir


def _make_rtp(tmp_path, rows):
    """Создаёт временный РТП.xlsx."""
    path = tmp_path / "rtp.xlsx"
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return str(path)


def _make_kv(tmp_path, rows):
    """Создаёт временный Кванты.xlsx."""
    path = tmp_path / "kv.xlsx"
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return str(path)


# =========================================================
# БАЗОВЫЕ ТЕСТЫ
# =========================================================
class TestRunBasic:
    def test_empty_rtp(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """Пустой РТП — не падаем."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "1", "Название типа операции": "Приход",
             "Количество": 10},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "1", "Наименование ТП": "Товар",
             "ГР 20": "Прочее", "Потери (руб без НДС)": 5000,
             "Излишек\\Недостача": "Недостача"},
        ])

        # Патчим FOLDERS
        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        result = kv_analyzer.run(rtp, kv)
        assert result["success"] is True
        assert "files" in result

    def test_returns_shadow_rows(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """run() возвращает shadow_rows."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "1", "Название типа операции": "Приход",
             "Количество": 10},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "1", "Наименование ТП": "Яблоки",
             "ГР 20": "Свежие фрукты", "Потери (руб без НДС)": 5000,
             "Излишек\\Недостача": "Недостача"},
        ])

        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        result = kv_analyzer.run(rtp, kv)
        assert "shadow_rows" in result
        assert len(result["shadow_rows"]) >= 1

        # Проверяем поля
        row = result["shadow_rows"][0]
        assert "tp_code" in row
        assert "rule_fired" in row
        assert "reason" in row


# =========================================================
# ПРАВИЛО A1 — ФРУКТЫ/ОВОЩИ
# =========================================================
class TestRuleA1:
    def test_fruits_rule(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """Строка с ГР 20 = Свежие фрукты → A1."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "1", "Название типа операции": "Приход",
             "Количество": 10},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "1", "Наименование ТП": "Яблоки",
             "ГР 20": "Свежие фрукты", "Потери (руб без НДС)": 5000,
             "Излишек\\Недостача": "Недостача"},
        ])

        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        result = kv_analyzer.run(rtp, kv)

        # Ищем строку с A1
        a1_rows = [r for r in result["shadow_rows"] if r["rule_fired"] == "A1"]
        assert len(a1_rows) == 1
        assert "Пересорт" in a1_rows[0]["reason"]

    def test_veg_rule(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """ГР 20 = Свежие овощи → A1."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "2", "Название типа операции": "Приход",
             "Количество": 5},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "2", "Наименование ТП": "Огурцы",
             "ГР 20": "Свежие овощи", "Потери (руб без НДС)": 3000,
             "Излишек\\Недостача": "Недостача"},
        ])

        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        result = kv_analyzer.run(rtp, kv)
        a1_rows = [r for r in result["shadow_rows"] if r["rule_fired"] == "A1"]
        assert len(a1_rows) == 1


# =========================================================
# ПРАВИЛО A2 — СЫРЬЁ
# =========================================================
class TestRuleA2:
    def test_syre_by_gr20(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """ГР 20 = Сырье → A2."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "3", "Название типа операции": "Приход",
             "Количество": 8},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "3", "Наименование ТП": "Мука",
             "ГР 20": "Сырье", "Потери (руб без НДС)": 7000,
             "Излишек\\Недостача": "Недостача"},
        ])

        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        result = kv_analyzer.run(rtp, kv)
        a2_rows = [r for r in result["shadow_rows"] if r["rule_fired"] == "A2"]
        assert len(a2_rows) == 1

    def test_syre_by_name(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """Наименование содержит "сырье" → A2."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "4", "Название типа операции": "Приход",
             "Количество": 3},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "4", "Наименование ТП": "Сырье для выпечки",
             "ГР 20": "Прочее", "Потери (руб без НДС)": 4000,
             "Излишек\\Недостача": "Недостача"},
        ])

        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        result = kv_analyzer.run(rtp, kv)
        a2_rows = [r for r in result["shadow_rows"] if r["rule_fired"] == "A2"]
        assert len(a2_rows) == 1


# =========================================================
# ПРАВИЛО B — МЕСТНЫЙ ПОСТАВЩИК
# =========================================================
class TestRuleB:
    def test_local_supplier(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """Операция "Приход•Местный" → B."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "5", "Название типа операции": "Приход•Местный",
             "Количество": 10},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "5", "Наименование ТП": "Товар",
             "ГР 20": "Прочее", "Потери (руб без НДС)": 6000,
             "Излишек\\Недостача": "Недостача"},
        ])

        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        result = kv_analyzer.run(rtp, kv)
        b_rows = [r for r in result["shadow_rows"] if r["rule_fired"] == "B"]
        assert len(b_rows) >= 1


# =========================================================
# ПОРОГ ПОТЕРЬ
# =========================================================
class TestLossFilter:
    def test_below_threshold_skipped(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """Строки с потерями < 1000 руб — отфильтрованы."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "6", "Название типа операции": "Приход",
             "Количество": 10},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "6", "Наименование ТП": "Товар",
             "ГР 20": "Прочее", "Потери (руб без НДС)": 500,
             "Излишек\\Недостача": "Недостача"},
        ])

        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        result = kv_analyzer.run(rtp, kv)
        # 500 < 1000 → строка отфильтрована → shadow_rows пустые
        assert len(result["shadow_rows"]) == 0

    def test_above_threshold_kept(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """Строки с потерями >= 1000 руб — оставлены."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "7", "Название типа операции": "Приход",
             "Количество": 10},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "7", "Наименование ТП": "Товар",
             "ГР 20": "Прочее", "Потери (руб без НДС)": 1500,
             "Излишек\\Недостача": "Недостача"},
        ])

        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        result = kv_analyzer.run(rtp, kv)
        assert len(result["shadow_rows"]) >= 1


# =========================================================
# ФАЙЛЫ РЕЗУЛЬТАТА
# =========================================================
class TestOutputFiles:
    def test_creates_excel_files(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """run() создаёт Ревизор 1.xlsx и Ревизор 2.xlsx."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "8", "Название типа операции": "Приход",
             "Количество": 10},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "8", "Наименование ТП": "Товар",
             "ГР 20": "Прочее", "Потери (руб без НДС)": 5000,
             "Излишек\\Недостача": "Недостача"},
        ])

        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        result = kv_analyzer.run(rtp, kv)
        assert result["success"] is True
        assert len(result["files"]) == 2

        for f in result["files"]:
            assert os.path.isfile(f)


# =========================================================
# PROGRESS CALLBACK
# =========================================================
class TestProgressCallback:
    def test_callback_called(self, kv_analyzer, tmp_path, tmp_folders, monkeypatch):
        """progress_callback вызывается."""
        rtp = _make_rtp(tmp_path, [
            {"Код товара": "9", "Название типа операции": "Приход",
             "Количество": 10},
        ])
        kv = _make_kv(tmp_path, [
            {"Код ТП": "9", "Наименование ТП": "Товар",
             "ГР 20": "Прочее", "Потери (руб без НДС)": 5000,
             "Излишек\\Недостача": "Недостача"},
        ])

        monkeypatch.setattr(
            "config.FOLDERS",
            {"kv": str(tmp_folders)},
            raising=False,
        )

        calls = []

        def callback(value, message=None):
            calls.append((value, message))

        kv_analyzer.run(rtp, kv, progress_callback=callback)
        assert len(calls) > 0
        # Проверяем, что callback получает значения от 0 до 1
        values = [c[0] for c in calls]
        assert min(values) >= 0
        assert max(values) <= 1