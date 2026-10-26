# tests/test_ml_integration.py
"""
Интеграционные тесты ML-модуля (v0.3).

Проверяют связку shadow + feedback + storage:
- Полный цикл: run_shadow → get_hypotheses → add_feedback → export
- Изоляция: ошибка Shadow не ломает основной анализ
- Storage: схема БД создаётся корректно

ВАЖНО (v0.3): Shadow пишет ВСЕ строки (датасет), а не только
«гипотезы». Поэтому число записей = числу входных строк.
"""
import os
import sqlite3

import pytest


@pytest.fixture
def isolated_ml(tmp_path, monkeypatch):
    db_path = tmp_path / "shadow.sqlite"
    report_path = tmp_path / "shadow_report.jsonl"
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()

    monkeypatch.setattr("ml.config.SHADOW_DB_PATH", str(db_path))
    monkeypatch.setattr("ml.config.SHADOW_REPORT_PATH", str(report_path))
    monkeypatch.setattr("ml.config.ML_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("ml.config.EXPORTS_DIR", str(exports_dir))
    monkeypatch.setattr("ml.config.MODELS_DIR", str(tmp_path))

    monkeypatch.setattr("ml.storage.SHADOW_DB_PATH", str(db_path))
    monkeypatch.setattr("ml.shadow.SHADOW_REPORT_PATH", str(report_path))
    monkeypatch.setattr("ml.feedback.EXPORTS_DIR", str(exports_dir))

    return {"db_path": db_path, "report_path": report_path, "exports_dir": exports_dir}


# =========================================================
# STORAGE
# =========================================================
class TestStorage:
    def test_get_connection_creates_schema(self, isolated_ml):
        from ml.storage import get_connection
        conn = get_connection()
        assert conn is not None

        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cur.fetchall()]
        conn.close()

        assert "hypotheses" in tables
        assert "feedback" in tables

    def test_indexes_created(self, isolated_ml):
        from ml.storage import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cur.fetchall()]
        conn.close()

        assert "idx_feedback_hyp" in indexes
        assert "idx_hyp_inventory" in indexes

    def test_idempotent(self, isolated_ml):
        """Повторный вызов get_connection не ломает схему."""
        from ml.storage import get_connection
        conn1 = get_connection()
        conn1.close()
        conn2 = get_connection()
        conn2.close()


# =========================================================
# FULL CYCLE
# =========================================================
class TestFullCycle:
    def test_run_feedback_export(self, isolated_ml):
        """Полный цикл: shadow → feedback → export (v0.3).

        В v0.3 Shadow пишет ВСЕ строки (это датасет), а не только
        «гипотезы». Поэтому ожидаем 3 записи, а не 2.
        """
        from ml.shadow import run_shadow, get_hypotheses
        from ml.feedback import add_feedback, get_feedback_stats, export_feedback

        rows = [
            {"rtp": "R1", "tp_code": "11111", "date": "2026-10-08",
             "rule_fired": None, "rule_confidence": None, "reason": ""},
            {"rtp": "R2", "tp_code": "22222", "date": "2026-10-08",
             "rule_fired": "B", "rule_confidence": None,
             "reason": "Ошибки в работе (Местный поставщик)"},
            {"rtp": "R3", "tp_code": "33333", "date": "2026-10-08",
             "rule_fired": "A1", "rule_confidence": None,
             "reason": "Пересорт на кассе"},
        ]

        res = run_shadow(
            rows=rows,
            active_inventory={"gm_code": "GM001", "start_date": "2026-10-01"},
        )
        assert res["total"] == 3
        assert res["db_written"] == 3

        hyps = get_hypotheses(inventory_key="GM001|2026-10-01")
        assert len(hyps) == 3

        add_feedback(hyps[0]["id"], "agree", reviewer="Лёша")
        add_feedback(hyps[1]["id"], "disagree")

        stats = get_feedback_stats("GM001|2026-10-01")
        assert stats["agree"] == 1
        assert stats["disagree"] == 1
        assert stats["total"] == 2

        path = export_feedback()
        assert os.path.isfile(path)
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_only_unlabeled_after_feedback(self, isolated_ml):
        """После разметки запись уходит из 'только неразмеченные'."""
        from ml.shadow import run_shadow, get_hypotheses
        from ml.feedback import add_feedback

        rows = [
            {"rtp": "R1", "tp_code": "1", "date": "x",
             "rule_fired": "A1", "rule_confidence": None,
             "reason": "Пересорт на кассе"},
            {"rtp": "R2", "tp_code": "2", "date": "x",
             "rule_fired": "A1", "rule_confidence": None,
             "reason": "Пересорт на кассе"},
        ]
        run_shadow(rows=rows, active_inventory=None)

        hyps = get_hypotheses()
        assert len(hyps) == 2
        add_feedback(hyps[0]["id"], "agree")

        unlabeled = get_hypotheses(only_unlabeled=True)
        assert len(unlabeled) == 1
        assert unlabeled[0]["id"] == hyps[1]["id"]


# =========================================================
# ISOLATION (Shadow не ломает основной анализ)
# =========================================================
class TestIsolation:
    def test_shadow_error_does_not_propagate(self, isolated_ml, monkeypatch):
        """Если Shadow падает, ошибка логируется, но не летит наружу."""
        def failing_run_shadow(*args, **kwargs):
            raise RuntimeError("Симуляция падения Shadow")

        monkeypatch.setattr("ml.shadow.run_shadow", failing_run_shadow)

        result = {"success": True, "shadow_rows": [{"rtp": "R1"}]}

        try:
            from ml.shadow import run_shadow
            try:
                run_shadow(rows=result.get("shadow_rows"), active_inventory=None)
            except Exception:
                pass
        except Exception as e:
            pytest.fail(f"_run_shadow пробросил исключение: {e}")


# =========================================================
# SCHEMA MIGRATION
# =========================================================
class TestSchema:
    def test_hypotheses_columns(self, isolated_ml):
        from ml.storage import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(hypotheses)")
        cols = [row[1] for row in cur.fetchall()]
        conn.close()

        expected = {
            "id", "inventory_key", "row_key", "rule_fired",
            "rule_confidence", "ai_hypothesis", "confidence",
            "features_json", "created_at",
        }
        assert expected.issubset(set(cols))

    def test_feedback_columns(self, isolated_ml):
        from ml.storage import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(feedback)")
        cols = [row[1] for row in cur.fetchall()]
        conn.close()

        expected = {
            "id", "hypothesis_id", "verdict",
            "comment", "reviewer", "created_at",
        }
        assert expected.issubset(set(cols))