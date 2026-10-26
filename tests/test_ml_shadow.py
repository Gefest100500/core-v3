# tests/test_ml_shadow.py
"""
Тесты для ml/shadow.py (Shadow Engine v0.3.2).

Покрываем:
- _build_row_key / _build_inventory_key
- _explain_row: объяснение + все features
- run_shadow: запись всех строк в JSONL и SQLite
- get_hypotheses: чтение с фильтрами
- get_confidence_stats: статистика
"""
import json
import os
import sqlite3

import pytest


@pytest.fixture
def isolated_ml(tmp_path, monkeypatch):
    db_path = tmp_path / "shadow.sqlite"
    report_path = tmp_path / "shadow_report.jsonl"

    monkeypatch.setattr("ml.config.SHADOW_DB_PATH", str(db_path))
    monkeypatch.setattr("ml.config.SHADOW_REPORT_PATH", str(report_path))
    monkeypatch.setattr("ml.config.ML_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("ml.config.EXPORTS_DIR", str(tmp_path))
    monkeypatch.setattr("ml.config.MODELS_DIR", str(tmp_path))

    monkeypatch.setattr("ml.storage.SHADOW_DB_PATH", str(db_path))
    monkeypatch.setattr("ml.shadow.SHADOW_REPORT_PATH", str(report_path))

    return {"db_path": db_path, "report_path": report_path, "tmp_path": tmp_path}


# =========================================================
# _build_row_key
# =========================================================
class TestBuildRowKey:
    def test_all_fields(self):
        from ml.shadow import _build_row_key
        assert _build_row_key({"rtp": "R1", "tp_code": "12345", "date": "2026-10-08"}) == "R1|12345|2026-10-08"

    def test_missing_fields(self):
        from ml.shadow import _build_row_key
        assert _build_row_key({"tp_code": "12345"}) == "12345"

    def test_empty(self):
        from ml.shadow import _build_row_key
        assert _build_row_key({}) == ""

    def test_strips(self):
        from ml.shadow import _build_row_key
        row = {"rtp": "  R1  ", "tp_code": "  12345  ", "date": "  2026-10-08  "}
        assert _build_row_key(row) == "R1|12345|2026-10-08"

    def test_skips_empty(self):
        from ml.shadow import _build_row_key
        assert _build_row_key({"rtp": "", "tp_code": "1", "date": ""}) == "1"


# =========================================================
# _build_inventory_key
# =========================================================
class TestBuildInventoryKey:
    def test_normal(self):
        from ml.shadow import _build_inventory_key
        assert _build_inventory_key({"gm_code": "GM001", "start_date": "2026-10-01"}) == "GM001|2026-10-01"

    def test_none(self):
        from ml.shadow import _build_inventory_key
        assert _build_inventory_key(None) == "unknown"

    def test_empty_dict(self):
        from ml.shadow import _build_inventory_key
        assert _build_inventory_key({}) == "unknown"

    def test_partial(self):
        from ml.shadow import _build_inventory_key
        assert _build_inventory_key({"gm_code": "GM001"}) == "GM001|?"


# =========================================================
# _explain_row
# =========================================================
class TestExplainRow:
    def test_a1_high_confidence(self):
        from ml.shadow import _explain_row, RULE_A1, RULE_CONFIDENCE
        row = {"rule_fired": "A1", "reason": "Пересорт на кассе"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["rule_fired"] == RULE_A1
        assert exp["confidence"] == RULE_CONFIDENCE[RULE_A1]
        assert "A1" in exp["explanation"]

    def test_a2_high_confidence(self):
        from ml.shadow import _explain_row, RULE_A2, RULE_CONFIDENCE
        row = {"rule_fired": "A2", "reason": "Потери ТО (сырьё)"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["rule_fired"] == RULE_A2
        assert exp["confidence"] == RULE_CONFIDENCE[RULE_A2]

    def test_b_medium_confidence(self):
        from ml.shadow import _explain_row, RULE_B, RULE_CONFIDENCE
        row = {"rule_fired": "B", "reason": "Ошибки в работе (Местный поставщик)"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["rule_fired"] == RULE_B
        assert exp["confidence"] == RULE_CONFIDENCE[RULE_B]

    def test_steal(self):
        from ml.shadow import _explain_row, RULE_STEAL
        row = {"rule_fired": "steal", "reason": "Возможно хищение"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["rule_fired"] == RULE_STEAL

    def test_box(self):
        from ml.shadow import _explain_row, RULE_BOX
        row = {"rule_fired": "box", "reason": "Коробочный недовоз - обычная приемка"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["rule_fired"] == RULE_BOX

    def test_mirror(self):
        from ml.shadow import _explain_row, RULE_MIRROR
        row = {"rule_fired": "mirror", "reason": "Нет потерь,  выявлено зеркальное отклонение"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["rule_fired"] == RULE_MIRROR

    def test_fallback_with_reason(self):
        from ml.shadow import _explain_row, RULE_FALLBACK
        row = {"rule_fired": None, "reason": "Коробочный недовоз - обычная приемка"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["rule_fired"] == RULE_FALLBACK
        assert "по умолчанию" in exp["explanation"].lower()

    def test_unknown_no_reason(self):
        from ml.shadow import _explain_row, RULE_UNKNOWN
        row = {"rule_fired": None, "reason": ""}
        exp = _explain_row(row, threshold=0.6)
        assert exp["rule_fired"] == RULE_UNKNOWN
        assert "аномалия" in exp["explanation"].lower()

    def test_unknown_missing_reason_key(self):
        from ml.shadow import _explain_row, RULE_UNKNOWN
        row = {"rule_fired": None}
        exp = _explain_row(row, threshold=0.6)
        assert exp["rule_fired"] == RULE_UNKNOWN

    def test_unknown_rule_treated_as_fallback(self):
        from ml.shadow import _explain_row, RULE_FALLBACK
        row = {"rule_fired": "XYZ", "reason": "Что-то"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["rule_fired"] == RULE_FALLBACK

    def test_features_include_reason(self):
        from ml.shadow import _explain_row
        row = {"rule_fired": "A1", "reason": "Пересорт на кассе"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["features"]["reason"] == "Пересорт на кассе"

    def test_features_include_tp_code(self):
        from ml.shadow import _explain_row
        row = {"rule_fired": "A1", "reason": "Пересорт",
               "tp_code": "12345"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["features"]["tp_code"] == "12345"

    def test_features_include_operation(self):
        from ml.shadow import _explain_row
        row = {"rule_fired": "B", "reason": "Местный",
               "operation": "Приход•Местный"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["features"]["operation"] == "Приход•Местный"

    def test_features_include_sign(self):
        from ml.shadow import _explain_row
        row = {"rule_fired": "A1", "reason": "Пересорт",
               "sign": "Недостача"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["features"]["sign"] == "Недостача"

    def test_features_include_loss_amount(self):
        from ml.shadow import _explain_row
        row = {"rule_fired": "A1", "reason": "Пересорт",
               "loss_amount": 1234.56}
        exp = _explain_row(row, threshold=0.6)
        assert exp["features"]["loss_amount"] == 1234.56

    def test_features_include_name_and_gr20(self):
        from ml.shadow import _explain_row
        row = {"rule_fired": "A2", "reason": "Сырьё",
               "name": "Сыр Российский", "gr20": "Сырье"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["features"]["name"] == "Сыр Российский"
        assert exp["features"]["gr20"] == "Сырье"

    def test_features_include_doc(self):
        from ml.shadow import _explain_row
        row = {"rule_fired": "A2", "reason": "Сырьё",
               "doc": "Нет номера БФ"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["features"]["doc"] == "Нет номера БФ"

    def test_features_missing_fields_safe(self):
        from ml.shadow import _explain_row
        row = {"rule_fired": "A1", "reason": "Пересорт"}
        exp = _explain_row(row, threshold=0.6)
        assert exp["features"]["tp_code"] == ""
        assert exp["features"]["operation"] == ""
        assert exp["features"]["sign"] == ""

    def test_confidence_ordering(self):
        from ml.shadow import RULE_CONFIDENCE
        assert RULE_CONFIDENCE["A1"] > RULE_CONFIDENCE["A2"]
        assert RULE_CONFIDENCE["A2"] > RULE_CONFIDENCE["B"]
        assert RULE_CONFIDENCE["B"] > RULE_CONFIDENCE["steal"]
        assert RULE_CONFIDENCE["steal"] > RULE_CONFIDENCE["box"]
        assert RULE_CONFIDENCE["box"] > RULE_CONFIDENCE["mirror"]
        assert RULE_CONFIDENCE["mirror"] > RULE_CONFIDENCE["fallback"]
        assert RULE_CONFIDENCE["fallback"] > RULE_CONFIDENCE["unknown"]


# =========================================================
# run_shadow
# =========================================================
class TestRunShadow:
    def test_empty_rows(self, isolated_ml):
        from ml.shadow import run_shadow
        res = run_shadow(rows=[], active_inventory=None, clear_before=False)
        assert res["total"] == 0
        assert res["db_written"] == 0

    def test_writes_all_rows(self, isolated_ml):
        from ml.shadow import run_shadow
        rows = [
            {"rtp": "R1", "tp_code": "1", "date": "2026-10-08",
             "rule_fired": "A1", "reason": "Пересорт на кассе"},
            {"rtp": "R2", "tp_code": "2", "date": "2026-10-08",
             "rule_fired": None, "reason": "Коробочный недовоз"},
            {"rtp": "R3", "tp_code": "3", "date": "2026-10-08",
             "rule_fired": None, "reason": ""},
        ]
        res = run_shadow(rows=rows, active_inventory=None, clear_before=False)
        assert res["total"] == 3
        assert res["db_written"] == 3

    def test_writes_jsonl(self, isolated_ml):
        from ml.shadow import run_shadow
        rows = [
            {"rtp": "R1", "tp_code": "1", "date": "x",
             "rule_fired": "A1", "reason": "Пересорт на кассе"},
        ]
        run_shadow(rows=rows, active_inventory=None, clear_before=False)

        report_path = isolated_ml["report_path"]
        assert os.path.isfile(report_path)

        with open(report_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1
        d = json.loads(lines[0])
        assert d["rule_fired"] == "A1"

    def test_writes_sqlite(self, isolated_ml):
        from ml.shadow import run_shadow
        rows = [
            {"rtp": "R1", "tp_code": "1", "date": "x",
             "rule_fired": "A1", "reason": "Пересорт на кассе"},
        ]
        run_shadow(rows=rows, active_inventory=None, clear_before=False)

        conn = sqlite3.connect(str(isolated_ml["db_path"]))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM hypotheses")
        count = cur.fetchone()[0]
        conn.close()
        assert count == 1

    def test_appends_jsonl(self, isolated_ml):
        from ml.shadow import run_shadow
        rows = [{"rtp": "R1", "tp_code": "1", "date": "x",
                 "rule_fired": "A1", "reason": "Пересорт на кассе"}]
        run_shadow(rows=rows, active_inventory=None, clear_before=False)
        run_shadow(rows=rows, active_inventory=None, clear_before=False)

        with open(isolated_ml["report_path"], "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_inventory_key(self, isolated_ml):
        from ml.shadow import run_shadow
        rows = [{"rtp": "R1", "tp_code": "1", "date": "x",
                 "rule_fired": "A1", "reason": "Пересорт на кассе"}]
        run_shadow(
            rows=rows,
            active_inventory={"gm_code": "GM001", "start_date": "2026-10-01"},
            clear_before=False,
        )

        with open(isolated_ml["report_path"], "r", encoding="utf-8") as f:
            d = json.loads(f.readline())
        assert d["inventory_key"] == "GM001|2026-10-01"


# =========================================================
# get_hypotheses
# =========================================================
class TestGetHypotheses:
    def test_empty(self, isolated_ml):
        from ml.shadow import get_hypotheses
        assert get_hypotheses() == []

    def test_returns_all(self, isolated_ml):
        from ml.shadow import run_shadow, get_hypotheses
        rows = [
            {"rtp": "R1", "tp_code": "1", "date": "x",
             "rule_fired": "A1", "reason": "Пересорт на кассе"},
            {"rtp": "R2", "tp_code": "2", "date": "x",
             "rule_fired": None, "reason": ""},
        ]
        run_shadow(rows=rows, active_inventory=None, clear_before=False)
        result = get_hypotheses()
        assert len(result) == 2

    def test_sorted_by_confidence_asc(self, isolated_ml):
        from ml.shadow import run_shadow, get_hypotheses
        rows = [
            {"rtp": "R1", "tp_code": "1", "date": "x",
             "rule_fired": "A1", "reason": "Пересорт на кассе"},
            {"rtp": "R2", "tp_code": "2", "date": "x",
             "rule_fired": None, "reason": ""},
            {"rtp": "R3", "tp_code": "3", "date": "x",
             "rule_fired": None, "reason": "Коробочный недовоз"},
        ]
        run_shadow(rows=rows, active_inventory=None, clear_before=False)
        result = get_hypotheses()
        confidences = [r["confidence"] for r in result]
        assert confidences == sorted(confidences)

    def test_filter_max_confidence(self, isolated_ml):
        from ml.shadow import run_shadow, get_hypotheses
        rows = [
            {"rtp": "R1", "tp_code": "1", "date": "x",
             "rule_fired": "A1", "reason": "Пересорт на кассе"},
            {"rtp": "R2", "tp_code": "2", "date": "x",
             "rule_fired": None, "reason": ""},
        ]
        run_shadow(rows=rows, active_inventory=None, clear_before=False)

        result = get_hypotheses(max_confidence=0.5)
        assert len(result) == 1
        assert result[0]["confidence"] <= 0.5

    def test_only_unlabeled(self, isolated_ml):
        from ml.shadow import run_shadow, get_hypotheses
        from ml.feedback import add_feedback

        rows = [{"rtp": "R1", "tp_code": "1", "date": "x",
                 "rule_fired": "A1", "reason": "Пересорт на кассе"}]
        run_shadow(rows=rows, active_inventory=None, clear_before=False)

        all_recs = get_hypotheses()
        add_feedback(all_recs[0]["id"], "agree")

        unlabeled = get_hypotheses(only_unlabeled=True)
        assert len(unlabeled) == 0


# =========================================================
# get_confidence_stats
# =========================================================
class TestGetConfidenceStats:
    def test_empty(self, isolated_ml):
        from ml.shadow import get_confidence_stats
        stats = get_confidence_stats()
        assert stats["total"] == 0

    def test_stats(self, isolated_ml):
        from ml.shadow import run_shadow, get_confidence_stats
        rows = [
            {"rtp": "R1", "tp_code": "1", "date": "x",
             "rule_fired": "A1", "reason": "Пересорт на кассе"},
            {"rtp": "R2", "tp_code": "2", "date": "x",
             "rule_fired": None, "reason": ""},
        ]
        run_shadow(rows=rows, active_inventory=None, clear_before=False)
        stats = get_confidence_stats()
        assert stats["total"] == 2
        assert stats["min"] == 0.1
        assert stats["max"] == 1.0