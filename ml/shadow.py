# ml/shadow.py
"""
Shadow Engine — «Объяснитель правил» (v0.3).

Работает ПАРАЛЛЕЛЬНО с жёсткими правилами (A1, A2, B), НЕ влияет
на итоговую выгрузку ревизора. Пишет «Отчёт стажёра» в:

    Logs/shadow_report.jsonl   — сырой лог (по строке на запись)
    data/ml/shadow.sqlite      — таблица hypotheses

СМЕНА ПАРАДИГМЫ (v0.3):
    Раньше (v0.1, v0.2) Shadow искал АНОМАЛИИ — строки, где правила
    не сработали или сработали неуверенно. На реальных данных это
    давало 0 гипотез, потому что финальные правила kv_analyzer
    добивают причину ВСЕМ строкам.

    Теперь Shadow ОБЪЯСНЯЕТ решения правил. Для каждой строки он:
      1) Смотрит, какое правило сработало (rule_fired).
      2) Вычисляет УВЕРЕННОСТЬ — насколько сильно это правило.
      3) Формирует человеческое объяснение «почему так».
      4) Пишет ВСЕ строки в БД — это датасет для обучения.

    Цель: imitation learning. Модель учится повторять решения
    правил, а потом — превосходить их.

ВЕСА ПРАВИЛ (уверенность):
    A1 (Фрукты/овощи)           — 1.0  (чёткий признак: ГР 20)
    A2 (Сырьё)                  — 0.9  (два признака: ГР 20 + имя)
    B  (Местный поставщик)      — 0.7  (код ТП из операций)
    steal (Хищение)             — 0.6  (код из списка)
    box (Коробочный)            — 0.5  (отклонение < 50%)
    mirror (Зеркальный)         — 0.4  (отклонение < 25%)
    fallback (по знаку)         — 0.3  (правила молчат — «по умолчанию»)
    unknown (без причины)       — 0.1  (истинная аномалия)

ИЗМЕНЕНИЯ (v0.3.2):
- _explain_row() теперь кладёт в features все поля строки:
  tp_code, name, gr20, sign, doc, loss_amount, operation.
  Это нужно для боковой панели «Детали» во вкладке AI.
- run_shadow() получил параметр clear_before (по умолчанию True).
  Перед записью очищает таблицу hypotheses, сохраняя feedback
  в архив data/ml/exports/feedback_archive.jsonl.
"""
import json
from datetime import datetime
from typing import Optional

from utils.logger import log
from ml.config import (
    SHADOW_REPORT_PATH,
    DEFAULT_CONFIDENCE_THRESHOLD,
    ensure_dirs,
)
from ml.storage import get_connection


# =========================================================
# ВЕСА ПРАВИЛ
# =========================================================
RULE_A1 = "A1"
RULE_A2 = "A2"
RULE_B = "B"
RULE_STEAL = "steal"
RULE_BOX = "box"
RULE_MIRROR = "mirror"
RULE_FALLBACK = "fallback"
RULE_UNKNOWN = "unknown"

RULE_CONFIDENCE = {
    RULE_A1: 1.0,
    RULE_A2: 0.9,
    RULE_B: 0.7,
    RULE_STEAL: 0.6,
    RULE_BOX: 0.5,
    RULE_MIRROR: 0.4,
    RULE_FALLBACK: 0.3,
    RULE_UNKNOWN: 0.1,
}

RULE_LABELS = {
    RULE_A1: "A1 — Фрукты/овощи (чёткий признак ГР 20)",
    RULE_A2: "A2 — Сырьё (ГР 20 + наименование)",
    RULE_B: "B — Местный поставщик (код ТП из операций)",
    RULE_STEAL: "Хищение (код из списка)",
    RULE_BOX: "Коробочный (отклонение < 50%)",
    RULE_MIRROR: "Зеркальное отклонение (отклонение < 25%)",
    RULE_FALLBACK: "Fallback (правила молчат — причина по умолчанию)",
    RULE_UNKNOWN: "Без правила (истинная аномалия)",
}


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ
# =========================================================
def _build_row_key(row: dict) -> str:
    """Составной ключ строки: РТП + код ТП + дата."""
    parts = [
        str(row.get("rtp", "")).strip(),
        str(row.get("tp_code", "")).strip(),
        str(row.get("date", "")).strip(),
    ]
    return "|".join(p for p in parts if p)


def _build_inventory_key(active_inventory: Optional[dict]) -> str:
    """Ключ инвентаризации: ГМ + дата начала."""
    if not active_inventory:
        return "unknown"
    gm = active_inventory.get("gm_code", "?")
    start = active_inventory.get("start_date", "?")
    return f"{gm}|{start}"


def _make_explanation(rule: str, row: dict) -> str:
    """Человеческое объяснение: почему правило сработало именно так."""
    label = RULE_LABELS.get(rule, rule)
    reason = (row.get("reason") or "").strip()

    if rule == RULE_UNKNOWN:
        return "Ни одно правило не сработало, причина пустая — истинная аномалия."

    if rule == RULE_FALLBACK:
        return (
            f"Правила молчат. Причина «{reason}» поставлена по умолчанию "
            f"(по знаку Излишек/Недостача). Возможно, здесь что-то другое."
        )

    return f"Сработало правило: {label}. Причина: «{reason}»."


def _explain_row(row: dict, threshold: float) -> dict:
    """Объясняет решение правил по строке.

    Возвращает словарь:
        {
            "rule_fired": str,
            "confidence": float,
            "explanation": str,
            "features": dict,
        }

    features содержит:
        - rule: метка правила (A1/A2/B/…)
        - reason: типовая причина
        - tp_code: код ТП
        - name: наименование ТП
        - gr20: группа 20
        - sign: «Излишек» / «Недостача»
        - doc: номер документа
        - loss_amount: сумма потерь
        - operation: название операции из РТП
    """
    rule = row.get("rule_fired")
    reason = (row.get("reason") or "").strip()

    # Готовим общие признаки — они одинаковы во всех ветках
    base_features = {
        "rule": rule,
        "reason": reason,
        "tp_code": str(row.get("tp_code", "")).strip(),
        "name": str(row.get("name", "")).strip(),
        "gr20": str(row.get("gr20", "")).strip(),
        "sign": str(row.get("sign", "")).strip(),
        "doc": str(row.get("doc", "")).strip(),
        "loss_amount": row.get("loss_amount", 0.0),
        "operation": str(row.get("operation", "")).strip(),
    }

    # Случай 1: правило есть — берём его вес
    if rule and rule in RULE_CONFIDENCE:
        conf = RULE_CONFIDENCE[rule]
        return {
            "rule_fired": rule,
            "confidence": conf,
            "explanation": _make_explanation(rule, row),
            "features": base_features,
        }

    # Случай 2: правило неизвестное — считаем как fallback
    if rule:
        return {
            "rule_fired": RULE_FALLBACK,
            "confidence": RULE_CONFIDENCE[RULE_FALLBACK],
            "explanation": _make_explanation(RULE_FALLBACK, row),
            "features": base_features,
        }

    # Случай 3: правило не сработало
    if not reason:
        return {
            "rule_fired": RULE_UNKNOWN,
            "confidence": RULE_CONFIDENCE[RULE_UNKNOWN],
            "explanation": _make_explanation(RULE_UNKNOWN, row),
            "features": base_features,
        }

    # Причина есть, но правило не из жёстких — fallback
    return {
        "rule_fired": RULE_FALLBACK,
        "confidence": RULE_CONFIDENCE[RULE_FALLBACK],
        "explanation": _make_explanation(RULE_FALLBACK, row),
        "features": base_features,
    }


# =========================================================
# ПУБЛИЧНЫЙ API
# =========================================================
def run_shadow(
    rows: list,
    active_inventory: Optional[dict] = None,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    clear_before: bool = True,
) -> dict:
    """Прогоняет строки через Shadow Engine v0.3.

    ВАЖНО: пишет ВСЕ строки — это датасет для обучения.

    Args:
        rows: список словарей-строк с полями
              rtp, tp_code, date, rule_fired, rule_confidence, reason,
              name, gr20, sign, doc, loss_amount, operation.
        active_inventory: словарь активной инвентаризации.
        threshold: порог уверенности (не используется в v0.3).
        clear_before: если True — перед записью очищает таблицу
                      hypotheses (сохраняя feedback в архив).

    Returns:
        {
            "total": int,
            "explanations": int,
            "hypotheses": int,
            "db_written": int,
            "path": str,
        }
    """
    ensure_dirs()

    inventory_key = _build_inventory_key(active_inventory)
    now = datetime.now().isoformat(timespec="seconds")

    # --- Очистка старой базы ---
    if clear_before:
        try:
            from ml.storage import clear_all_hypotheses
            clear_result = clear_all_hypotheses(archive_feedback=True)
            log.info(
                f"ml.shadow: очистка базы — "
                f"удалено {clear_result['hypotheses_deleted']} записей, "
                f"архивировано {clear_result['feedback_archived']} фидбэков"
            )
        except Exception as e:
            log.exception(f"ml.shadow: ошибка очистки — {e}")

    explanations = []
    for row in rows:
        exp = _explain_row(row, threshold)
        row_key = _build_row_key(row)

        record = {
            "inventory_key": inventory_key,
            "row_key": row_key,
            "rule_fired": exp["rule_fired"],
            "rule_confidence": exp["confidence"],
            "ai_hypothesis": exp["explanation"],
            "confidence": exp["confidence"],
            "features": exp["features"],
            "created_at": now,
        }
        explanations.append(record)

    # --- Пишем JSONL (append) ---
    try:
        with open(SHADOW_REPORT_PATH, "a", encoding="utf-8") as f:
            for rec in explanations:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log.info(
            f"ml.shadow: {len(explanations)} объяснений → {SHADOW_REPORT_PATH}"
        )
    except Exception as e:
        log.exception(f"ml.shadow: ошибка записи JSONL — {e}")

    # --- Пишем в SQLite ---
    db_written = 0
    conn = get_connection()
    if conn is not None:
        try:
            cur = conn.cursor()
            for rec in explanations:
                cur.execute("""
                    INSERT INTO hypotheses (
                        inventory_key, row_key, rule_fired,
                        rule_confidence, ai_hypothesis, confidence,
                        features_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rec["inventory_key"],
                    rec["row_key"],
                    rec["rule_fired"],
                    rec["rule_confidence"],
                    rec["ai_hypothesis"],
                    rec["confidence"],
                    json.dumps(rec["features"], ensure_ascii=False),
                    rec["created_at"],
                ))
                db_written += 1
            conn.commit()
            log.info(f"ml.shadow: {db_written} записей в SQLite")
        except Exception as e:
            log.exception(f"ml.shadow: ошибка записи в SQLite — {e}")
        finally:
            conn.close()

    return {
        "total": len(rows),
        "explanations": len(explanations),
        "hypotheses": len(explanations),
        "db_written": db_written,
        "path": SHADOW_REPORT_PATH,
    }


def get_hypotheses(
    inventory_key: Optional[str] = None,
    only_unlabeled: bool = False,
    max_confidence: Optional[float] = None,
) -> list:
    """Читает записи из SQLite.

    Args:
        inventory_key: фильтр по инвентаризации.
        only_unlabeled: только без разметки.
        max_confidence: только записи с confidence <= порога.

    Returns:
        Список записей, отсортированных по уверенности (возрастание).
    """
    conn = get_connection()
    if conn is None:
        return []

    try:
        conn.row_factory = __import__("sqlite3").Row
        cur = conn.cursor()

        if only_unlabeled:
            base_sql = """
                SELECT h.* FROM hypotheses h
                LEFT JOIN feedback f ON f.hypothesis_id = h.id
                WHERE f.id IS NULL
            """
        else:
            base_sql = "SELECT h.* FROM hypotheses h WHERE 1=1"

        params = []
        if inventory_key:
            base_sql += " AND h.inventory_key = ?"
            params.append(inventory_key)

        if max_confidence is not None:
            base_sql += " AND h.confidence <= ?"
            params.append(max_confidence)

        base_sql += " ORDER BY h.confidence ASC NULLS FIRST, h.id DESC"

        cur.execute(base_sql, params)

        rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["features"] = json.loads(d.pop("features_json", "{}"))
            except Exception:
                d["features"] = {}
            result.append(d)
        return result
    except Exception as e:
        log.exception(f"ml.shadow.get_hypotheses: {e}")
        return []
    finally:
        conn.close()


def get_confidence_stats(inventory_key: Optional[str] = None) -> dict:
    """Статистика по уверенности: total / avg / min / max."""
    conn = get_connection()
    if conn is None:
        return {"total": 0, "avg": 0.0, "min": 0.0, "max": 0.0}

    try:
        cur = conn.cursor()
        if inventory_key:
            cur.execute(
                "SELECT COUNT(*), AVG(confidence), MIN(confidence), MAX(confidence) "
                "FROM hypotheses WHERE inventory_key = ?",
                (inventory_key,),
            )
        else:
            cur.execute(
                "SELECT COUNT(*), AVG(confidence), MIN(confidence), MAX(confidence) "
                "FROM hypotheses"
            )

        row = cur.fetchone()
        total, avg, mn, mx = row if row else (0, 0.0, 0.0, 0.0)
        return {
            "total": total or 0,
            "avg": round(avg, 3) if avg is not None else 0.0,
            "min": round(mn, 3) if mn is not None else 0.0,
            "max": round(mx, 3) if mx is not None else 0.0,
        }
    except Exception as e:
        log.exception(f"ml.shadow.get_confidence_stats: {e}")
        return {"total": 0, "avg": 0.0, "min": 0.0, "max": 0.0}
    finally:
        conn.close()