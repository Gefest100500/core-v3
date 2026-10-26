# ml/feedback.py
"""
Feedback Loop — приём разметки от ревизора.

Ревизор во вкладке AI нажимает «Согласен» / «Не согласен» —
эта функция пишет вердикт в SQLite (таблица feedback).

Позже, когда накопится N записей, ml/train.py переобучит модель.
"""
import json
import os
from datetime import datetime

from utils.logger import log
from ml.config import EXPORTS_DIR, ensure_dirs
from ml.storage import get_connection


def add_feedback(
    hypothesis_id: int,
    verdict: str,
    comment: str = "",
    reviewer: str = "",
) -> bool:
    """Записывает вердикт ревизора.

    Args:
        hypothesis_id: id гипотезы из таблицы hypotheses.
        verdict: 'agree' или 'disagree'.
        comment: опциональный комментарий ревизора.
        reviewer: имя ревизора (для аудита).

    Returns:
        True, если запись прошла успешно.
    """
    if verdict not in ("agree", "disagree"):
        log.warning(f"ml.feedback: неверный verdict '{verdict}'")
        return False

    conn = get_connection()
    if conn is None:
        return False

    try:
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute("""
            INSERT INTO feedback (
                hypothesis_id, verdict, comment, reviewer, created_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (hypothesis_id, verdict, comment, reviewer, now))
        conn.commit()
        log.info(f"ml.feedback: гипотеза {hypothesis_id} → {verdict}")
        return True
    except Exception as e:
        log.exception(f"ml.feedback.add_feedback: {e}")
        return False
    finally:
        conn.close()


def get_feedback_stats(inventory_key: str = None) -> dict:
    """Сводка по разметке: сколько agree / disagree / всего."""
    conn = get_connection()
    if conn is None:
        return {"agree": 0, "disagree": 0, "total": 0}

    try:
        cur = conn.cursor()
        if inventory_key:
            cur.execute("""
                SELECT f.verdict, COUNT(*) FROM feedback f
                JOIN hypotheses h ON h.id = f.hypothesis_id
                WHERE h.inventory_key = ?
                GROUP BY f.verdict
            """, (inventory_key,))
        else:
            cur.execute(
                "SELECT verdict, COUNT(*) FROM feedback GROUP BY verdict"
            )

        stats = {"agree": 0, "disagree": 0, "total": 0}
        for verdict, count in cur.fetchall():
            stats[verdict] = count
            stats["total"] += count
        return stats
    except Exception as e:
        log.exception(f"ml.feedback.get_feedback_stats: {e}")
        return {"agree": 0, "disagree": 0, "total": 0}
    finally:
        conn.close()


def export_feedback(path: str = None) -> str:
    """Экспорт разметки в JSONL.

    Returns:
        Путь к файлу экспорта (или пустая строка при ошибке).
    """
    ensure_dirs()

    if path is None:
        path = os.path.join(EXPORTS_DIR, "feedback_export.jsonl")

    conn = get_connection()
    if conn is None:
        return ""

    try:
        conn.row_factory = __import__("sqlite3").Row
        cur = conn.cursor()
        cur.execute("""
            SELECT
                h.id AS hypothesis_id,
                h.inventory_key,
                h.row_key,
                h.rule_fired,
                h.ai_hypothesis,
                h.confidence,
                f.verdict,
                f.comment,
                f.reviewer,
                f.created_at
            FROM feedback f
            JOIN hypotheses h ON h.id = f.hypothesis_id
            ORDER BY f.created_at
        """)
        with open(path, "w", encoding="utf-8") as f:
            for row in cur.fetchall():
                f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
        log.info(f"ml.feedback: экспорт → {path}")
        return path
    except Exception as e:
        log.exception(f"ml.feedback.export_feedback: {e}")
        return ""
    finally:
        conn.close()