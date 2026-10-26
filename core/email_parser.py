# core/email_parser.py
"""
Парсер тела письма от Krs_gk_gm_otchet@magnit.ru.

Чистая логика. Без PyQt. Без win32com. Тестируется отдельно.

Вход:  plain-text тело письма (строка).
Выход: словарь с полями:
    report_date, gm_code, gm_name, format,
    start_date, end_date, duration_days, variant,
    author, author_date, executors,
    totals, final_totals, is_final,
    preparation, events, time_log, comments,
    parse_warnings

ФИНАЛЬНОЕ ПИСЬМО:
- Содержит строки «Сумма полной инвентаризации c РМ и МЦ» и
  «Сумма полной инвентаризации без учета РМ и МЦ».
- Если они есть — is_final = True.
- Суммы — в final_totals.
- report_date = end_date (дата окончания инвентаризации), чтобы
  финальное письмо не перекрывалось с ежедневным по ключу.

ИЗМЕНЕНИЯ:
- Парсинг дат начала/окончания инвентаризации.
- Флаг is_final и final_totals.
- _parse_comments не ищет маркер «Дополнительный комментарий» — он уже отрезан.
- Поддержка двух форматов шапки ГМ:
  1. «инвентаризации ГМ Самара 3 Кирова (996313, формат «L+»)» — ежедневный отчёт.
  2. «Гипермаркет (ГМ): Самара 3 Кирова (996313).» + «Формат ГМ: L+» — финальный отчёт.
- Для финального письма report_date берётся из end_date.
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


# =========================================================
# КОНСТАНТЫ
# =========================================================
SECTION_PREPARATION = "Подготовка к инвентаризации"
SECTION_EVENTS = "Проведение инвентаризации"
SECTION_TIME = "Учет рабочего времени"
SECTION_COMMENTS = "Дополнительный комментарий"

NOT_STARTED = "Не приступали"
YES_MARK = "Да"
NO_MARK = "Нет"


# =========================================================
# РЕГУЛЯРКИ
# =========================================================

# Формат 1 — ежедневный отчёт:
# «...инвентаризации ГМ Самара 3 Кирова (996313, формат «L+»)»
RE_GM_HEADER = re.compile(
    r"инвентаризации\s+ГМ\s+(?P<name>.+?)\s*\((?P<code>\d{6}),\s*"
    r"формат\s*[«\"]?(?P<format>[^)\"»]+)[»\"]?\s*\)",
    re.IGNORECASE,
)

# Формат 2 — финальный отчёт:
# «Гипермаркет (ГМ): Самара 3 Кирова (996313).»
RE_GM_HEADER_FINAL = re.compile(
    r"Гипермаркет\s*\(ГМ\)\s*:\s*(?P<name>.+?)\s*\((?P<code>\d{6})\)",
    re.IGNORECASE,
)

# Формат ГМ отдельной строкой в финальном письме:
# «Формат ГМ: L+»
RE_FORMAT_FINAL = re.compile(
    r"Формат\s+ГМ\s*:\s*(?P<format>\S+)",
    re.IGNORECASE,
)

RE_DAILY_TOTAL = re.compile(
    r"Итого\s+за\s+день\s*\((?P<date>[\d\.]+)\)\s*:\s*"
    r"(?P<amount>-?[\d\s\xa0]+(?:[\.,]\d+)?)\s*руб\.?\s*"
    r"(?P<type>недостач[а-я]*|излишк[а-я]*)",
    re.IGNORECASE,
)

RE_CUMULATIVE = re.compile(
    r"Итого\s+накопительно\s+(?P<kind>с\s+РМ\s+и\s+МЦ|без\s+учета\s+РМ\s+и\s+МЦ)\s*:\s*"
    r"(?P<amount>-?[\d\s\xa0]+(?:[\.,]\d+)?)\s*руб\.?\s*"
    r"(?P<type>недостач[а-я]*|излишк[а-я]*)",
    re.IGNORECASE,
)

# ФИНАЛЬНЫЕ СТРОКИ:
# «Сумма полной инвентаризации c РМ и МЦ: 4 335 740,53 руб. недостачей,»
# «Сумма полной инвентаризации без учета РМ и МЦ: 4 387 282,54 руб. недостачей»
RE_FULL_WITH_RM = re.compile(
    r"Сумма\s+полной\s+инвентаризации\s+[cс]\s+РМ\s+и\s+МЦ\s*:\s*"
    r"(?P<amount>-?[\d\s\xa0]+(?:[\.,]\d+)?)\s*руб\.?\s*"
    r"(?P<type>недостач[а-я]*|излишк[а-я]*)",
    re.IGNORECASE,
)

RE_FULL_WITHOUT_RM = re.compile(
    r"Сумма\s+полной\s+инвентаризации\s+без\s+уч[её]та\s+РМ\s+и\s+МЦ\s*:\s*"
    r"(?P<amount>-?[\d\s\xa0]+(?:[\.,]\d+)?)\s*руб\.?\s*"
    r"(?P<type>недостач[а-я]*|излишк[а-я]*)",
    re.IGNORECASE,
)

# Даты инвентаризации из шапки
RE_DATE_START = re.compile(
    r"Дата\s+начала\s+инвентаризации\s+ГМ\s*:\s*(?P<date>\d{2}\.\d{2}\.\d{4})",
    re.IGNORECASE,
)

RE_DATE_END = re.compile(
    r"Дата\s+окончания\s+инвентаризации\s+ГМ\s*:\s*(?P<date>\d{2}\.\d{2}\.\d{4})",
    re.IGNORECASE,
)

# Длительность и вариант
RE_DURATION_VARIANT = re.compile(
    r"Длительность\s+интенсивного\s+пересчета\s+товара\s*:\s*"
    r"(?P<days>\d+)\s+сут[а-я]*\s*\(Вариант\s+(?P<variant>[А-ЯЁA-Z])\)",
    re.IGNORECASE,
)

RE_EXECUTOR = re.compile(
    r"^\s*(?P<name>[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)"
    r"\s*\|\s*(?P<city>[^\(]+)\((?P<role>[^)]+)\)"
    r"\s*(?P<phone>[\+\d\s]*)",
)

RE_AUTHOR = re.compile(
    r"Отчет\s+отправил\S*"
    r"\s+(?P<name>[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)"
    r"\s+(?P<date>\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})",
)

RE_EVENT = re.compile(
    r"^\s*[-–—]\s*(?P<label>.+?)"
    r"\s*[:\-]\s*"
    r"(?P<status>Да|Нет|Не приступали|—)"
    r"(?:\s*,\s*(?P<date>\d{2}\.\d{2}\.\d{4}))?"
    r"(?:\s*,\s*(?P<amount>-?[\d\s\xa0]+(?:[\.,]\d+)?)\s*руб\s*"
    r"(?P<type>недостач[а-я]*|излишк[а-я]*))?"
    r"(?:\s*\(Комментарий:\s*(?P<comment>[^)]+)\))?"
    r"\s*$",
    re.IGNORECASE,
)

RE_TIME_LOG = re.compile(
    r"^\s*[-–—]\s*(?P<label>\d+\s+сутки,\s*[а-яё]+\.?\s*"
    r"(?:день|ночь)\s*\([^)]+\)|Первый\s+день.*|Первая\s+ночь.*|"
    r"Второй\s+день.*|Вторая\s+ночь.*|Третий\s+день.*|Третья\s+ночь.*|"
    r"Четвертый\s+день.*|Четвертая\s+ночь.*|Пятый\s+день.*|Пятая\s+ночь.*)"
    r"\s*[:\-]\s*"
    r"(?P<status>Да|Нет|Не приступали)"
    r"(?:\s*,\s*(?P<date_from>\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})"
    r"\s*-\s*(?P<date_to>\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}))?"
    r"(?:\s*,\s*\((?P<hours>[\d:]+)\))?"
    r"(?:\s*,\s*(?P<people>.+?))?"
    r"\s*$",
    re.IGNORECASE,
)

# Дата в конце строки
RE_DATE_AT_END = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s*$")


# =========================================================
# ПАРСИНГ ЧИСЛА
# =========================================================
def _parse_amount(raw: str) -> Optional[float]:
    """Парсит '132 583' или '-3 397' или '-271 060' -> float."""
    if not raw:
        return None

    s = raw.replace("\xa0", "").replace(" ", "").strip()
    s = s.replace(",", ".")

    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# =========================================================
# ПАРСИНГ ШАПКИ
# =========================================================
def _parse_executors(lines: List[str]) -> List[Dict[str, str]]:
    """Ищет исполнителей в шапке письма."""
    result = []
    for line in lines[:80]:
        line = line.strip()
        if not line or "|" not in line:
            continue

        m = RE_EXECUTOR.match(line)
        if not m:
            continue

        result.append({
            "name": m.group("name").strip(),
            "city": m.group("city").strip(),
            "role": m.group("role").strip(),
            "phone": (m.group("phone") or "").strip(),
        })

    return result


def _parse_gm_header(text: str) -> Dict[str, str]:
    """Ищет строку с ГМ. Поддерживает два формата писем:

    1. Ежедневный отчёт:
       «...инвентаризации ГМ Самара 3 Кирова (996313, формат «L+»)»

    2. Финальный отчёт:
       «Гипермаркет (ГМ): Самара 3 Кирова (996313).»
       плюс отдельная строка «Формат ГМ: L+»
    """
    # Формат 1 — ежедневный
    m = RE_GM_HEADER.search(text)
    if m:
        return {
            "gm_name": m.group("name").strip(),
            "gm_code": m.group("code").strip(),
            "format": m.group("format").strip(),
        }

    # Формат 2 — финальный
    m = RE_GM_HEADER_FINAL.search(text)
    if m:
        result = {
            "gm_name": m.group("name").strip(),
            "gm_code": m.group("code").strip(),
            "format": "",
        }
        mf = RE_FORMAT_FINAL.search(text)
        if mf:
            result["format"] = mf.group("format").strip()
        return result

    return {}


def _parse_dates(text: str) -> Dict[str, str]:
    """Парсит даты начала/окончания инвентаризации из шапки письма."""
    result = {"start_date": "", "end_date": ""}

    m = RE_DATE_START.search(text)
    if m:
        result["start_date"] = m.group("date").strip()

    m = RE_DATE_END.search(text)
    if m:
        result["end_date"] = m.group("date").strip()

    return result


def _parse_duration_variant(text: str) -> Dict[str, Any]:
    """Парсит 'Длительность интенсивного пересчета товара: 4 суток (Вариант Е)'."""
    result = {"duration_days": None, "variant": ""}

    m = RE_DURATION_VARIANT.search(text)
    if m:
        try:
            result["duration_days"] = int(m.group("days"))
        except (ValueError, TypeError):
            pass
        result["variant"] = m.group("variant").strip().upper()

    return result


def _parse_author(text: str) -> Dict[str, str]:
    """Ищет 'Отчет отправил(a) ФИО дата'."""
    m = RE_AUTHOR.search(text)
    if not m:
        return {}
    return {
        "author": m.group("name").strip(),
        "author_date": m.group("date").strip(),
    }


# =========================================================
# ПАРСИНГ ИТОГОВ
# =========================================================
def _parse_totals(text: str) -> Dict[str, Any]:
    """Парсит блок 'Промежуточные итоги' + финальные суммы."""
    result: Dict[str, Any] = {
        "daily": [],
        "cumulative_with_rm": None,
        "cumulative_without_rm": None,
    }

    for m in RE_DAILY_TOTAL.finditer(text):
        amount = _parse_amount(m.group("amount"))
        if amount is None:
            continue
        result["daily"].append({
            "date": m.group("date").strip(),
            "amount": amount,
            "type": m.group("type").strip().lower(),
        })

    for m in RE_CUMULATIVE.finditer(text):
        kind = m.group("kind").strip().lower()
        amount = _parse_amount(m.group("amount"))
        if amount is None:
            continue

        entry = {
            "amount": amount,
            "type": m.group("type").strip().lower(),
        }

        if "без" in kind:
            result["cumulative_without_rm"] = entry
        else:
            result["cumulative_with_rm"] = entry

    return result


def _parse_final_totals(text: str) -> Dict[str, Any]:
    """Парсит финальные строки:
        «Сумма полной инвентаризации c РМ и МЦ: ...»
        «Сумма полной инвентаризации без учета РМ и МЦ: ...»

    Returns:
        {
            "with_rm": {"amount": float, "type": str} or None,
            "without_rm": {"amount": float, "type": str} or None,
        }
    """
    result: Dict[str, Any] = {
        "with_rm": None,
        "without_rm": None,
    }

    m = RE_FULL_WITH_RM.search(text)
    if m:
        amount = _parse_amount(m.group("amount"))
        if amount is not None:
            result["with_rm"] = {
                "amount": amount,
                "type": m.group("type").strip().lower(),
            }

    m = RE_FULL_WITHOUT_RM.search(text)
    if m:
        amount = _parse_amount(m.group("amount"))
        if amount is not None:
            result["without_rm"] = {
                "amount": amount,
                "type": m.group("type").strip().lower(),
            }

    return result


# =========================================================
# ПАРСИНГ СОБЫТИЙ
# =========================================================
def _parse_events_block(lines: List[str]) -> List[Dict[str, Any]]:
    """Парсит блок событий: '-Название: Да , дата, сумма'."""
    events = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        m = RE_EVENT.match(line)
        if not m:
            m2 = re.match(
                r"^\s*[-–—]\s*(?P<label>.+?)\s*[-–—]\s*"
                r"(?P<status>Да|Нет|Не приступали)\s*$",
                line,
                re.IGNORECASE,
            )
            if m2:
                events.append({
                    "label": m2.group("label").strip(),
                    "status": m2.group("status").strip(),
                    "date": "",
                    "amount": None,
                    "type": "",
                    "comment": "",
                })
            continue

        status = m.group("status").strip()
        date_str = (m.group("date") or "").strip()
        amount_raw = m.group("amount") or ""
        amount = _parse_amount(amount_raw)
        type_str = (m.group("type") or "").strip().lower()
        comment = (m.group("comment") or "").strip()

        events.append({
            "label": m.group("label").strip(),
            "status": status,
            "date": date_str,
            "amount": amount,
            "type": type_str,
            "comment": comment,
        })

    return events


# =========================================================
# ПАРСИНГ УЧЁТА ВРЕМЕНИ
# =========================================================
def _parse_time_log(lines: List[str]) -> List[Dict[str, Any]]:
    """Парсит блок учёта рабочего времени."""
    result = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        m = RE_TIME_LOG.match(line)
        if not m:
            continue

        status = m.group("status").strip()
        date_from = (m.group("date_from") or "").strip()
        date_to = (m.group("date_to") or "").strip()
        hours = (m.group("hours") or "").strip()
        people_raw = (m.group("people") or "").strip()

        people = [p.strip() for p in people_raw.split(",") if p.strip()]

        result.append({
            "label": m.group("label").strip(),
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
            "hours": hours,
            "people": people,
        })

    return result


# =========================================================
# ПАРСИНГ КОММЕНТАРИЕВ
# =========================================================
def _parse_comments(lines: List[str]) -> List[Dict[str, str]]:
    """Парсит строки блока 'Дополнительный комментарий'.

    ВАЖНО: маркер "Дополнительный комментарий" УЖЕ ОТРЕЗАН
    в parse_email_body. Здесь приходят только строки ПОСЛЕ маркера.

    Логика:
      - Пропускаем пустые.
      - Останавливаемся на одиночном дефисе или "С уважением".
      - Пропускаем заголовок "КомментарийДата".
      - Строки, заканчивающиеся на дату 04.10.2026 — это комментарий.
    """
    result = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        # Конец блока — одиночный дефис
        if line == "-" or (line.startswith("-") and len(line) <= 3):
            break

        # Конец блока — подпись
        if "С уважением" in line:
            break

        # Пропускаем заголовок "КомментарийДата"
        if re.match(r"^Комментарий\s*Дата\s*$", line, re.IGNORECASE):
            continue

        # Ищем дату в конце
        m = RE_DATE_AT_END.search(line)
        if not m:
            continue

        date_str = m.group(1)
        text = line[:m.start()].strip()
        text = text.rstrip("\t ").strip()

        if not text:
            continue

        result.append({
            "text": text,
            "date": date_str,
        })

    return result


# =========================================================
# ОСНОВНАЯ ФУНКЦИЯ
# =========================================================
def parse_email_body(body: str, subject: str = "") -> Dict[str, Any]:
    """Парсит тело письма от Krs_gk_gm_otchet@magnit.ru."""
    warnings: List[str] = []

    if not body:
        return {
            "report_date": "",
            "gm_code": "",
            "gm_name": "",
            "format": "",
            "start_date": "",
            "end_date": "",
            "duration_days": None,
            "variant": "",
            "author": "",
            "author_date": "",
            "executors": [],
            "totals": {
                "daily": [],
                "cumulative_with_rm": None,
                "cumulative_without_rm": None,
            },
            "final_totals": {"with_rm": None, "without_rm": None},
            "is_final": False,
            "preparation": [],
            "events": [],
            "time_log": [],
            "comments": [],
            "parse_warnings": ["Тело письма пустое"],
        }

    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = body.lstrip("\ufeff")
    lines = body.split("\n")

    # --- ГМ ---
    gm_info = _parse_gm_header(body)
    gm_code = gm_info.get("gm_code", "")
    gm_name = gm_info.get("gm_name", "")
    gm_format = gm_info.get("format", "")

    if not gm_code:
        m = re.search(
            r"ГМ\s+(?P<name>.+?)\s*[—\-]\s*(?P<date>\d{2}\.\d{2}\.\d{4})",
            subject,
        )
        if m:
            gm_name = m.group("name").strip()
            warnings.append("gm_code не найден в теле — только в теме")

    # --- Финальные суммы и даты (нужны для report_date) ---
    final_totals = _parse_final_totals(body)
    is_final = (
        final_totals["with_rm"] is not None
        or final_totals["without_rm"] is not None
    )

    dates = _parse_dates(body)

    # --- Дата отчёта ---
    # Ежедневные письма: дата из темы (или последняя дневная в totals).
    # Финальные письма: дата окончания инвентаризации (end_date),
    # чтобы не пересечься по ключу с ежедневным письмом первого дня.
    report_date = ""

    if is_final and dates["end_date"]:
        report_date = dates["end_date"]
    else:
        m = re.search(r"(\d{2}\.\d{2}\.\d{4})", subject)
        if m:
            report_date = m.group(1)
        else:
            daily = _parse_totals(body).get("daily", [])
            if daily:
                report_date = daily[-1]["date"]
            else:
                warnings.append("report_date не найден")

    # --- Даты инвентаризации ---
    if not dates["start_date"]:
        warnings.append("start_date не найден")
    if not dates["end_date"]:
        warnings.append("end_date не найден")

    # --- Длительность и вариант ---
    dur_var = _parse_duration_variant(body)

    # --- Автор ---
    author_info = _parse_author(body)
    author = author_info.get("author", "")
    author_date = author_info.get("author_date", "")

    # --- Исполнители ---
    executors = _parse_executors(lines)
    if not executors:
        warnings.append("executors не найдены")

    # --- Итоги ---
    totals = _parse_totals(body)
    if not totals["daily"]:
        warnings.append("totals.daily пуст")

    if is_final:
        warnings.append("обнаружено финальное письмо (is_final=True)")

    # --- Разбиваем на секции ---
    prep_lines: List[str] = []
    event_lines: List[str] = []
    time_lines: List[str] = []
    comment_lines: List[str] = []

    current_section = None
    for line in lines:
        stripped = line.strip()

        if SECTION_PREPARATION in stripped:
            current_section = "prep"
            continue
        if SECTION_EVENTS in stripped:
            current_section = "events"
            continue
        if SECTION_TIME in stripped:
            current_section = "time"
            continue
        if SECTION_COMMENTS in stripped:
            current_section = "comments"
            continue

        if current_section == "prep":
            prep_lines.append(line)
        elif current_section == "events":
            event_lines.append(line)
        elif current_section == "time":
            time_lines.append(line)
        elif current_section == "comments":
            comment_lines.append(line)

    preparation = _parse_events_block(prep_lines)
    events = _parse_events_block(event_lines)
    time_log = _parse_time_log(time_lines)
    comments = _parse_comments(comment_lines)

    if not preparation:
        warnings.append("preparation пуст")
    if not events:
        warnings.append("events пуст")
    if not time_log:
        warnings.append("time_log пуст")
    if not comments:
        warnings.append("comments пуст")

    return {
        "report_date": report_date,
        "gm_code": gm_code,
        "gm_name": gm_name,
        "format": gm_format,
        "start_date": dates["start_date"],
        "end_date": dates["end_date"],
        "duration_days": dur_var["duration_days"],
        "variant": dur_var["variant"],
        "author": author,
        "author_date": author_date,
        "executors": executors,
        "totals": totals,
        "final_totals": final_totals,
        "is_final": is_final,
        "preparation": preparation,
        "events": events,
        "time_log": time_log,
        "comments": comments,
        "parse_warnings": warnings,
    }


# =========================================================
# ВСПОМОГАТЕЛЬНОЕ — ИТОГ ПО ВСЕМ ДНЯМ
# =========================================================
def summarize_emails(parsed_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Строит сводку по списку распарсенных писем (одного ГМ)."""
    if not parsed_list:
        return {
            "gm_code": "", "gm_name": "",
            "daily": [], "cumulative_last": None,
            "top_events": [], "not_started": [], "time_total": {},
        }

    gm_code = parsed_list[0].get("gm_code", "")
    gm_name = parsed_list[0].get("gm_name", "")

    daily_map: Dict[str, Dict[str, Any]] = {}
    for p in parsed_list:
        for d in p.get("totals", {}).get("daily", []):
            daily_map[d["date"]] = d
    daily = sorted(daily_map.values(), key=lambda x: x["date"])

    cumulative_last = None
    for p in parsed_list:
        cum = p.get("totals", {}).get("cumulative_with_rm")
        if cum:
            cumulative_last = cum

    event_sums: Dict[str, float] = {}
    for p in parsed_list:
        for e in p.get("events", []):
            if e.get("amount") is None:
                continue
            label = e["label"]
            event_sums[label] = event_sums.get(label, 0.0) + abs(e["amount"])
    top_events = sorted(event_sums.items(), key=lambda x: -x[1])[:15]

    not_started_set = set()
    for p in parsed_list:
        for e in p.get("events", []):
            if e.get("status") == NOT_STARTED:
                not_started_set.add(e["label"])
    not_started = sorted(not_started_set)

    time_total: Dict[str, float] = {}
    for p in parsed_list:
        for t in p.get("time_log", []):
            if t.get("status") != YES_MARK:
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
                time_total[person] = time_total.get(person, 0.0) + hours

    return {
        "gm_code": gm_code,
        "gm_name": gm_name,
        "daily": daily,
        "cumulative_last": cumulative_last,
        "top_events": top_events,
        "not_started": not_started,
        "time_total": time_total,
    }