# ml/storage.py
"""
Работа с SQLite для ML-модуля.

Единая точка: подключение, создание схемы, миграции.

Таблицы:
    hypotheses — объяснения решений правил (Shadow Engine)
    feedback   — разметка ревизоров

ИЗМЕНЕНИЯ:
- Добавлены clear_all_hypotheses() и clear_by_inventory().
  clear_all_hypotheses() перед удалением архивирует feedback
  в data/ml/exports/feedback_archive.jsonl (append), чтобы
  разметка не терялась.
"""
import json
import os
import sqlite3
from datetime import datetime

from utils.logger import log
from ml.config import SHADOW_DB_PATH, EXPORTS_DIR, ensure_dirs


def get_connection():
    """Возвращает подключение к БД, создавая схему при необходимости.

    Returns:
        sqlite3.Connection или None, если SQLite недоступен.
    """
    try:
        ensure_dirs()
        conn = sqlite3.connect(SHADOW_DB_PATH)
        _ensure_schema(conn)
        return conn
    except Exception as e:
        log.warning(f"ml.storage: SQLite недоступен — {e}")
        return None


def _ensure_schema(conn):
    """Создаёт таблицы, если их нет."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hypotheses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_key TEXT,
            row_key TEXT,
            rule_fired TEXT,
            rule_confidence REAL,
            ai_hypothesis TEXT,
            confidence REAL,
            features_json TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hypothesis_id INTEGER NOT NULL,
            verdict TEXT NOT NULL,
            comment TEXT,
            reviewer TEXT,
            created_at TEXT,
            FOREIGN KEY(hypothesis_id) REFERENCES hypotheses(id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_feedback_hyp
        ON feedback(hypothesis_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_hyp_inventory
        ON hypotheses(inventory_key)
    """)
    conn.commit()


# =========================================================
# ОЧИСТКА
# =========================================================
def clear_all_hypotheses(archive_feedback: bool = True) -> dict:
    """Удаляет все записи из hypotheses.

    ВАЖНО: перед удалением опционально архивирует feedback в JSONL,
    чтобы разметка не потерялась.

    Args:
        archive_feedback: если True — сохранить feedback в
                          data/ml/exports/feedback_archive.jsonl (append).

    Returns:
        {
            "hypotheses_deleted": int,
            "feedback_archived": int,
        }
    """
    ensure_dirs()

    conn = get_connection()
    if conn is None:
        return {"hypotheses_deleted": 0, "feedback_archived": 0}

    try:
        cur = conn.cursor()

        # --- 1. Архивация feedback ---
        archived = 0
        if archive_feedback:
            try:
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
                rows = cur.fetchall()

                if rows:
                    archive_path = os.path.join(
                        EXPORTS_DIR, "feedback_archive.jsonl"
                    )
                    with open(archive_path, "a", encoding="utf-8") as fp:
                        for row in rows:
                            d = {
                                "archived_at": datetime.now().isoformat(timespec="seconds"),
                                "hypothesis_id": row[0],
                                "inventory_key": row[1],
                                "row_key": row[2],
                                "rule_fired": row[3],
                                "ai_hypothesis": row[4],
                                "confidence": row[5],
                                "verdict": row[6],
                                "comment": row[7],
                                "reviewer": row[8],
                                "created_at": row[9],
                            }
                            fp.write(json.dumps(d, ensure_ascii=False) + "\n")
                    archived = len(rows)
                    log.info(f"ml.storage: {archived} фидбэков → {archive_path}")
            except Exception as e:
                log.exception(f"ml.storage: ошибка архивации feedback — {e}")

        # --- 2. Удаление feedback (FK на hypotheses) ---
        cur.execute("DELETE FROM feedback")
        feedback_deleted = cur.rowcount

        # --- 3. Удаление hypotheses ---
        cur.execute("DELETE FROM hypotheses")
        hypotheses_deleted = cur.rowcount

        conn.commit()

        log.info(
            f"ml.storage: очистка — "
            f"hypotheses: {hypotheses_deleted}, "
            f"feedback: {feedback_deleted}, "
            f"архивировано: {archived}"
        )

        return {
            "hypotheses_deleted": hypotheses_deleted,
            "feedback_archived": archived,
        }
    except Exception as e:
        log.exception(f"ml.storage.clear_all_hypotheses: {e}")
        return {"hypotheses_deleted": 0, "feedback_archived": 0}
    finally:
        conn.close()


def clear_by_inventory(inventory_key: str) -> int:
    """Удаляет записи hypotheses для конкретной инвентаризации.

    Используется, если хочешь чистить точечно, а не всё.

    Returns:
        Число удалённых записей hypotheses.
    """
    conn = get_connection()
    if conn is None:
        return 0

    try:
        cur = conn.cursor()

        # Сначала — feedback для этих hypotheses
        cur.execute("""
            DELETE FROM feedback
            WHERE hypothesis_id IN (
                SELECT id FROM hypotheses WHERE inventory_key = ?
            )
        """, (inventory_key,))

        # Потом — сами hypotheses
        cur.execute(
            "DELETE FROM hypotheses WHERE inventory_key = ?",
            (inventory_key,),
        )
        deleted = cur.rowcount
        conn.commit()

        log.info(
            f"ml.storage: очистка по inventory_key='{inventory_key}' — "
            f"{deleted} записей"
        )
        return deleted
    except Exception as e:
        log.exception(f"ml.storage.clear_by_inventory: {e}")
        return 0
    finally:
        conn.close()