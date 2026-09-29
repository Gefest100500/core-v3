# utils/machine_info.py
import os
import re
import socket
import json
from datetime import datetime

from utils.logger import log


SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "user_settings.json"
)


def get_machine_name():
    """Возвращает имя компьютера."""
    try:
        return socket.gethostname()
    except Exception:
        return os.environ.get("COMPUTERNAME", "")


def get_local_ip():
    """Возвращает локальный IP (IPv4)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    except Exception:
        return None


def load_user_settings():
    """Загружает user_settings.json."""
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_user_settings(settings):
    """Сохраняет user_settings.json."""
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"Не удалось сохранить user_settings.json: {e}")


def get_saved_gm_code():
    """Возвращает сохранённый код ГМ (если он сохранён СЕГОДНЯ).

    Returns:
        Код ГМ или None, если:
        - Не сохранён
        - Сохранён вчера или раньше
    """
    settings = load_user_settings()
    code = settings.get("gm_code")
    saved_date = settings.get("gm_code_date")

    if not code:
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    if saved_date != today:
        log.info(f"Код ГМ сохранён {saved_date}, сегодня {today} — нужно переопределить")
        return None

    return code


def get_saved_gm_code_any_date():
    """Возвращает сохранённый код ГМ независимо от даты (для UI-показа)."""
    settings = load_user_settings()
    return settings.get("gm_code")


def get_saved_gm_date():
    """Возвращает дату сохранения ГМ."""
    settings = load_user_settings()
    return settings.get("gm_code_date")


def set_saved_gm_code(code):
    """Сохраняет код ГМ с текущей датой. Если code=None — удаляет."""
    settings = load_user_settings()

    if code:
        settings["gm_code"] = code
        settings["gm_code_date"] = datetime.now().strftime("%Y-%m-%d")
    else:
        settings.pop("gm_code", None)
        settings.pop("gm_code_date", None)

    save_user_settings(settings)


def is_gm_saved_today():
    """Проверяет, сохранён ли ГМ сегодня."""
    return get_saved_gm_code() is not None


def get_machine_info():
    """Возвращает информацию о машине и сохранённый код ГМ."""
    return {
        "name": get_machine_name(),
        "ip": get_local_ip(),
        "gm_code": get_saved_gm_code(),
        "gm_code_any": get_saved_gm_code_any_date(),
        "gm_date": get_saved_gm_date(),
    }