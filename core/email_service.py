# core/email_service.py
"""
Сервис сбора писем из Outlook.

Оркестрирует: Outlook → парсер → хранилище.

Чистая логика. Без PyQt. Тестируется отдельно.
Возвращает статистику: сколько найдено, сколько новых, сколько дубликатов.

ИЗМЕНЕНИЯ:
- Новый модуль. Сервис для сбора писем.
- ФИКС производительности: вместо поштучного save_email
  (каждый вызов перезаписывал emails.json целиком)
  теперь используется батчинг через save_emails_batch.
  Это ускоряет сохранение в разы при большом количестве писем.
- Сигнатура collect_emails и формат возвращаемого словаря
  сохранены для обратной совместимости с app.py и dashboard_frame.py.
"""
from typing import Any, Callable, Dict, List, Optional

from core.email_parser import parse_email_body
from core.email_storage import save_emails_batch, load_emails, load_archive
from core.outlook_connector import fetch_emails, is_outlook_available
from utils.logger import log


# =========================================================
# СБОР
# =========================================================
def collect_emails(
    days_back: int = 30,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Собирает письма из Outlook, парсит, сохраняет.

    Args:
        days_back:         за сколько дней забирать.
        progress_callback: функция (message: str) — для прогресса.

    Returns:
        {
            "success": bool,
            "error": str,             # если success=False
            "fetched": int,           # сколько писем получено из Outlook
            "parsed": int,            # сколько успешно распарсено
            "saved": int,             # сколько новых сохранено
            "duplicates": int,        # сколько пропущено (уже есть)
            "failed": int,            # сколько не удалось распарсить
            "details": [              # по каждому письму
                {"subject": "...", "gm_code": "...", "status": "saved"/"duplicate"/"failed"},
                ...
            ],
        }
    """
    def report(msg: str):
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    result: Dict[str, Any] = {
        "success": False,
        "error": "",
        "fetched": 0,
        "parsed": 0,
        "saved": 0,
        "duplicates": 0,
        "failed": 0,
        "details": [],
    }

    if not is_outlook_available():
        result["error"] = "Outlook недоступен (win32com не установлен)"
        log.warning(f"collect_emails: {result['error']}")
        return result

    report("Поиск писем в Outlook...")
    try:
        emails = fetch_emails(days_back=days_back)
    except Exception as e:
        result["error"] = f"Ошибка поиска писем: {e}"
        log.exception("collect_emails: ошибка fetch_emails")
        return result

    result["fetched"] = len(emails)
    log.info(f"collect_emails: получено из Outlook — {len(emails)}")

    if not emails:
        result["success"] = True
        report("Писем не найдено")
        return result

    report(f"Обработка {len(emails)} писем...")

    # --- Батчинг: собираем все распарсенные письма в список ---
    parsed_list: List[Dict[str, Any]] = []
    failed_list: List[Dict[str, Any]] = []

    for i, email in enumerate(emails, 1):
        subject = email.get("subject", "")
        body = email.get("body", "")

        # --- Парсинг ---
        try:
            parsed = parse_email_body(body, subject)
        except Exception as e:
            result["failed"] += 1
            failed_list.append({
                "subject": subject,
                "gm_code": "",
                "status": "failed",
                "error": str(e),
            })
            log.exception(f"collect_emails: ошибка парсинга «{subject[:60]}»")
            continue

        result["parsed"] += 1

        # --- Сохраняем в памяти, добавим позже ---
        parsed["_raw_subject"] = subject
        parsed["_raw_body"] = body
        parsed_list.append(parsed)

        report(f"Обработано {i} из {len(emails)}")

    # --- Батч-сохранение ---
    report(f"Сохранение {len(parsed_list)} писем...")
    try:
        save_stats = save_emails_batch(parsed_list)
    except Exception as e:
        log.exception("collect_emails: ошибка батч-сохранения")
        result["error"] = f"Ошибка сохранения: {e}"
        return result

    result["saved"] = save_stats.get("saved", 0)
    result["duplicates"] = save_stats.get("duplicates", 0)
    result["failed"] += save_stats.get("failed", 0)

    # --- Формируем details ---
    result["details"] = failed_list + save_stats.get("details", [])

    result["success"] = True

    log.info(
        f"collect_emails: итог — fetched={result['fetched']}, "
        f"parsed={result['parsed']}, saved={result['saved']}, "
        f"duplicates={result['duplicates']}, failed={result['failed']}"
    )

    return result


# =========================================================
# СТАТИСТИКА
# =========================================================
def storage_stats() -> Dict[str, Any]:
    """Возвращает статистику по хранилищу."""
    from core.email_analytics import gm_list

    emails = load_emails()
    return {
        "total": len(emails),
        "gms": gm_list(),
    }