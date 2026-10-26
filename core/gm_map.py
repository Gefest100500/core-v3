# core/gm_map.py
"""
Работа с картой ГМ: геокодинг городов, кэш координат, поиск магазинов.

Использует Nominatim (OpenStreetMap) для получения координат.
Кэш хранится в data/gm_cities_cache.json.

ИЗМЕНЕНИЯ:
- find_store_by_text: добавлена защита от пустой строки.
  Раньше пустой text_lower ("") давал совпадение с любым названием
  ("" in name всегда True), и функция возвращала первый магазин.
  Теперь пустой запрос возвращает None.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

from utils.logger import log


# --- НАДЁЖНОЕ ПОСТРОЕНИЕ ПУТИ ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GM_DATA_PATH = os.path.join(_PROJECT_ROOT, "data", "gm_data.json")
CACHE_PATH = os.path.join(_PROJECT_ROOT, "data", "gm_cities_cache.json")


def _extract_city(name):
    """'Альметьевск 1 Шевченко' -> 'Альметьевск'"""
    match = re.match(r'^([^\d]+?)\s+\d', name)
    if match:
        return match.group(1).strip()
    return None


def load_gm_data():
    """Загружает gm_data.json"""
    if not os.path.exists(GM_DATA_PATH):
        raise FileNotFoundError(f"Файл не найден: {GM_DATA_PATH}")
    with open(GM_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("gm_data.json должен содержать массив [] объектов.")
    return data


def get_unique_cities(data):
    """Возвращает отсортированный список уникальных городов"""
    cities = set()
    for row in data:
        name = row.get("Название", "")
        city = _extract_city(name)
        if city:
            cities.add(city)
    return sorted(cities)


def geocode_city(city_name):
    """Геокодирование через Nominatim (OpenStreetMap)"""
    url = "https://nominatim.openstreetmap.org/search"
    params = urllib.parse.urlencode({
        "q": f"{city_name}, Россия",
        "format": "json",
        "limit": 1
    })
    full_url = f"{url}?{params}"
    req = urllib.request.Request(full_url)
    req.add_header("User-Agent", "CoreAudit/1.0")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


def get_city_coords(force_rebuild=False):
    """Возвращает координаты городов из кэша (или генерирует заново)"""
    if not force_rebuild and os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    data = load_gm_data()
    cities = get_unique_cities(data)

    log.info(f"Геокодирование {len(cities)} городов...")
    coords = {}
    for i, city in enumerate(cities, 1):
        percent = int(100 * i / len(cities))
        log.debug(f"[{i}/{len(cities)}] ({percent}%) {city}...")
        result = geocode_city(city)
        if result:
            coords[city] = {"lat": result[0], "lon": result[1]}
            log.debug(f"  {city}: OK")
        else:
            log.debug(f"  {city}: не найдено")
        time.sleep(1.1)

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(coords, f, ensure_ascii=False, indent=2)
    log.info(f"Готово: {len(coords)} городов. Кэш: {CACHE_PATH}")
    return coords


def update_cache_if_needed():
    """Проверяет, все ли города в кэше. Если нет — догружает."""
    try:
        data = load_gm_data()
        cities = set(get_unique_cities(data))

        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cached = json.load(f)
            missing = cities - set(cached.keys())
        else:
            cached = {}
            missing = cities

        if not missing:
            return cached

        log.info(f"Обновление кэша: не хватает {len(missing)} городов")
        for city in missing:
            result = geocode_city(city)
            if result:
                cached[city] = {"lat": result[0], "lon": result[1]}
            time.sleep(1.1)

        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cached, f, ensure_ascii=False, indent=2)
        return cached
    except Exception:
        return get_city_coords()


def get_stores_by_city(stores_data):
    """Группирует магазины по городам"""
    result = {}
    for row in stores_data:
        city = _extract_city(row.get("Название", ""))
        if not city:
            continue
        result.setdefault(city, []).append(row)
    return result


def find_store_by_text(text, stores_data):
    """Ищет магазин по строке (точное или частичное совпадение).
    Возвращает dict магазина или None.

    ИЗМЕНЕНИЯ:
    - Добавлена защита от пустой строки: если text после strip() пустой,
      возвращается None. Раньше пустая строка совпадала с любым
      названием ("" in name всегда True) и функция возвращала
      первый магазин из списка.
    """
    text_lower = text.strip().lower()

    # Защита от пустой строки
    if not text_lower:
        return None

    # Точное совпадение названия
    for store in stores_data:
        if store.get("Название", "").lower() == text_lower:
            return store

    # Частичное совпадение
    for store in stores_data:
        name = store.get("Название", "").lower()
        address = store.get("Адрес", "").lower()
        if text_lower in name or text_lower in address:
            return store

    return None