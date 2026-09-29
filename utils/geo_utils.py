# utils/geo_utils.py
import math

from utils.logger import log


def haversine(lat1, lon1, lat2, lon2):
    """Расстояние по прямой между двумя точками (в км)"""
    R = 6371.0  # Радиус Земли в км
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def estimate_by_road(direct_km, factor=1.2):
    """Оценка расстояния по дорогам (по умолчанию ×1.2)"""
    return direct_km * factor


def estimate_duration(road_km, speed_kmh=80):
    """Оценка времени в пути (в часах)"""
    if speed_kmh <= 0:
        return 0
    return road_km / speed_kmh


def format_duration(hours):
    """Часы (float) → '11 ч 47 мин'"""
    if hours is None or hours <= 0:
        return "—"
    total_min = int(round(hours * 60))
    h = total_min // 60
    m = total_min % 60
    if h > 0:
        return f"{h} ч {m} мин"
    return f"{m} мин"


def calculate_distance(coords1, coords2, road_factor=1.2, speed_kmh=80):
    """Полный расчёт расстояния между двумя координатами.

    Args:
        coords1: {"lat": ..., "lon": ...}
        coords2: {"lat": ..., "lon": ...}
        road_factor: коэффициент для оценки по дорогам
        speed_kmh: средняя скорость для расчёта времени

    Returns:
        dict с полями:
            direct_km — по прямой
            road_km — по дорогам (оценка)
            duration_hours — время в часах
            duration_str — "11 ч 47 мин"
    """
    try:
        direct_km = haversine(
            coords1["lat"], coords1["lon"],
            coords2["lat"], coords2["lon"]
        )
        road_km = estimate_by_road(direct_km, road_factor)
        duration_h = estimate_duration(road_km, speed_kmh)

        return {
            "direct_km": round(direct_km, 1),
            "road_km": round(road_km, 1),
            "duration_hours": round(duration_h, 2),
            "duration_str": format_duration(duration_h),
        }
    except Exception as e:
        log.exception(f"Ошибка расчёта расстояния: {e}")
        return None