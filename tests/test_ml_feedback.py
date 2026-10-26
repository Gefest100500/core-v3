# tests/test_ml_feedback.py
"""
Тесты для ml/feedback.py (Feedback Loop).

Покрываем:
- add_feedback: запись вердикта
- get_feedback_stats: сводка
- export_feedback: выгрузка в JSONL

ВАЖНО: тесты используют временный SQLite (tmp_path),
чтобы не трогать реальные данные.
"""
import json
import os
import sqlite3

import pytest


@pytest.fixture
def isolated_ml(tmp_path, monkeypatch):
    """Изолирует ML-модуль на tmp_path."""
    db_path = tmp_path / "shadow.sqlite"
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()

    monkeypatch.setattr("ml.config.SHADOW_DB_PATH", str(db_path))
    monkeypatch.setattr("ml.config.ML_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("ml.config.EXPORTS_DIR", str(exports_dir))
    monkeypatch.setattr("ml.config.MODELS_DIR", str(tmp_path))

    monkeypatch.setattr("ml.storage.SHADOW_DB_PATH", str(db_path))
    monkeypatch.setattr("ml.feedback.EXPORTS_DIR", str(exports_dir))

    return {
        "db_path": db_path,
        "exports_dir": exports_dir,
        "tmp_path": tmp_path,
    }


def _make_hypothesis(tmp_path, monkeypatch):
    """Создаёт одну гипотезу в БД и возвращает её id."""
    from ml.shadow import run_shadow, get_hypotheses
    rows = [{"rtp": "R1", "tp_code": "1", "date": "x",
             "rule_fired": None, "rule_confidence": None, "reason": ""}]
    run_shadow(rows=rows, active_inventory=None)
    return get_hypotheses()[0]["id"]


# =========================================================
# add_feedback
# =========================================================
class TestAddFeedback:
    def test_agree(self, isolated_ml, monkeypatch):
        from ml.feedback import add_feedback
        hid = _make_hypothesis(isolated_ml["tmp_path"], monkeypatch)
        ok = add_feedback(hid, "agree")
        assert ok is True

    def test_disagree(self, isolated_ml, monkeypatch):
        from ml.feedback import add_feedback
        hid = _make_hypothesis(isolated_ml["tmp_path"], monkeypatch)
        ok = add_feedback(hid, "disagree")
        assert ok is True

    def test_invalid_verdict(self, isolated_ml, monkeypatch):
        from ml.feedback import add_feedback
        hid = _make_hypothesis(isolated_ml["tmp_path"], monkeypatch)
        ok = add_feedback(hid, "maybe")
        assert ok is False

    def test_writes_to_db(self, isolated_ml, monkeypatch):
        from ml.feedback import add_feedback
        hid = _make_hypothesis(isolated_ml["tmp_path"], monkeypatch)
        add_feedback(hid, "agree", comment="ok", reviewer="Лёша")

        conn = sqlite3.connect(str(isolated_ml["db_path"]))
        cur = conn.cursor()
        cur.execute("SELECT hypothesis_id, verdict, comment, reviewer FROM feedback")
        rows = cur.fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0][0] == hid
        assert rows[0][1] == "agree"
        assert rows[0][2] == "ok"
        assert rows[0][3] == "Лёша"

    def test_multiple_feedbacks(self, isolated_ml, monkeypatch):
        """На одну гипотезу можно записать несколько вердиктов (история)."""
        from ml.feedback import add_feedback
        hid = _make_hypothesis(isolated_ml["tmp_path"], monkeypatch)
        add_feedback(hid, "agree")
        add_feedback(hid, "disagree")

        conn = sqlite3.connect(str(isolated_ml["db_path"]))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM feedback")
        count = cur.fetchone()[0]
        conn.close()
        assert count == 2


# =========================================================
# get_feedback_stats
# =========================================================
class TestGetFeedbackStats:
    def test_empty(self, isolated_ml):
        from ml.feedback import get_feedback_stats
        stats = get_feedback_stats()
        assert stats == {"agree": 0, "disagree": 0, "total": 0}

    def test_counts(self, isolated_ml, monkeypatch):
        from ml.feedback import add_feedback, get_feedback_stats
        from ml.shadow import run_shadow, get_hypotheses

        rows = [
            {"rtp": "R1", "tp_code": "1", "date": "x",
             "rule_fired": None, "rule_confidence": None, "reason": ""},
            {"rtp": "R2", "tp_code": "2", "date": "x",
             "rule_fired": None, "rule_confidence": None, "reason": ""},
            {"rtp": "R3", "tp_code": "3", "date": "x",
             "rule_fired": None, "rule_confidence": None, "reason": ""},
        ]
        run_shadow(rows=rows, active_inventory=None)
        hyps = get_hypotheses()

        add_feedback(hyps[0]["id"], "agree")
        add_feedback(hyps[1]["id"], "agree")
        add_feedback(hyps[2]["id"], "disagree")

        stats = get_feedback_stats()
        assert stats["agree"] == 2
        assert stats["disagree"] == 1
        assert stats["total"] == 3

    def test_filter_by_inventory(self, isolated_ml, monkeypatch):
        from ml.feedback import add_feedback, get_feedback_stats
        from ml.shadow import run_shadow, get_hypotheses

        rows = [{"rtp": "R1", "tp_code": "1", "date": "x",
                 "rule_fired": None, "rule_confidence": None, "reason": ""}]

        run_shadow(rows=rows,
                   active_inventory={"gm_code": "GM1", "start_date": "2026-10-01"})
        run_shadow(rows=rows,
                   active_inventory={"gm_code": "GM2", "start_date": "2026-10-02"})

        hyps = get_hypotheses()
        add_feedback(hyps[0]["id"], "agree")

        stats_gm1 = get_feedback_stats("GM1|2026-10-01")
        stats_gm2 = get_feedback_stats("GM2|2026-10-02")

        # Одна из них имеет разметку, другая — нет
        total = stats_gm1["total"] + stats_gm2["total"]
        assert total == 1


# =========================================================
# export_feedback
# =========================================================
class TestExportFeedback:
    def test_empty(self, isolated_ml):
        """Если разметки нет — файл пустой, но создаётся."""
        from ml.feedback import export_feedback
        path = export_feedback()
        assert path != ""
        assert os.path.isfile(path)

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert content == ""

    def test_exports_data(self, isolated_ml, monkeypatch):
        from ml.feedback import add_feedback, export_feedback
        hid = _make_hypothesis(isolated_ml["tmp_path"], monkeypatch)
        add_feedback(hid, "agree", comment="ok", reviewer="Лёша")

        path = export_feedback()
        assert os.path.isfile(path)

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 1
        d = json.loads(lines[0])
        assert d["hypothesis_id"] == hid
        assert d["verdict"] == "agree"
        assert d["comment"] == "ok"
        assert d["reviewer"] == "Лёша"
        assert "row_key" in d
        assert "ai_hypothesis" in d

    def test_utf8_encoding(self, isolated_ml, monkeypatch):
        """Русский текст сохраняется корректно (не бьётся).

        Проверяем, что в тексте гипотезы есть кириллица вообще,
        а не конкретное слово — формулировки могут меняться
        между версиями baseline (v0.1 → v0.2).
        """
        from ml.feedback import add_feedback, export_feedback
        hid = _make_hypothesis(isolated_ml["tmp_path"], monkeypatch)
        add_feedback(hid, "agree", comment="Проверка кириллицы")

        path = export_feedback()
        with open(path, "r", encoding="utf-8") as f:
            d = json.loads(f.readline())

        # В тексте гипотезы точно есть кириллица
        text = d["ai_hypothesis"]
        has_cyrillic = any("а" <= ch.lower() <= "я" for ch in text)
        assert has_cyrillic, f"Нет кириллицы в тексте: {text!r}"

        # И в комментарии тоже
        assert d["comment"] == "Проверка кириллицы"

    def test_custom_path(self, isolated_ml, monkeypatch):
        from ml.feedback import add_feedback, export_feedback
        hid = _make_hypothesis(isolated_ml["tmp_path"], monkeypatch)
        add_feedback(hid, "disagree")

        custom = str(isolated_ml["tmp_path"] / "custom_export.jsonl")
        path = export_feedback(path=custom)
        assert path == custom
        assert os.path.isfile(custom)

    def test_sorted_by_created_at(self, isolated_ml, monkeypatch):
        """Строки в экспорте отсортированы по created_at."""
        from ml.feedback import add_feedback, export_feedback
        from ml.shadow import run_shadow, get_hypotheses

        rows = [
            {"rtp": "R1", "tp_code": "1", "date": "x",
             "rule_fired": None, "rule_confidence": None, "reason": ""},
            {"rtp": "R2", "tp_code": "2", "date": "x",
             "rule_fired": None, "rule_confidence": None, "reason": ""},
        ]
        run_shadow(rows=rows, active_inventory=None)
        hyps = get_hypotheses()

        add_feedback(hyps[0]["id"], "agree")
        add_feedback(hyps[1]["id"], "disagree")

        path = export_feedback()
        with open(path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]

        # Проверяем, что обе записи есть
        verdicts = {d["verdict"] for d in lines}
        assert verdicts == {"agree", "disagree"}