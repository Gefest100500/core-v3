# core/dashboard_builder.py
"""
Сбор данных для дашборда «Общий пересчёт».

Чистая логика. Без PyQt. Без Dash. Тестируется отдельно.

Читает:
- actions_history.json     — история действий
- active_inventory.json    — активная инвентаризация
- inventory_archive.json   — архив инвентаризаций
- Готовые/Кванты/*.xlsx    — результаты квантов (Ревизор 1, Ревизор 2)

Возвращает:
- pandas.DataFrame — для таблиц
- dict             — для сводок

ИЗМЕНЕНИЯ:
- load_os_mbp_info удалён — ОС/МБП отдельный дашборд.
- Добавлены фильтры по периоду и ГМ в:
  load_history_filtered, load_inventory_archive_filtered, load_kv_results_filtered.
- kv_summary теперь принимает DataFrame — для гибкости.
- Пути к data/ вычисляются через get_data_dir() (функции _history_path,
  _active_inv_path, _archive_path) — данные лежат в %LOCALAPPDATA%,
  а не в корне проекта. Нужно для работы из Program Files и для
  тестов через monkeypatch.
"""
import json
import os
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import pandas as pd

from utils.file_utils import get_base_dir, get_data_dir
from utils.logger import log


# =========================================================
# ПУТИ (вычисляются при вызове, не при импорте)
# =========================================================
def _generated_dir() -> str:
    """Папка результатов (Готовые/) рядом с проектом."""
    return os.path.join(get_base_dir(), "Готовые")


def _history_path() -> str:
    """Путь к actions_history.json в папке данных (%LOCALAPPDATA%)."""
    return os.path.join(get_data_dir(), "actions_history.json")


def _active_inv_path() -> str:
    """Путь к active_inventory.json в папке данных (%LOCALAPPDATA%)."""
    return os.path.join(get_data_dir(), "active_inventory.json")


def _archive_path() -> str:
    """Путь к inventory_archive.json в папке данных (%LOCALAPPDATA%)."""
    return os.path.join(get_data_dir(), "inventory_archive.json")


# =========================================================
# JSON — БЕЗОПАСНОЕ ЧТЕНИЕ
# =========================================================
def _read_json(path: str) -> Any:
    """Читает JSON. При ошибке — возвращает None."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError) as e:
        log.warning(f"Не удалось прочитать {path}: {e}")
        return None


# =========================================================
# ИСТОРИЯ
# =========================================================
def load_history() -> pd.DataFrame:
    """Загружает историю действий как DataFrame.

    Колонки: timestamp, date, time, action, details, icon.
    """
    raw = _read_json(_history_path()) or []
    if not isinstance(raw, list):
        raw = []

    rows = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue

        ts_raw = entry.get("timestamp", "")
        dt = None
        try:
            dt = datetime.fromisoformat(ts_raw)
        except (ValueError, TypeError):
            pass

        rows.append({
            "timestamp": ts_raw,
            "date": dt.strftime("%d.%m.%Y") if dt else "",
            "time": dt.strftime("%H:%M") if dt else "",
            "date_obj": dt.date() if dt else None,
            "action": entry.get("action", ""),
            "details": entry.get("details", ""),
            "icon": entry.get("icon", ""),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)

    return df


def load_history_filtered(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    action_filter: Optional[str] = None,
) -> pd.DataFrame:
    """История с фильтрами.

    Args:
        date_from: с какого дня (включительно)
        date_to: по какой день (включительно)
        action_filter: подстрока в поле action

    Returns:
        Отфильтрованный DataFrame.
    """
    df = load_history()
    if df.empty:
        return df

    if date_from is not None and "date_obj" in df.columns:
        df = df[df["date_obj"].notna() & (df["date_obj"] >= date_from)]

    if date_to is not None and "date_obj" in df.columns:
        df = df[df["date_obj"].notna() & (df["date_obj"] <= date_to)]

    if action_filter:
        mask = df["action"].str.contains(action_filter, case=False, na=False)
        df = df[mask]

    return df.reset_index(drop=True)


# =========================================================
# АКТИВНАЯ ИНВЕНТАРИЗАЦИЯ
# =========================================================
def load_active_inventory() -> Optional[Dict[str, Any]]:
    """Загружает активную инвентаризацию. None, если нет."""
    raw = _read_json(_active_inv_path())
    if not isinstance(raw, dict):
        return None
    return raw


# =========================================================
# АРХИВ ИНВЕНТАРИЗАЦИЙ
# =========================================================
def load_inventory_archive() -> pd.DataFrame:
    """Загружает архив инвентаризаций как DataFrame."""
    raw = _read_json(_archive_path()) or []
    if not isinstance(raw, list):
        raw = []

    rows = []
    for inv in raw:
        if not isinstance(inv, dict):
            continue

        start_str = inv.get("start_date", "")
        start_obj = None
        try:
            start_obj = datetime.fromisoformat(start_str).date()
        except (ValueError, TypeError):
            pass

        rows.append({
            "gm_code": inv.get("gm_code", ""),
            "gm_name": inv.get("gm_name", ""),
            "variant": inv.get("variant", ""),
            "start_date": start_str,
            "end_date": inv.get("end_date", ""),
            "start_date_obj": start_obj,
            "days_passed": inv.get("days_passed", 0),
            "days_total": inv.get("days_total", 0),
            "sum_difference": inv.get("sum_difference"),
            "result_folder": inv.get("result_folder", ""),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("start_date", ascending=False).reset_index(drop=True)

    return df


def load_inventory_archive_filtered(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    gm_filter: Optional[str] = None,
) -> pd.DataFrame:
    """Архив с фильтрами по периоду и ГМ.

    Args:
        date_from: с какого дня (по start_date)
        date_to: по какой день (по start_date)
        gm_filter: подстрока в названии или коде ГМ
    """
    df = load_inventory_archive()
    if df.empty:
        return df

    if date_from is not None:
        df = df[
            df["start_date_obj"].notna()
            & (df["start_date_obj"] >= date_from)
        ]

    if date_to is not None:
        df = df[
            df["start_date_obj"].notna()
            & (df["start_date_obj"] <= date_to)
        ]

    if gm_filter:
        gm_lower = gm_filter.lower()
        mask = (
            df["gm_name"].str.lower().str.contains(gm_lower, na=False)
            | df["gm_code"].astype(str).str.contains(gm_lower, na=False)
        )
        df = df[mask]

    return df.reset_index(drop=True)


# =========================================================
# КВАНТЫ — РЕЗУЛЬТАТЫ
# =========================================================
def load_kv_results() -> pd.DataFrame:
    """Загружает результаты анализа квантов из Готовые/Кванты/.

    Колонки: _file, _reviewer + все колонки из исходного xlsx.
    """
    kv_dir = os.path.join(_generated_dir(), "Кванты")

    if not os.path.isdir(kv_dir):
        return pd.DataFrame()

    frames = []
    for name in ("Ревизор 1.xlsx", "Ревизор 2.xlsx"):
        path = os.path.join(kv_dir, name)
        if not os.path.isfile(path):
            continue

        try:
            df = pd.read_excel(path)
            df["_file"] = name
            df["_reviewer"] = name.replace(".xlsx", "")
            frames.append(df)
        except Exception as e:
            log.warning(f"Не удалось прочитать {path}: {e}")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    return combined


def load_kv_results_filtered(
    gm_filter: Optional[str] = None,
) -> pd.DataFrame:
    """Кванты с фильтром по ГМ.

    ВАЖНО: в самих файлах квантов НЕТ колонки ГМ.
    Фильтр по ГМ применяется только если он есть в данных
    (например, если в будущем добавим).

    Сейчас — фильтр по ГМ НЕ работает. Возвращает всё.
    Оставлен для будущего расширения.
    """
    df = load_kv_results()
    return df


def kv_summary(df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Сводка по квантам.

    Args:
        df: DataFrame с данными квантов. Если None — загружается.

    Returns:
        {
            "total_rows": int,
            "reviewers": {name: count},
            "reasons": [(reason, count), ...],  # отсортировано по count desc
            "loss_total": float,
        }
    """
    if df is None:
        df = load_kv_results()

    if df.empty:
        return {
            "total_rows": 0,
            "reviewers": {},
            "reasons": [],
            "loss_total": 0.0,
        }

    result: Dict[str, Any] = {
        "total_rows": len(df),
        "reviewers": {},
        "reasons": [],
        "loss_total": 0.0,
    }

    # Ревизоры
    if "_reviewer" in df.columns:
        result["reviewers"] = df["_reviewer"].value_counts().to_dict()

    # Причины
    reason_col = "Типовая причина"
    if reason_col in df.columns:
        counts = df[reason_col].fillna("(пусто)").value_counts()
        # Сортируем по убыванию
        result["reasons"] = list(counts.items())

    # Сумма потерь
    loss_col = "Потери (руб без НДС)"
    if loss_col in df.columns:
        try:
            losses = pd.to_numeric(df[loss_col], errors="coerce").fillna(0)
            result["loss_total"] = float(losses.sum())
        except Exception:
            pass

    return result


# =========================================================
# СПИСОК ГМ ДЛЯ АВТОКОМПЛИТА
# =========================================================
def load_gm_list() -> List[Dict[str, str]]:
    """Возвращает список ГМ для автокомплита.

    Объединяет:
    - gm_data.json (все известные магазины)
    - gm_code и gm_name из архива инвентаризаций

    Returns:
        [{"code": "...", "name": "...", "display": "code — name"}, ...]
    """
    result = []
    seen_codes = set()

    # Из архива инвентаризаций
    archive = load_inventory_archive()
    if not archive.empty:
        for _, row in archive.iterrows():
            code = str(row.get("gm_code", "")).strip()
            name = str(row.get("gm_name", "")).strip()
            if code and code not in seen_codes:
                seen_codes.add(code)
                result.append({
                    "code": code,
                    "name": name,
                    "display": f"{code} — {name}",
                })

    # Из gm_data.json
    gm_data = _read_json(os.path.join(get_data_dir(), "gm_data.json")) or []
    if isinstance(gm_data, list):
        for gm in gm_data:
            if not isinstance(gm, dict):
                continue
            code = str(gm.get("Код", "")).strip()
            name = str(gm.get("Название", "")).strip()
            if code and code not in seen_codes:
                seen_codes.add(code)
                result.append({
                    "code": code,
                    "name": name,
                    "display": f"{code} — {name}",
                })

    result.sort(key=lambda x: x["name"].lower())
    return result


# =========================================================
# ОБЩАЯ СВОДКА (ДЛЯ ГЛАВНОЙ ДАШБОРДА)
# =========================================================
def build_summary() -> Dict[str, Any]:
    """Собирает всё вместе для главной страницы дашборда.

    Returns:
        dict с ключами:
            active_inventory, archive_count, history_count,
            kv_summary
    """
    active = load_active_inventory()
    archive = load_inventory_archive()
    history = load_history()
    kv = kv_summary()

    return {
        "active_inventory": active,
        "archive_count": len(archive),
        "history_count": len(history),
        "kv_summary": kv,
    }