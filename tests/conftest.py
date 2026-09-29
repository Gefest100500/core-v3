# tests/conftest.py
"""
Общие фикстуры для тестов Core.

- isolated_config: временный config.json
- fake_kv_dataframe: фейковый DataFrame квантов
- fake_rtp_dataframe: фейковый DataFrame РТП
- tmp_data_manager: DataManager с временной папкой
"""
import json
import os
import sys
from pathlib import Path

import pytest
import pandas as pd


# Добавляем корень проекта в sys.path, чтобы импорты работали
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# =========================================================
# ФИКСТУРЫ ДАННЫХ
# =========================================================
@pytest.fixture
def fake_kv_dataframe():
    """Фейковый DataFrame квантов с минимально нужными столбцами."""
    return pd.DataFrame({
        "Код ТП": ["111", "222", "333", "444", "555"],
        "Наименование ТП": [
            "Товар 1",
            "Товар 2 (сырье)",
            "Свежие овощи",
            "Товар 4",
            "Товар 5",
        ],
        "ГР 20": ["Группа", "Сырье", "Свежие овощи", "Группа", "Группа"],
        "Излишек\\Недостача": [
            "Излишек", "Недостача", "Недостача", "Излишек", "Недостача"
        ],
        "Потери (руб без НДС)": [5000, 3000, 2000, 1500, 800],
    })


@pytest.fixture
def fake_rtp_dataframe():
    """Фейковый DataFrame РТП с операциями."""
    return pd.DataFrame({
        "Код товара": ["111", "222", "222", "333", "444", "555"],
        "Название типа операции": [
            "Приход•Местный",
            "Приход•Недовоз от поставщика",
            "Приход•Недовоз от поставщика",
            "Приход•Недовоз внутри компании",
            "Приход•Перевоз внутри компании",
            "Инвентаризация",
        ],
        "Количество": [10, 5, 5, 20, 15, 30],
    })


# =========================================================
# ФИКСТУРЫ ВРЕМЕННЫХ ФАЙЛОВ
# =========================================================
@pytest.fixture
def tmp_json_file(tmp_path):
    """Создаёт временный JSON-файл с данными."""
    def _make(data, filename="test.json"):
        path = tmp_path / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return str(path)
    return _make


@pytest.fixture
def fake_kv_rules(tmp_path):
    """Создаёт временный kv_rules.json с минимальным набором правил."""
    rules = {
        "loss_min_rub": 1000.0,
        "box_deviation_pct": 50,
        "mirror_deviation_pct": 25,
        "gr20_fruits_veg": ["Свежие овощи", "Свежие фрукты"],
        "gr20_syre": "Сырье",
        "syre_name_marker": "сырье",
        "operation_types": {
            "local_supplier": ["Приход•Местный", "Приход•Недовоз от поставщика"],
            "nevoz": ["Приход•Недовоз внутри компании"],
            "perevoz": ["Приход•Перевоз внутри компании", "Приход•Неподтверждённый перевоз"],
            "inventory_prefix": "Инвентаризация",
        },
        "columns": {
            "code": "Код ТП",
            "name": "Наименование ТП",
            "gr20": "ГР 20",
            "loss": "Потери (руб без НДС)",
            "surplus_deficit": "Излишек\\Недостача",
            "reason": "Типовая причина",
            "doc_number": "Номер документа/заявки",
        },
        "values": {"surplus": "Излишек", "deficit": "Недостача"},
        "reasons": {
            "fruits_veg": "Пересорт на кассе",
            "syre": "Потери ТО (сырьё)",
            "local_supplier_errors": "Ошибки в работе (Местный поставщик)",
            "local_supplier_losses": "Потери ТО (Местный поставщик)",
            "steal": "Возможно хищение",
            "box_surplus": "Коробочный излишек",
            "box_shortage": "Коробочный недовоз",
            "mirror": "Зеркальное отклонение",
        },
        "doc_number": {
            "no_bf": "Нет номера БФ",
            "reasons_with_doc": [
                "Коробочный недовоз",
                "Коробочный излишек",
                "Ошибки в работе (Местный поставщик)",
                "Потери ТО (Местный поставщик)",
            ],
            "reasons_without_doc": [
                "Пересорт на кассе",
                "Зеркальное отклонение",
                "Возможно хищение",
                "Потери ТО (сырьё)",
            ],
        },
        "reviewers": ["Ревизор 1", "Ревизор 2"],
        "output": {
            "file_reviewer_1": "Ревизор 1.xlsx",
            "file_reviewer_2": "Ревизор 2.xlsx",
        },
    }

    path = tmp_path / "kv_rules.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    return str(path)