# core/terminal_helper.py
"""
Вспомогательная логика для вкладки «Терминал».

Здесь нет PyQt. Только чистые функции:
- Поиск ГМ по коду / названию / IP / шаблону S...term.
- Формирование цели подключения S{код}term.
- Шифрование и дешифрование пароля (XOR + base64).
- Генерация ключа шифрования на основе имени пользователя Windows.

Это позволяет тестировать логику без запуска Qt.
"""
import base64
import getpass
import hashlib
import re
from typing import Optional, Dict, Any, List


# Ключ для XOR-шифрования пароля
_XOR_KEY_BASE = "CoreV3_Terminal_Secret"


def get_password_key() -> str:
    """Возвращает ключ шифрования на основе имени пользователя Windows."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "default"
    raw = f"{_XOR_KEY_BASE}:{user}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def xor_encrypt(text: str, key: str) -> str:
    """XOR-шифрование + base64. Обратимо."""
    data = text.encode("utf-8")
    key_bytes = key.encode("utf-8")
    out = bytearray()
    for i, b in enumerate(data):
        out.append(b ^ key_bytes[i % len(key_bytes)])
    return base64.b64encode(bytes(out)).decode("ascii")


def xor_decrypt(token: str, key: str) -> str:
    """Обратное к xor_encrypt. При ошибке возвращает пустую строку."""
    try:
        data = base64.b64decode(token.encode("ascii"))
        key_bytes = key.encode("utf-8")
        out = bytearray()
        for i, b in enumerate(data):
            out.append(b ^ key_bytes[i % len(key_bytes)])
        return bytes(out).decode("utf-8")
    except Exception:
        return ""


def build_target(code: str) -> str:
    """Формирует цель подключения.

    Если code уже выглядит как S...term — возвращает как есть.
    Иначе — оборачивает в S{code}term.
    """
    code = code.strip()
    if not code:
        return ""
    if re.fullmatch(r"S\d+term", code, re.IGNORECASE):
        return code
    return f"S{code}term"


def resolve_gm(text: str, gm_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Ищет ГМ по коду, названию, IP или шаблону S...term.

    Приоритет поиска:
    1. Точное совпадение по коду.
    2. Точное совпадение по названию (без учёта регистра).
    3. Совпадение по IP (подстрока в поле «Папка»).
    4. Готовый шаблон S...term (возвращается как «виртуальный» ГМ).
    5. Частичное вхождение в название (без учёта регистра).

    Возвращает словарь из gm_data или синтетический {"Код": ..., "Название": ...},
    либо None, если ничего не найдено.
    """
    text = text.strip()
    if not text:
        return None

    # 1) Точное совпадение по коду
    for item in gm_data:
        if item.get("Код", "") == text:
            return item

    # 2) Точное совпадение по названию
    for item in gm_data:
        if item.get("Название", "").lower() == text.lower():
            return item

    # 3) Совпадение по IP
    for item in gm_data:
        if text in item.get("Папка", ""):
            return item

    # 4) Готовый шаблон S...term
    if re.fullmatch(r"S\d+term", text, re.IGNORECASE):
        return {"Код": text, "Название": text}

    # 5) Частичное вхождение в название
    for item in gm_data:
        if text.lower() in item.get("Название", "").lower():
            return item

    return None


def get_gm_names(gm_data: List[Dict[str, Any]]) -> List[str]:
    """Возвращает список названий ГМ для QCompleter."""
    names = []
    for g in gm_data:
        name = g.get("Название", "").strip()
        if name:
            names.append(name)
    return names