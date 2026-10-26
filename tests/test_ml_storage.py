# tests/test_ml_storage.py
"""
Тесты для ml/storage.py — функции очистки.

Покрываем:
- clear_all_hypotheses: удаление + архивация
- clear_by_inventory: точечная очистка
"""
import json
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
    monkeypatch.setattr("ml.storage.EXPORTS_DIR", str(exports_dir))
    monkeypatch.setattr("ml.shadow.SHADOW_REPORT_PATH", str(report_path))
    monkeypatch.setattr("ml.feedback.EXPORTS_DIR", str(exports_dir))

    return {
        "db_path": db_path,
        "exports_dir": exports_dir,
        "tmp_path": tmp_path,
    }


def _make_n(tmp_path, monkeypatch, n=3):
    """Создаёт n гипотез и возвращает их id."""
    from ml.shadow import run_shadow, get_hypotheses
    rows = [
        {"rtp": f"R{i}", "tp_code": str(i), "date": "x",
         "rule_fired": "A1", "reason": "Пересорт на кассе"}
        for i in range(n)
    ]
    run_shadow(rows=rows, active_inventory=None, clear_before=False)
    return [h["id"] for h in get_hypotheses()]


# =========================================================
# clear_all_hypotheses
# =========================================================
class TestClearAll:
    def test_empty(self, isolated_ml):
        from ml.storage import clear_all_hypotheses
        res = clear_all_hypotheses()
        assert res["hypotheses_deleted"] == 0
        assert res["feedback_archived"] == 0

    def test_deletes_all(self, isolated_ml, monkeypatch):
        from ml.storage import clear_all_hypotheses
        from ml.shadow import get_hypotheses
        _make_n(isolated_ml["tmp_path"], monkeypatch, n=5)

        assert len(get_hypotheses()) == 5

        res = clear_all_hypotheses()
        assert res["hypotheses_deleted"] == 5

        assert len(get_hypotheses()) == 0

    def test_archives_feedback(self, isolated_ml, monkeypatch):
        from ml.storage import clear_all_hypotheses
        from ml.feedback import add_feedback

        ids = _make_n(isolated_ml["tmp_path"], monkeypatch, n=3)
        add_feedback(ids[0], "agree", reviewer="Лёша")
        add_feedback(ids[1], "disagree")

        res = clear_all_hypotheses(archive_feedback=True)
        assert res["feedback_archived"] == 2

        archive_path = os.path.join(
            str(isolated_ml["exports_dir"]), "feedback_archive.jsonl"
        )
        assert os.path.isfile(archive_path)

        with open(archive_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2

        d = json.loads(lines[0])
        assert "archived_at" in d
        assert d["verdict"] in ("agree", "disagree")
        assert "row_key" in d

    def test_no_archive(self, isolated_ml, monkeypatch):
        from ml.storage import clear_all_hypotheses
        from ml.feedback import add_feedback

        ids = _make_n(isolated_ml["tmp_path"], monkeypatch, n=2)
        add_feedback(ids[0], "agree")

        res = clear_all_hypotheses(archive_feedback=False)
        assert res["feedback_archived"] == 0

        archive_path = os.path.join(
            str(isolated_ml["exports_dir"]), "feedback_archive.jsonl"
        )
        assert not os.path.isfile(archive_path)

    def test_archive_appends(self, isolated_ml, monkeypatch):
        """Второй архив — добавляется, а не перезаписывает."""
        from ml.storage import clear_all_hypotheses
        from ml.feedback import add_feedback

        ids = _make_n(isolated_ml["tmp_path"], monkeypatch, n=2)
        add_feedback(ids[0], "agree")
        clear_all_hypotheses(archive_feedback=True)

        ids2 = _make_n(isolated_ml["tmp_path"], monkeypatch, n=2)
        add_feedback(ids2[0], "disagree")
        clear_all_hypotheses(archive_feedback=True)

        archive_path = os.path.join(
            str(isolated_ml["exports_dir"]), "feedback_archive.jsonl"
        )
        with open(archive_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2


# =========================================================
# clear_by_inventory
# =========================================================
class TestClearByInventory:
    def test_specific(self, isolated_ml, monkeypatch):
        from ml.storage import clear_by_inventory
        from ml.shadow import run_shadow, get_hypotheses

        rows = [{"rtp": "R1", "tp_code": "1", "date": "x",
                 "rule_fired": "A1", "reason": "Пересорт на кассе"}]

        run_shadow(rows=rows,
                   active_inventory={"gm_code": "GM1", "start_date": "2026-10-01"},
                   clear_before=False)
        run_shadow(rows=rows,
                   active_inventory={"gm_code": "GM2", "start_date": "2026-10-02"},
                   clear_before=False)

        assert len(get_hypotheses()) == 2

        deleted = clear_by_inventory("GM1|2026-10-01")
        assert deleted == 1

        remaining = get_hypotheses()
        assert len(remaining) == 1
        assert remaining[0]["inventory_key"] == "GM2|2026-10-02"