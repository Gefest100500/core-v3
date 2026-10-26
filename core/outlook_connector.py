# core/outlook_connector.py
"""
Забирает письма из Outlook через win32com.

Чистая логика. Без PyQt. Тестируется отдельно (если Outlook есть).

Поиск идёт ВСЕГДА по ВСЕМУ ЯЩИКУ: обходятся все корневые папки
(namespace.Folders), включая Inbox, «KRS GM», «Архив», «Отправленные»,
отдельные .pst и всё, что подключено к Outlook. Рекурсивно, до max_depth.
Имена папок не настраиваются — это исключает ошибку пользователя.

Фильтры:
    - Отправитель: Krs_gk_gm_otchet@magnit.ru
    - Тема: содержит "Отчет о ходе проведения полной инвентаризации"
      или "Отчет о завершении полной инвентаризации"
    - Дата получения: за последние N дней (days_back=None — весь ящик)

ИЗМЕНЕНИЯ:
- days_back=None — не фильтруем по дату, забираем весь ящик.
- Поиск по SMTP через PropertyAccessor (работает для Exchange DN).
- Поле folder — имя папки, откуда взято письмо.
- subject_filters — список подстрок темы (ход + завершение).
- ФИКС COM: CoInitialize может вернуть S_FALSE (уже инициализирован).
  В этом случае CoUninitialize вызывать НЕЛЬЗЯ.
- УПРОЩЕНИЕ: убран параметр folder_names и _get_config_folders.
- РАСШИРЕНИЕ: обход теперь идёт по ВСЕМ корневым папкам
  (namespace.Folders), а не только по Inbox. Это нужно, потому что
  письма могут лежать в пользовательских папках («KRS GM» и т.п.),
  в «Архиве», в отдельных .pst — у разных пользователей по-разному.
- Логирование: на уровне debug пишем, какие папки обошли и сколько
  писем в каждой; на уровне info — итог.
"""
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.logger import log


OUTLOOK_AVAILABLE = False
try:
    import win32com.client  # noqa: F401
    OUTLOOK_AVAILABLE = True
except ImportError:
    log.info("outlook_connector: win32com не установлен — интеграция отключена")


SENDER_FILTER = "Krs_gk_gm_otchet@magnit.ru"
SUBJECT_FILTERS = [
    "Отчет о ходе проведения полной инвентаризации",
    "Отчет о завершении полной инвентаризации",
]
DEFAULT_DAYS_BACK = 30

OL_MAIL = 43
OL_FOLDER_INBOX = 6
PR_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptags/0x39FE001E"

# Максимальная глубина рекурсии по папкам.
# 10 — с запасом: у большинства пользователей структура не глубже 3–4.
MAX_FOLDER_DEPTH = 10


# =========================================================
# УТИЛИТЫ
# =========================================================
def _get_smtp_address(item) -> str:
    """SMTP-адрес отправителя через PropertyAccessor."""
    try:
        smtp = item.PropertyAccessor.GetProperty(PR_SMTP_ADDRESS)
        if smtp:
            return str(smtp)
    except Exception:
        pass

    try:
        addr = str(item.SenderEmailAddress or "")
        if "@" in addr:
            return addr
    except Exception:
        pass

    return ""


def _get_sender_variants(item) -> List[str]:
    """Все варианты отправителя."""
    variants = []
    try:
        if item.SenderEmailAddress:
            variants.append(str(item.SenderEmailAddress))
    except Exception:
        pass
    try:
        if item.SenderName:
            variants.append(str(item.SenderName))
    except Exception:
        pass
    smtp = _get_smtp_address(item)
    if smtp:
        variants.append(smtp)
    return variants


def _walk_folders(folder, depth=0, max_depth=MAX_FOLDER_DEPTH):
    """Рекурсивный обход папок.

    Обходит folder и все её подпапки до max_depth.
    Ошибки доступа к подпапкам не роняют обход — просто пропускаются.
    """
    if depth > max_depth:
        return
    yield folder
    try:
        subfolders = folder.Folders
    except Exception:
        return
    try:
        count = int(subfolders.Count)
    except Exception:
        return
    for i in range(1, count + 1):
        try:
            sub = subfolders.Item(i)
        except Exception:
            continue
        yield from _walk_folders(sub, depth + 1, max_depth)


def _iter_root_folders(namespace):
    """Итерирует все корневые папки ящика (включая Inbox, KRS GM, Архив, .pst)."""
    try:
        roots = namespace.Folders
    except Exception as e:
        log.error(f"fetch_emails: не удалось получить корневые папки: {e}")
        return
    try:
        count = int(roots.Count)
    except Exception:
        count = 0
    for i in range(1, count + 1):
        try:
            yield roots.Item(i)
        except Exception as e:
            log.debug(f"fetch_emails: не удалось открыть корневую папку #{i}: {e}")


# =========================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =========================================================
def fetch_emails(
    days_back: Optional[int] = DEFAULT_DAYS_BACK,
    sender_filter: str = SENDER_FILTER,
    subject_filters: Optional[List[str]] = None,
    max_emails: int = 5000,
) -> List[Dict[str, Any]]:
    """Забирает письма из Outlook.

    Поиск идёт по ВСЕМУ ЯЩИКУ: все корневые папки namespace.Folders,
    каждая рекурсивно до MAX_FOLDER_DEPTH. Это включает Inbox,
    пользовательские папки («KRS GM» и т.п.), «Архив», «Отправленные»,
    отдельные .pst — всё, что подключено к Outlook.

    Args:
        days_back:       за сколько дней. None — весь ящик (без фильтра по дате).
        sender_filter:   подстрока в e-mail отправителя.
        subject_filters: список подстрок в теме (любая из них).
        max_emails:      максимум писем всего (защита).
    """
    if not OUTLOOK_AVAILABLE:
        log.warning("fetch_emails: Outlook недоступен")
        return []

    try:
        import win32com.client
        import pythoncom
    except ImportError:
        log.warning("fetch_emails: win32com или pythoncom не установлен")
        return []

    # CoInitialize может вернуть S_FALSE (уже инициализирован).
    com_initialized = False
    try:
        hr = pythoncom.CoInitialize()
        com_initialized = (hr == 0)
    except Exception:
        pythoncom = None

    try:
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
        except Exception as e:
            log.error(f"fetch_emails: не удалось подключиться к Outlook: {e}")
            return []

        try:
            namespace = outlook.GetNamespace("MAPI")
        except Exception as e:
            log.error(f"fetch_emails: не удалось получить MAPI namespace: {e}")
            return []

        # Дата отсечки
        if days_back is None:
            cutoff = None
            log.info("fetch_emails: фильтр по дате отключён — весь ящик")
        else:
            cutoff = datetime.now() - timedelta(days=days_back)

        if subject_filters is None:
            subject_filters = SUBJECT_FILTERS
        subject_filters_lower = [s.lower() for s in subject_filters if s]

        result: List[Dict[str, Any]] = []
        seen_entry_ids = set()
        scanned_total = 0
        folders_scanned = 0

        for root in _iter_root_folders(namespace):
            try:
                root_name = str(root.Name or "?")
            except Exception:
                root_name = "?"

            for subfolder in _walk_folders(root, depth=0, max_depth=MAX_FOLDER_DEPTH):
                folders_scanned += 1

                try:
                    sub_name = str(subfolder.Name or "?")
                except Exception:
                    sub_name = "?"

                try:
                    items = subfolder.Items
                    try:
                        items.Sort("[ReceivedTime]", True)
                    except Exception:
                        pass
                except Exception as e:
                    log.debug(f"fetch_emails: не удалось открыть «{root_name}/{sub_name}»: {e}")
                    continue

                folder_hits = 0

                for item in items:
                    if len(result) >= max_emails:
                        break
                    scanned_total += 1

                    try:
                        if item.Class != OL_MAIL:
                            continue

                        received = item.ReceivedTime
                        try:
                            if hasattr(received, "year"):
                                received_dt = datetime(
                                    received.year, received.month, received.day,
                                    received.hour, received.minute, received.second,
                                )
                            else:
                                received_dt = datetime.now()
                        except Exception:
                            received_dt = datetime.now()

                        if cutoff is not None and received_dt < cutoff:
                            continue

                        sender_variants = _get_sender_variants(item)
                        sender_raw = sender_variants[0] if sender_variants else ""

                        if sender_filter:
                            sf = sender_filter.lower()
                            if not any(sf in v.lower() for v in sender_variants):
                                continue

                        try:
                            subject = str(item.Subject or "")
                        except Exception:
                            subject = ""

                        if subject_filters_lower:
                            subj_lower = subject.lower()
                            if not any(f in subj_lower for f in subject_filters_lower):
                                continue

                        try:
                            body = str(item.Body or "")
                        except Exception:
                            body = ""

                        try:
                            entry_id = str(item.EntryID or "")
                        except Exception:
                            entry_id = ""

                        if entry_id and entry_id in seen_entry_ids:
                            continue
                        if entry_id:
                            seen_entry_ids.add(entry_id)

                        smtp = _get_smtp_address(item)

                        result.append({
                            "entry_id": entry_id,
                            "subject": subject,
                            "body": body,
                            "date": received_dt.isoformat(),
                            "sender": smtp or sender_raw,
                            "sender_raw": sender_raw,
                            "received_time": received_dt.strftime("%d.%m.%Y %H:%M"),
                            "folder": sub_name,
                            "root_folder": root_name,
                        })
                        folder_hits += 1

                    except Exception as e:
                        log.debug(f"fetch_emails: пропускаю письмо — {e}")
                        continue

                if folder_hits:
                    log.debug(
                        f"fetch_emails: «{root_name}/{sub_name}» — "
                        f"{folder_hits} писем"
                    )

        log.info(
            f"fetch_emails: получено {len(result)} писем "
            f"(просканировано {scanned_total}, папок {folders_scanned})"
        )
        return result

    finally:
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def extract_report_date(subject: str) -> str:
    m = re.search(r"(\d{2}\.\d{2}\.\d{4})", subject)
    return m.group(1) if m else ""


def extract_gm_name(subject: str) -> str:
    m = re.search(r"ГМ\s+(.+?)\s*[—\-]\s*\d{2}\.\d{2}\.\d{4}", subject)
    return m.group(1).strip() if m else ""


def is_outlook_available() -> bool:
    return OUTLOOK_AVAILABLE