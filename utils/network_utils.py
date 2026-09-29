# utils/network_utils.py
import re
import socket
import subprocess

from utils.logger import log


# Стандартные порты сетевых принтеров
PRINTER_PORTS = [9100, 515, 631, 80, 443]  # RAW, LPD, IPP, HTTP, HTTPS


def extract_ip_from_text(text):
    """Извлекает IPv4-адрес из произвольного текста.

    Примеры:
        'IP: 010.003.002.094'         → '10.3.2.94'
        '\\\\10.3.2.94\\printer'      → '10.3.2.94'
        'http://10.3.2.94:8080'       → '10.3.2.94'
        '10.3.2.94'                   → '10.3.2.94'
        '  10 . 3 . 2 . 94  '         → '10.3.2.94'
        '192.168.001.100'             → '192.168.1.100'

    Returns:
        Нормализованный IP или None, если не найдено.
    """
    if not text:
        return None

    # Убираем пробелы вокруг точек: "10 . 3 . 2 . 94" → "10.3.2.94"
    cleaned = re.sub(r'\s*\.\s*', '.', text.strip())

    # Ищем 4 группы цифр, разделённых точками
    # Не заботясь о диапазоне пока — нормализуем позже
    matches = re.findall(r'\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b', cleaned)

    if not matches:
        return None

    # Берём первую четвёрку
    parts = matches[0]

    # Проверяем диапазон и убираем ведущие нули
    normalized_parts = []
    for p in parts:
        try:
            n = int(p)
            if n < 0 or n > 255:
                # Невалидный октет — это не IP
                return None
            normalized_parts.append(str(n))
        except ValueError:
            return None

    return ".".join(normalized_parts)


def normalize_ip(ip):
    """Нормализует IP-адрес (убирает ведущие нули, лишние символы).

    Возвращает нормализованный IP или пустую строку, если невозможно.
    """
    if not ip:
        return ""

    extracted = extract_ip_from_text(ip)
    return extracted or ""


def is_valid_ip(ip):
    """Проверяет корректность IPv4-адреса."""
    if not ip:
        return False

    parts = ip.split(".")
    if len(parts) != 4:
        return False

    for part in parts:
        try:
            n = int(part)
            if n < 0 or n > 255:
                return False
        except ValueError:
            return False

    return True


def ping_host(host, timeout=3):
    """Пингует хост. Возвращает (success, info)."""
    try:
        result = subprocess.run(
            ["ping", "-n", "2", "-w", "1000", host],
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="replace",
            timeout=timeout + 3,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )

        output = result.stdout or ""

        if "TTL=" in output or "ttl=" in output.lower():
            m = re.search(r'(?:time|время)[=<]\s*(\d+)\s*мс', output, re.IGNORECASE)
            if m:
                return True, f"{m.group(1)} мс"
            return True, "доступен"

        return False, "нет ответа"

    except subprocess.TimeoutExpired:
        return False, "таймаут"
    except Exception as e:
        log.warning(f"Ошибка пинга {host}: {e}")
        return False, str(e)


def check_printer_port(host, timeout=2):
    """Проверяет доступность стандартных портов принтера.

    Returns:
        (True, port) — если порт открыт
        (False, None) — если ничего не открыто
    """
    for port in PRINTER_PORTS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            result = s.connect_ex((host, port))
            s.close()

            if result == 0:
                return True, port
        except Exception:
            continue

    return False, None


def check_host(host, timeout=3):
    """Полная проверка доступности хоста."""
    result = {
        "online": False,
        "port": None,
        "ping_ok": False,
        "ping_info": "",
    }

    port_ok, port = check_printer_port(host, timeout=timeout)
    if port_ok:
        result["online"] = True
        result["port"] = port
        log.info(f"Хост {host}: открыт порт {port}")

    ping_ok, ping_info = ping_host(host, timeout=timeout)
    result["ping_ok"] = ping_ok
    result["ping_info"] = ping_info

    if ping_ok:
        result["online"] = True

    return result