# core/inventory_helper.py
"""
Чистая логика для вкладки «Инвентаризация».

Здесь нет PyQt. Только функции, которые можно тестировать отдельно:
- Поиск ГМ по коду.
- Работа с вариантами планов (названия, ключи).
- Формирование чек-листа и расчёт прогресса.
- Расчёт дат (окончание, текущий день).
- Форматирование дат.
"""
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional


def find_gm_by_code(code: str, gm_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Ищет ГМ по точному коду (без учёта пробелов)."""
    code = str(code).strip()
    for gm in gm_data:
        if str(gm.get("Код", "")).strip() == code:
            return gm
    return None


def get_variant_values(plans: Dict[str, Any]) -> List[str]:
    """Возвращает список названий вариантов для ComboBox."""
    if not plans:
        return ["(нет доступных вариантов)"]
    values = []
    for key in sorted(plans.keys()):
        plan = plans[key]
        title = plan.get("title", key)
        values.append(title)
    return values


def get_variant_key_from_title(title: str, plans: Dict[str, Any]) -> Optional[str]:
    """Находит ключ варианта по его названию."""
    for key, plan in plans.items():
        if plan.get("title", key) == title:
            return key
    return None


def build_empty_checklist(plan: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, bool]]]:
    """Формирует пустой чек-лист по плану.

    Структура: {day_1: {shift_1: {"0": False, ...}, ...}, ...}
    """
    checklist_state = {}
    for day_data in plan.get("days", []):
        day_num = day_data.get("day_num", 1)
        day_key = f"day_{day_num}"
        checklist_state[day_key] = {}
        for shift_idx, shift_data in enumerate(day_data.get("shifts", [])):
            shift_key = f"shift_{shift_idx + 1}"
            tasks = shift_data.get("tasks", [])
            checklist_state[day_key][shift_key] = {
                str(i): False for i in range(len(tasks))
            }
    return checklist_state


def calculate_end_date(start_date: date, days_total: int) -> date:
    """Вычисляет дату окончания инвентаризации.

    Если days_total <= 0 — возвращает start_date.
    """
    if days_total <= 0:
        return start_date
    return start_date + timedelta(days=days_total - 1)


def calculate_days_passed(start_date: date, days_total: int) -> int:
    """Считает, какой по счёту день инвентаризации идёт сейчас.

    Ограничен диапазоном [1, days_total].
    """
    if days_total <= 0:
        return 1
    try:
        passed = (date.today() - start_date).days + 1
        return max(1, min(passed, days_total))
    except Exception:
        return 1


def calculate_progress(
    checklist: Dict[str, Any],
    plan: Dict[str, Any],
) -> Dict[str, int]:
    """Считает прогресс по всему чек-листу.

    Возвращает:
        {"done": int, "total": int, "percent": int}
    """
    total_all = 0
    done_all = 0

    for d in plan.get("days", []):
        d_num = d.get("day_num", 1)
        d_key = f"day_{d_num}"
        d_state = checklist.get(d_key, {})

        for shift_idx, shift_data in enumerate(d.get("shifts", [])):
            s_key = f"shift_{shift_idx + 1}"
            tasks = shift_data.get("tasks", [])
            s_state = d_state.get(s_key, {})

            total_all += len(tasks)
            done_all += sum(
                1 for i in range(len(tasks)) if s_state.get(str(i), False)
            )

    percent = int((done_all / total_all) * 100) if total_all > 0 else 0
    return {"done": done_all, "total": total_all, "percent": percent}


def format_date_ru(iso_str: str) -> str:
    """Форматирует ISO-дату в dd.MM.yyyy.

    Если строка пустая или битая — возвращает исходную (или «—»).
    """
    if not iso_str:
        return "—"
    try:
        return datetime.fromisoformat(iso_str).strftime("%d.%m.%Y")
    except Exception:
        return iso_str


def get_day_data(plan: Dict[str, Any], day_num: int) -> Optional[Dict[str, Any]]:
    """Возвращает данные конкретного дня из плана (или None)."""
    for d in plan.get("days", []):
        if d.get("day_num") == day_num:
            return d
    return None