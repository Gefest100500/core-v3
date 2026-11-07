# core/log_sender.py
"""
Отправка логов разработчику через Outlook.
Чистая логика. Без PyQt. Тестируется отдельно.
"""
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from utils.logger import log

try:
    import win32com.client
    OUTLOOK_AVAILABLE = True
except ImportError:
    OUTLOOK_AVAILABLE = False
    log.info("log_sender: win32com не установлен — отправка логов отключена")

# Настройки отправки
LOG_EMAIL_TO = "silchenko_as@magnit.ru"  # ЗАМЕНИ НА СВОЮ ПОЧТУ
LOG_SUBJECT_PREFIX = "Core V3.0 — Лог"


def _get_log_file() -> Path:
    """Возвращает путь к текущему файлу лога."""
    # Ищем app.log или похожий в корне программы
    possible_names = ["app.log", "core.log", "log.txt"]
    base_dir = Path.cwd()  # или get_base_dir() из твоих утилит
    
    for name in possible_names:
        p = base_dir / name
        if p.is_file():
            return p
            
    # Если не нашли, ищем в папке logs
    logs_dir = base_dir / "logs"
    if logs_dir.is_dir():
        for name in possible_names:
            p = logs_dir / name
            if p.is_file():
                return p
                
    return None


def send_log_to_dev(extra_info: str = "") -> Dict[str, Any]:
    """
    Создает письмо в Outlook с логом и отправляет.
    Возвращает словарь с результатом.
    """
    result = {"success": False, "error": "", "file": ""}
    
    if not OUTLOOK_AVAILABLE:
        result["error"] = "Outlook недоступен (нет win32com)"
        return result

    log_file = _get_log_file()
    if not log_file:
        result["error"] = "Файл лога не найден"
        return result

    result["file"] = str(log_file)

    try:
        # Подключаемся к Outlook
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = MailItem

        # Формируем тему
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        pc_name = platform.node()
        mail.Subject = f"{LOG_SUBJECT_PREFIX} от {pc_name} ({now_str})"

        # Формируем тело
        body = f"Автоматическая отправка лога.\n\n"
        body += f"Компьютер: {pc_name}\n"
        body += f"ОС: {platform.system()} {platform.release()}\n"
        body += f"Время: {now_str}\n"
        if extra_info:
            body += f"\nДополнительно:\n{extra_info}\n"
        body += "\nЛог прикреплен к письму."
        
        mail.Body = body
        mail.To = LOG_EMAIL_TO

        # Прикрепляем файл
        mail.Attachments.Add(str(log_file))

        # Отправляем
        mail.Send()
        
        result["success"] = True
        log.info(f"log_sender: лог успешно отправлен на {LOG_EMAIL_TO}")
        
    except Exception as e:
        result["error"] = str(e)
        log.error(f"log_sender: ошибка отправки: {e}")

    return result


def should_auto_send(last_sent_iso: str) -> bool:
    """
    Проверяет, нужно ли отправить лог автоматически.
    Если с последней отправки прошло больше 7 дней — True.
    """
    if not last_sent_iso:
        return True
        
    try:
        last_dt = datetime.fromisoformat(last_sent_iso)
        diff = datetime.now() - last_dt
        return diff.days >= 7
    except Exception:
        return True