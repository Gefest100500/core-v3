# tests/test_geo_utils.py
"""
Тесты для utils/geo_utils.py.

Проверяем:
- Формулу Haversine (расстояние по прямой).
- Оценку по дорогам.
- Оценку времени в пути.
- Форматирование времени.
- Полный расчёт (calculate_distance).
"""
import pytest

from utils.geo_utils import (
    haversine, estimate_by_road, estimate_duration,
    format_duration, calculate_distance,
)


# =========================================================
# haversine
# =========================================================
class TestHaversine:

    def test_same_point(self):
        assert haversine(55.75, 37.61, 55.75, 37.61) == pytest.approx(0.0, abs=0.01)

    def test_moscow_spb(self):
        # Москва (55.7558, 37.6173) → СПб (59.9343, 30.3351)
        # По прямой ~635 км
        d = haversine(55.7558, 37.6173, 59.9343, 30.3351)
        assert 630 < d < 640

    def test_symmetric(self):
        d1 = haversine(55.75, 37.61, 59.93, 30.33)
        d2 = haversine(59.93, 30.33, 55.75, 37.61)
        assert d1 == pytest.approx(d2, abs=0.01)


# =========================================================
# estimate_by_road
# =========================================================
class TestEstimateByRoad:

    def test_default_factor(self):
        assert estimate_by_road(100) == pytest.approx(120.0)

    def test_custom_factor(self):
        assert estimate_by_road(100, factor=1.5) == pytest.approx(150.0)

    def test_zero(self):
        assert estimate_by_road(0) == pytest.approx(0.0)


# =========================================================
# estimate_duration
# =========================================================
class TestEstimateDuration:

    def test_default_speed(self):
        # 80 км при 80 км/ч = 1 час
        assert estimate_duration(80) == pytest.approx(1.0)

    def test_custom_speed(self):
        assert estimate_duration(100, speed_kmh=50) == pytest.approx(2.0)

    def test_zero_distance(self):
        assert estimate_duration(0) == pytest.approx(0.0)

    def test_zero_speed_returns_zero(self):
        assert estimate_duration(100, speed_kmh=0) == 0

    def test_negative_speed_returns_zero(self):
        assert estimate_duration(100, speed_kmh=-10) == 0


# =========================================================
# format_duration
# =========================================================
class TestFormatDuration:

    def test_none(self):
        assert format_duration(None) == "—"

    def test_zero(self):
        assert format_duration(0) == "—"

    def test_negative(self):
        assert format_duration(-1) == "—"

    def test_minutes_only(self):
        # 0.5 часа = 30 минут
        assert format_duration(0.5) == "30 мин"

    def test_hours_and_minutes(self):
        # 11.7833 ч = 11 ч 47 мин (11*60 + 47 = 707 минут)
        assert format_duration(11 + 47 / 60) == "11 ч 47 мин"

    def test_exact_hour(self):
        assert format_duration(1.0) == "1 ч 0 мин"

    def test_rounding(self):
        # 0.75 ч = 45 минут
        assert format_duration(0.75) == "45 мин"


# =========================================================
# calculate_distance
# =========================================================
class TestCalculateDistance:

    def test_success(self):
        coords1 = {"lat": 55.7558, "lon": 37.6173}  # Москва
        coords2 = {"lat": 59.9343, "lon": 30.3351}  # СПб

        result = calculate_distance(coords1, coords2)
        assert result is not None
        assert "direct_km" in result
        assert "road_km" in result
        assert "duration_hours" in result
        assert "duration_str" in result

        assert 630 < result["direct_km"] < 640
        assert result["road_km"] == pytest.approx(result["direct_km"] * 1.2, abs=0.1)

    def test_custom_factor_and_speed(self):
        coords1 = {"lat": 0.0, "lon": 0.0}
        coords2 = {"lat": 0.0, "lon": 0.0}

        result = calculate_distance(coords1, coords2, road_factor=2.0, speed_kmh=100)
        assert result["direct_km"] == 0.0
        assert result["road_km"] == 0.0
        assert result["duration_hours"] == 0.0

    def test_invalid_coords_returns_none(self):
        result = calculate_distance({}, {"lat": 0, "lon": 0})
        assert result is None