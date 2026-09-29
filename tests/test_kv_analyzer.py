# tests/test_kv_analyzer.py
"""
Тесты для core/kv_analyzer.py.

Проверяем жёсткие правила на фейковых DataFrame.
"""
import os
import json

import pandas as pd
import pytest

from core.kv_analyzer import KvAnalyzer, _load_rules


class TestLoadRules:
    def test_default_rules(self, tmp_path, monkeypatch):
        # Временный путь к несуществующему kv_rules.json
        rules_path = tmp_path / "kv_rules.json"
        monkeypatch.setattr("core.kv_analyzer.KV_RULES_PATH", str(rules_path))

        rules = _load_rules()
        assert rules["loss_min_rub"] == 1000.0
        # Создался файл
        assert rules_path.exists()

    def test_existing_rules(self, tmp_path, monkeypatch, fake_kv_rules):
        monkeypatch.setattr("core.kv_analyzer.KV_RULES_PATH", fake_kv_rules)
        rules = _load_rules()
        assert rules["loss_min_rub"] == 1000.0
        assert "Свежие овощи" in rules["gr20_fruits_veg"]


class TestKvAnalyzerInit:
    def test_init(self, tmp_path, monkeypatch, fake_kv_rules):
        monkeypatch.setattr("core.kv_analyzer.KV_RULES_PATH", fake_kv_rules)

        steal_path = tmp_path / "steal_codes.json"
        with open(steal_path, "w") as f:
            json.dump([], f)
        monkeypatch.setattr("core.kv_analyzer.STEAL_CODES_PATH", str(steal_path))

        analyzer = KvAnalyzer()
        assert analyzer.rules is not None
        assert isinstance(analyzer.steal_codes, set)


class TestHardRules:
    """Проверяем жёсткие правила через _load_rules + ручной анализ.

    Полный run() требует FOLDERS и записи Excel — поэтому
    проверяем логику отдельно через фейковые DataFrame.
    """

    def test_fruits_veg_rule(self, fake_kv_dataframe, fake_rtp_dataframe):
        """Свежие овощи → «Пересорт на кассе»."""
        kv = fake_kv_dataframe
        fruits_veg = kv["ГР 20"].isin(["Свежие овощи", "Свежие фрукты"])
        assert fruits_veg.sum() == 1  # одна строка «Свежие овощи»

    def test_syre_by_gr20(self, fake_kv_dataframe):
        """ГР 20 == «Сырье» → по правилу."""
        kv = fake_kv_dataframe
        syre = kv["ГР 20"] == "Сырье"
        assert syre.sum() == 1

    def test_syre_by_name(self, fake_kv_dataframe):
        """Наименование содержит «сырье» → по правилу."""
        kv = fake_kv_dataframe
        syre_by_name = kv["Наименование ТП"].str.contains(
            "сырье", case=False, na=False, regex=False
        )
        assert syre_by_name.sum() == 1

    def test_local_supplier_rule(self, fake_rtp_dataframe):
        """Коды с операциями Приход•Местный / Приход•Недовоз от поставщика."""
        local_ops = ["Приход•Местный", "Приход•Недовоз от поставщика"]
        local_codes = fake_rtp_dataframe[
            fake_rtp_dataframe["Название типа операции"].isin(local_ops)
        ]["Код товара"].unique()
        # 111 (Местный), 222 (Недовоз от поставщика)
        assert "111" in local_codes
        assert "222" in local_codes
        assert "333" not in local_codes  # Недовоз внутри компании — не местный


class TestLossFilter:
    def test_filter_by_threshold(self, fake_kv_dataframe):
        """Фильтр потерь >= 1000 руб."""
        kv = fake_kv_dataframe
        kv["_num"] = pd.to_numeric(kv["Потери (руб без НДС)"], errors="coerce")
        filtered = kv[kv["_num"].abs() >= 1000.0]
        # 800 руб отсеивается, остаётся 4
        assert len(filtered) == 4