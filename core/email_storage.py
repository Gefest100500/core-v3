# core/email_storage.py
"""
Хранилище писем инвентаризации.

- emails.json — список писем
- inventory_archive.json — архив завершённых инвентаризаций

Чистая логика. Без PyQt. Тестируется отдельно.

ИЗМЕНЕНИЯ:
- Добавлена функция save_emails_batch: принимает список распарсенных
  писем, проверяет дубликаты в памяти (без чтения файла на каждом шаге),
  добавляет новые, сортирует и один раз пишет в DataManager.
  Это ускоряет сохранение в разы при большом количестве писем.
- Старая функция save_email сохранена для обратной совместимости.
- Восстановлены старые сигнатуры и возвращаемые поля для тестов:
    * make_key(gm_code, report_date) -> "gm_code_report_date"
    * _find_index(emails, gm_code, report_date) -> int | None
    * save_email -> {"saved", "overwritten", "reason", "gm_code", "key"}
    * add_to_archive -> {"created", "updated", "gm_code"}
    * get_emails_by_date_range(date_from, date_to, gm_code)
"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.data_manager import (
    EMAILS_PATH,
    INVENTORY_ARCHIVE_PATH,
    get_data_manager,
)
from utils.logger import log


# =========================================================
# ВНУТРЕННИЕ УТИЛИТЫ
# =========================================================
def make_key(gm_code: str, report_date: str) -> str:
    """Ключ для дедупликации: (gm_code, report_date).

    Разделитель '_' (как в старой версии) для совместимости с тестами.
    """
    return f"{gm_code}_{report_date}"


def _find_index(
    emails: List[Dict[str, Any]],
    gm_code: str,
    report_date: str,
) -> Optional[int]:
    """Ищет индекс письма по ключу (gm_code, report_date).

    Возвращает индекс или None, если не найдено.
    """
    key = make_key(gm_code, report_date)
    for i, e in enumerate(emails):
        gm = e.get("gm_code", "")
        rd = e.get("report_date", "")
        if make_key(gm, rd) == key:
            return i
    return None


# =========================================================
# ЗАГРУЗКА
# =========================================================
def load_emails() -> List[Dict[str, Any]]:
    """Загружает список писем из emails.json."""
    dm = get_data_manager()
    data = dm.get_emails()
    if not isinstance(data, list):
        log.warning("load_emails: emails.json не список — возвращаю []")
        return []
    return data


def load_archive() -> List[Dict[str, Any]]:
    """Загружает архив завершённых инвентаризаций."""
    dm = get_data_manager()
    data = dm.get_inventory_archive()
    if not isinstance(data, list):
        log.warning("load_archive: inventory_archive.json не список — возвращаю []")
        return []
    return data


# =========================================================
# СОХРАНЕНИЕ (поштучное — старая функция, оставлена для совместимости)
# =========================================================
def save_email(
    parsed: Dict[str, Any],
    raw_subject: str = "",
    raw_body: str = "",
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Сохраняет одно письмо.

    Возвращает:
        {
            "saved": bool,
            "overwritten": bool,
            "reason": "saved"/"duplicate"/"failed"/"no_gm_code_or_report_date",
            "gm_code": str,
            "key": str,
        }
    """
    gm_code = parsed.get("gm_code", "")
    report_date = parsed.get("report_date", "")

    if not gm_code or not report_date:
        log.warning("save_email: нет gm_code или report_date — пропускаю")
        return {
            "saved": False,
            "overwritten": False,
            "reason": "no_gm_code_or_report_date",
            "gm_code": gm_code,
            "key": "",
        }

    key = make_key(gm_code, report_date)

    emails = load_emails()
    idx = _find_index(emails, gm_code, report_date)

    if idx is not None and not overwrite:
        log.info(f"save_email: дубликат — {key}")
        # Для дубликата финального письма всё равно добавляем в архив
        if parsed.get("is_final"):
            add_to_archive(parsed)
        return {
            "saved": False,
            "overwritten": False,
            "reason": "duplicate",
            "gm_code": gm_code,
            "key": key,
        }

    # Добавляем raw-поля
    entry = dict(parsed)
    entry["raw_subject"] = raw_subject
    entry["raw_body"] = raw_body

    overwritten = False

    if idx is not None:
        emails[idx] = entry
        overwritten = True
        log.info(f"save_email: перезаписано — {key}")
    else:
        emails.append(entry)
        log.info(f"save_email: добавлено — {key}")

    # Сортируем по report_date (по убыванию)
    try:
        emails.sort(
            key=lambda x: x.get("report_date", ""),
            reverse=True,
        )
    except Exception:
        pass

    dm = get_data_manager()
    dm.set_emails(emails)

    # Если финальное письмо — добавляем в архив
    if parsed.get("is_final"):
        add_to_archive(parsed)

    return {
        "saved": True,
        "overwritten": overwritten,
        "reason": "saved",
        "gm_code": gm_code,
        "key": key,
    }


# =========================================================
# БАТЧ-СОХРАНЕНИЕ (новая функция — для collect_emails)
# =========================================================
def save_emails_batch(parsed_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Сохраняет список писем одним батчем.

    Это в разы быстрее, чем save_email в цикле.
    """
    stats = {
        "saved": 0,
        "duplicates": 0,
        "failed": 0,
        "details": [],
    }

    if not parsed_list:
        return stats

    emails = load_emails()

    # Строим set существующих ключей
    existing_keys = set()
    for e in emails:
        gm = e.get("gm_code", "")
        rd = e.get("report_date", "")
        if gm and rd:
            existing_keys.add(make_key(gm, rd))

    new_entries = []
    for parsed in parsed_list:
        gm_code = parsed.get("gm_code", "")
        report_date = parsed.get("report_date", "")
        subject = parsed.get("_raw_subject", parsed.get("subject", ""))

        if not gm_code or not report_date:
            stats["failed"] += 1
            stats["details"].append({
                "subject": subject,
                "gm_code": gm_code,
                "status": "failed",
                "error": "нет gm_code или report_date",
            })
            continue

        key = make_key(gm_code, report_date)

        if key in existing_keys:
            stats["duplicates"] += 1
            stats["details"].append({
                "subject": subject,
                "gm_code": gm_code,
                "report_date": report_date,
                "status": "duplicate",
            })
            # Дубликат финального — всё равно в архив
            if parsed.get("is_final"):
                add_to_archive(parsed)
            continue

        existing_keys.add(key)

        entry = dict(parsed)
        entry.pop("_raw_subject", None)
        entry.pop("_raw_body", None)
        new_entries.append(entry)

        stats["saved"] += 1
        stats["details"].append({
            "subject": subject,
            "gm_code": gm_code,
            "report_date": report_date,
            "status": "saved",
        })

    if new_entries:
        emails.extend(new_entries)

        try:
            emails.sort(
                key=lambda x: x.get("report_date", ""),
                reverse=True,
            )
        except Exception:
            pass

        dm = get_data_manager()
        dm.set_emails(emails)

        for entry in new_entries:
            if entry.get("is_final"):
                try:
                    add_to_archive(entry)
                except Exception as e:
                    log.warning(f"save_emails_batch: ошибка архивации: {e}")

    log.info(
        f"save_emails_batch: saved={stats['saved']}, "
        f"duplicates={stats['duplicates']}, failed={stats['failed']}"
    )

    return stats


# =========================================================
# АРХИВ
# =========================================================
def add_to_archive(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Добавляет финальное письмо в архив.

    Возвращает:
        {
            "created": bool,   # True, если создана новая запись
            "updated": bool,   # True, если обновлена существующая
            "gm_code": str,    # код ГМ (может быть "")
        }
    """
    dm = get_data_manager()
    archive = dm.get_inventory_archive() or []

    gm_code = parsed.get("gm_code", "")
    if not gm_code:
        return {"created": False, "updated": False, "gm_code": ""}

    idx = -1
    for i, a in enumerate(archive):
        if a.get("gm_code") == gm_code:
            idx = i
            break

    entry = {
        "gm_code": gm_code,
        "gm_name": parsed.get("gm_name", ""),
        "gm_address": parsed.get("gm_address", ""),
        "variant": parsed.get("variant", ""),
        "start_date": parsed.get("start_date", ""),
        "end_date": parsed.get("end_date", ""),
        "final_totals": parsed.get("final_totals", {}),
        "report_date": parsed.get("report_date", ""),
    }

    created = False
    updated = False

    if idx >= 0:
        archive[idx] = entry
        updated = True
        log.info(f"add_to_archive: обновлено — {gm_code}")
    else:
        archive.append(entry)
        created = True
        log.info(f"add_to_archive: добавлено — {gm_code}")

    dm.set_inventory_archive(archive)

    return {
        "created": created,
        "updated": updated,
        "gm_code": gm_code,
    }


# =========================================================
# ПОИСК
# =========================================================
def get_email(gm_code: str, report_date: str) -> Optional[Dict[str, Any]]:
    """Возвращает письмо по ключу или None."""
    emails = load_emails()
    idx = _find_index(emails, gm_code, report_date)
    return emails[idx] if idx is not None else None


def get_emails_by_gm(gm_code: str) -> List[Dict[str, Any]]:
    """Возвращает все письма для указанного ГМ."""
    emails = load_emails()
    return [e for e in emails if e.get("gm_code") == gm_code]


def get_emails_by_date_range(
    date_from: str = "",
    date_to: str = "",
    gm_code: str = "",
) -> List[Dict[str, Any]]:
    """Возвращает письма в диапазоне дат (и опционально по ГМ)."""
    emails = load_emails()
    result = []
    for e in emails:
        rd = e.get("report_date", "")
        if date_from and rd < date_from:
            continue
        if date_to and rd > date_to:
            continue
        if gm_code and e.get("gm_code") != gm_code:
            continue
        result.append(e)
    return result


# =========================================================
# СТАТИСТИКА
# =========================================================
def count_emails() -> int:
    """Возвращает количество писем."""
    return len(load_emails())


def get_unique_gm_codes() -> List[str]:
    """Возвращает список уникальных кодов ГМ."""
    emails = load_emails()
    codes = set()
    for e in emails:
        gm = e.get("gm_code", "")
        if gm:
            codes.add(gm)
    return sorted(codes)


def clear_all():
    """Очищает все письма."""
    dm = get_data_manager()
    dm.set_emails([])
    log.info("clear_all: emails.json очищен")