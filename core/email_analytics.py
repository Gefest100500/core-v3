# core/email_analytics.py
"""
Аналитика по сохранённым письмам инвентаризации.
(Возвращен к исходному рабочему состоянию + добавлена функция для суммы без РМ и МЦ)
"""
import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.email_storage import load_emails
from utils.logger import log


ZONES_CANONICAL = [
    "Алкоголь", "Косметика и Бытовая химия", "Весовые конфеты",
    "Заморозка", "Непрофиль", "Охлажденка", "Продукты",
    "Сигареты", "Фреш", "Алкоголь НД",
]

ZONE_MAP = [
    ("Алкоголь НД", "Алкоголь НД"), ("Алкоголь", "Алкоголь"),
    ("Косметика и Бытовая химия", "Косметика и Бытовая химия"),
    ("Косметика", "Косметика и Бытовая химия"),
    ("Бытовая химия", "Косметика и Бытовая химия"),
    ("Весовые конфеты", "Весовые конфеты"),
    ("Замороженная продукция", "Заморозка"), ("Заморозка", "Заморозка"),
    ("Непрофиль", "Непрофиль"),
    ("Охлажденная продукция", "Охлажденка"), ("Охлажденка", "Охлажденка"),
    ("Продукты", "Продукты"),
    ("Табачные изделия", "Сигареты"), ("Сигареты", "Сигареты"),
    ("Фреш", "Фреш"),
]

_QUOTE_CHARS = ('"', '«', '»', "'", '`', '“', '”', '‘', '’')


def _normalize_label_text(text: str) -> str:
    if not text:
        return ""
    s = text.lower()
    for q in _QUOTE_CHARS:
        s = s.replace(q, '')
    s = " ".join(s.split())
    return s


def extract_zone(label: str) -> Optional[str]:
    if not label:
        return None
    normalized = _normalize_label_text(label)
    if not normalized or normalized.startswith("перепроверка"):
        return None
    for marker, canonical in ZONE_MAP:
        marker_norm = _normalize_label_text(marker)
        if marker_norm and marker_norm in normalized:
            return canonical
    return None


ZONE_COLORS = [
    "#D42626", "#4CAF50", "#6366f1", "#FFD700", "#FF5252",
    "#00BCD4", "#9C27B0", "#FF9800", "#795548", "#607D8B",
    "#E91E63", "#3F51B5", "#8BC34A", "#FFC107", "#00E676",
    "#F44336", "#009688", "#673AB7", "#CDDC39", "#FF5722",
]


def get_zone_color(zone_name: str) -> str:
    if not zone_name:
        return ZONE_COLORS[0]
    h = int(hashlib.md5(zone_name.encode("utf-8")).hexdigest(), 16)
    return ZONE_COLORS[h % len(ZONE_COLORS)]


def _parse_ddmmyyyy(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d.%m.%Y")
    except (ValueError, TypeError):
        return None


def _date_in_range(d: str, date_from: Optional[str], date_to: Optional[str]) -> bool:
    dt = _parse_ddmmyyyy(d)
    if dt is None:
        return False
    if date_from:
        df = _parse_ddmmyyyy(date_from)
        if df and dt < df:
            return False
    if date_to:
        dt_to = _parse_ddmmyyyy(date_to)
        if dt_to and dt > dt_to:
            return False
    return True


def short_label(label: str, max_len: int = 60) -> str:
    if not label:
        return ""
    s = str(label).strip()
    if "," in s:
        s = s.split(",", 1)[0].strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip() + "…"
    return s


def _normalize_label(label: str, comment: str) -> str:
    if not label:
        return label
    if "Перепроверка расхождений" not in label:
        return label
    if not comment:
        return label
    c = comment.strip()
    m = re.match(r"Перепроверка\s*:\s*(.+)", c, re.IGNORECASE)
    if m:
        zone = m.group(1).strip()
        if zone and zone.lower() != "перепроверка":
            return f"Перепроверка расхождений ({zone})"
        return "Перепроверка расхождений"
    if c.lower() == "перепроверка":
        return "Перепроверка расхождений"
    return "Перепроверка расхождений"


def _extract_grand_total(email: Dict[str, Any]) -> float:
    if not email:
        return 0.0
    final_totals = email.get("final_totals") or {}
    with_rm = final_totals.get("with_rm") or {}
    amount = with_rm.get("amount")
    typ = (with_rm.get("type") or "").lower()
    if amount is not None:
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = 0.0
        if "недостач" in typ:
            return amount
        if "излиш" in typ:
            return -abs(amount)
        return amount
    totals = email.get("totals") or {}
    cum = totals.get("cumulative_with_rm") or {}
    amount = cum.get("amount")
    typ = (cum.get("type") or "").lower()
    if amount is None:
        return 0.0
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return 0.0
    if "недостач" in typ:
        return amount
    if "излиш" in typ:
        return -abs(amount)
    return amount


# =========================================================
# НОВАЯ ФУНКЦИЯ: сумма без РМ и МЦ
# =========================================================
def _extract_grand_total_no_rm(email: Dict[str, Any]) -> float:
    """Возвращает итоговую сумму БЕЗ учёта РМ и МЦ."""
    if not email:
        return 0.0
    # 1. final_totals.without_rm
    final_totals = email.get("final_totals") or {}
    without_rm = final_totals.get("without_rm") or {}
    amount = without_rm.get("amount")
    typ = (without_rm.get("type") or "").lower()
    if amount is not None:
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = 0.0
        if "недостач" in typ:
            return amount
        if "излиш" in typ:
            return -abs(amount)
        return amount
    # 2. totals.cumulative_without_rm
    totals = email.get("totals") or {}
    cum = totals.get("cumulative_without_rm") or {}
    amount = cum.get("amount")
    typ = (cum.get("type") or "").lower()
    if amount is None:
        return 0.0
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return 0.0
    if "недостач" in typ:
        return amount
    if "излиш" in typ:
        return -abs(amount)
    return amount


def get_filtered_emails(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict[str, Any]]:
    emails = load_emails()
    result = []
    for e in emails:
        if gm_code and e.get("gm_code") != gm_code:
            continue
        if not _date_in_range(e.get("report_date", ""), date_from, date_to):
            continue
        result.append(e)
    result.sort(key=lambda x: x.get("report_date", ""))
    return result


def get_daily_emails(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict[str, Any]]:
    emails = get_filtered_emails(gm_code, date_from, date_to)
    return [e for e in emails if not e.get("is_final")]


def get_final_emails(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict[str, Any]]:
    emails = get_filtered_emails(gm_code, date_from, date_to)
    return [e for e in emails if e.get("is_final")]


def get_last_email(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Optional[Dict[str, Any]]:
    emails = get_filtered_emails(gm_code, date_from, date_to)
    return emails[-1] if emails else None


def get_last_daily_email(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Optional[Dict[str, Any]]:
    emails = get_daily_emails(gm_code, date_from, date_to)
    return emails[-1] if emails else None


def get_last_email_with_events(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Optional[Dict[str, Any]]:
    emails = get_daily_emails(gm_code, date_from, date_to)
    for e in reversed(emails):
        if e.get("events"):
            return e
    return emails[-1] if emails else None


def gm_list() -> List[Dict[str, str]]:
    emails = load_emails()
    seen: Dict[str, str] = {}
    for e in emails:
        code = e.get("gm_code", "")
        name = e.get("gm_name", "")
        if code and code not in seen:
            seen[code] = name
    result = [{"code": code, "name": name, "display": f"{code} — {name}" if name else code} for code, name in seen.items()]
    result.sort(key=lambda x: x["name"].lower())
    return result


def _split_events_from(email: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    if not email:
        return {"zones": {}, "other_events": {}}
    zones: Dict[str, Dict[str, float]] = {}
    others: Dict[str, Dict[str, float]] = {}
    for ev in email.get("events", []):
        amount = ev.get("amount")
        if amount is None:
            continue
        label = ev.get("label", "")
        if not label:
            continue
        label = _normalize_label(label, ev.get("comment", ""))
        zone = extract_zone(label)
        target = zones if zone else others
        key = zone if zone else label
        d = target.setdefault(key, {"deficit": 0.0, "surplus": 0.0})
        if amount >= 0:
            d["deficit"] += float(amount)
        else:
            d["surplus"] += abs(float(amount))
    for d in list(zones.values()) + list(others.values()):
        d["total"] = d["deficit"] - d["surplus"]
    return {"zones": zones, "other_events": others}


def _top_zones_from(zones: Dict[str, Dict[str, float]]) -> List[Tuple[str, float, float, float]]:
    items = []
    for zone in ZONES_CANONICAL:
        d = zones.get(zone, {"deficit": 0.0, "surplus": 0.0, "total": 0.0})
        items.append((zone, d["total"], d["deficit"], d["surplus"]))
    items.sort(key=lambda x: -abs(x[1]))
    return items


def _top_other_from(others: Dict[str, Dict[str, float]], limit: int = 30) -> List[Tuple[str, float]]:
    items = [(k, d["total"]) for k, d in others.items()]
    items.sort(key=lambda x: -abs(x[1]))
    return items[:limit]


def _time_from(email: Optional[Dict[str, Any]]) -> List[Tuple[str, float]]:
    if not email:
        return []
    total: Dict[str, float] = {}
    for t in email.get("time_log", []):
        if t.get("status") != "Да":
            continue
        hours_str = t.get("hours", "")
        if not hours_str:
            continue
        try:
            h, m = hours_str.split(":")
            hours = int(h) + int(m) / 60.0
        except Exception:
            continue
        for person in t.get("people", []):
            if not person:
                continue
            total[person] = total.get(person, 0.0) + hours
    return sorted(total.items(), key=lambda x: -x[1])


def _not_started_from(email: Optional[Dict[str, Any]]) -> List[str]:
    if not email:
        return []
    s = set()
    for ev in email.get("events", []):
        if ev.get("status") == "Не приступали":
            label = ev.get("label", "")
            if label:
                s.add(short_label(label))
    return sorted(s)


def split_events(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Dict[str, Dict[str, float]]]:
    email = get_last_email_with_events(gm_code, date_from, date_to)
    return _split_events_from(email)


def top_zones(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Tuple[str, float, float, float]]:
    split = split_events(gm_code, date_from, date_to)
    return _top_zones_from(split["zones"])


def top_other_events(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, limit: int = 30) -> List[Tuple[str, float]]:
    split = split_events(gm_code, date_from, date_to)
    return _top_other_from(split["other_events"], limit=limit)


def time_total(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Tuple[str, float]]:
    email = get_last_email_with_events(gm_code, date_from, date_to)
    return _time_from(email)


def not_started(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[str]:
    email = get_last_email_with_events(gm_code, date_from, date_to)
    return _not_started_from(email)


def summary_history(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict[str, Any]]:
    emails = get_daily_emails(gm_code, date_from, date_to)
    if not emails:
        return []
    points: List[Dict[str, Any]] = []
    for i, email in enumerate(emails, start=1):
        grand = _extract_grand_total(email)
        points.append({
            "date": email.get("report_date", ""),
            "day_index": i,
            "label": f"{i} сутки",
            "total": grand,
        })
    return points


def summary(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    daily_emails = get_daily_emails(gm_code, date_from, date_to)
    final_emails = get_final_emails(gm_code, date_from, date_to)
    final_email = final_emails[-1] if final_emails else None
    email_with_events = None
    for e in reversed(daily_emails):
        if e.get("events"):
            email_with_events = e
            break
    if email_with_events is None and daily_emails:
        email_with_events = daily_emails[-1]
    split = _split_events_from(email_with_events)
    zones = split["zones"]
    others = split["other_events"]
    ref_email = final_email or email_with_events
    grand_total = _extract_grand_total(ref_email) if ref_email else 0.0
    grand_total_no_rm = _extract_grand_total_no_rm(ref_email) if ref_email else 0.0

    return {
        "emails_count": len(daily_emails),
        "report_date": ref_email.get("report_date", "") if ref_email else "",
        "gm_code": ref_email.get("gm_code", "") if ref_email else "",
        "gm_name": ref_email.get("gm_name", "") if ref_email else "",
        "zones": zones,
        "other_events": others,
        "top_zones": _top_zones_from(zones),
        "top_other_events": _top_other_from(others),
        "time_total": _time_from(email_with_events),
        "not_started": _not_started_from(email_with_events),
        "totals": {
            "grand_total": grand_total,
            "grand_total_no_rm": grand_total_no_rm,  # <-- ДОБАВЛЕНО
        },
    }


def summary_prev(gm_code: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Optional[Dict[str, Any]]:
    emails = get_daily_emails(gm_code, date_from, date_to)
    if len(emails) < 2:
        return None
    prev_email = emails[-2]
    grand_total = _extract_grand_total(prev_email)
    return {
        "report_date": prev_email.get("report_date", ""),
        "gm_code": prev_email.get("gm_code", ""),
        "gm_name": prev_email.get("gm_name", ""),
        "grand_total": grand_total,
    }