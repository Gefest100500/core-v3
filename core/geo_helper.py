# core/geo_helper.py
"""
Помощник для определения города по локальному IP.
"""
import json
import socket
from pathlib import Path

from utils.logger import log


# Базовые координаты для городов (можно пополнять)
CITY_COORDS = {
    "бугульма": (54.53, 52.79),
    "киров": (58.60, 49.66),
    "казань": (55.79, 49.10),
    "ижевск": (56.85, 53.20),
    "елабуга": (55.75, 52.06),
    "нижнекамск": (55.63, 51.82),
    "набережные челны": (55.74, 52.40),
    "балаково": (52.02, 47.80),
    "самара": (53.20, 50.15),
    "тольятти": (53.51, 49.42),
    "уфа": (54.73, 55.97),
    "саратов": (51.53, 46.03),
    "волгоград": (48.71, 44.51),
    "москва": (55.75, 37.61),
}


def get_local_ip() -> str:
    """Возвращает локальный IP компьютера."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        print(f"[GEO] Локальный IP: {ip}")
        return ip
    except Exception as e:
        print(f"[GEO] Ошибка получения IP: {e}")
        try:
            ip = socket.gethostbyname(socket.gethostname())
            print(f"[GEO] Локальный IP (fallback): {ip}")
            return ip
        except Exception as e2:
            print(f"[GEO] Ошибка fallback: {e2}")
            return ""


def find_gm_by_ip(ip: str) -> str:
    """Ищет Код ГМ по локальному IP."""
    if not ip:
        return ""

    parts = ip.split(".")
    if len(parts) != 4:
        return ""
    subnet = ".".join(parts[:3])
    print(f"[GEO] Ищем подсеть: {subnet}")

    base_dir = Path(__file__).parent.parent
    ip_file = base_dir / "data" / "gm_ip.json"
    
    # Проверяем также LOCALAPPDATA
    if not ip_file.is_file():
        import os
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            alt = Path(appdata) / "Core_V3_0" / "data" / "gm_ip.json"
            if alt.is_file():
                ip_file = alt

    print(f"[GEO] Ищем файл: {ip_file}")
    if not ip_file.is_file():
        print(f"[GEO] Файл не найден!")
        return ""

    try:
        with open(ip_file, "r", encoding="utf-8") as f:
            ip_data = json.load(f)
    except Exception as e:
        print(f"[GEO] Ошибка чтения: {e}")
        return ""

    for code, gm_ip in ip_data.items():
        if not gm_ip:
            continue
        gm_parts = gm_ip.split(".")
        if len(gm_parts) == 4:
            gm_subnet = ".".join(gm_parts[:3])
            if gm_subnet == subnet:
                print(f"[GEO] Найден ГМ: {code} ({gm_ip})")
                return code

    print(f"[GEO] Подсеть {subnet} не найдена в справочнике")
    return ""


def get_city_by_gm_code(code: str) -> str:
    """По коду ГМ находит название города (из gm_data.json)."""
    if not code:
        return ""

    base_dir = Path(__file__).parent.parent
    gm_file = base_dir / "data" / "gm_data.json"
    
    import os
    if not gm_file.is_file():
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            alt = Path(appdata) / "Core_V3_0" / "data" / "gm_data.json"
            if alt.is_file():
                gm_file = alt

    if not gm_file.is_file():
        print(f"[GEO] gm_data.json не найден")
        return ""

    try:
        with open(gm_file, "r", encoding="utf-8") as f:
            gm_data = json.load(f)
    except Exception as e:
        print(f"[GEO] Ошибка чтения gm_data.json: {e}")
        return ""

    for gm in gm_data:
        if str(gm.get("Код", "")) == str(code):
            name = gm.get("Название", "")
            if name:
                city = name.split()[0].lower()
                print(f"[GEO] Город по коду {code}: {city}")
                return city
            break

    print(f"[GEO] Код {code} не найден в gm_data.json")
    return ""


def get_coords_by_city(city: str):
    """Возвращает (lat, lon) для города."""
    if not city:
        return None
    coords = CITY_COORDS.get(city.lower())
    if coords:
        print(f"[GEO] Координаты для {city}: {coords}")
    else:
        print(f"[GEO] Нет координат для города {city}")
    return coords