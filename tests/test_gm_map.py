# tests/test_gm_map.py
"""
Тесты для core/gm_map.py.

Проверяем:
- Извлечение города из названия ГМ.
- Загрузку gm_data.json (успех, отсутствие файла, битый JSON).
- Уникальные города.
- Группировку магазинов по городам.
- Поиск магазина по тексту (точное/частичное совпадение).
- Геокодинг (замокан, без реальных запросов).
- Кэш координат (замокан).
"""
import json
import os
import pytest

from core import gm_map


# =========================================================
# _extract_city
# =========================================================
class TestExtractCity:

    def test_simple(self):
        assert gm_map._extract_city("Альметьевск 1 Шевченко") == "Альметьевск"

    def test_multiword_city(self):
        assert gm_map._extract_city("Набережные Челны 1 Чулман") == "Набережные Челны"

    def test_city_with_hyphen(self):
        assert gm_map._extract_city("Ростов-на-Дону 1 Лелюшенко") == "Ростов-на-Дону"

    def test_no_digit_returns_none(self):
        assert gm_map._extract_city("Просто название без цифры") is None

    def test_empty_returns_none(self):
        assert gm_map._extract_city("") is None

    def test_digit_at_start_returns_none(self):
        # Название начинается с цифры — не город
        assert gm_map._extract_city("1 Мая") is None


# =========================================================
# load_gm_data
# =========================================================
class TestLoadGmData:

    def test_success(self, tmp_path, monkeypatch):
        data = [{"Код": "1", "Название": "Тест 1"}]
        path = tmp_path / "gm_data.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(gm_map, "GM_DATA_PATH", str(path))

        result = gm_map.load_gm_data()
        assert result == data

    def test_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gm_map, "GM_DATA_PATH", str(tmp_path / "missing.json"))
        with pytest.raises(FileNotFoundError):
            gm_map.load_gm_data()

    def test_not_a_list(self, tmp_path, monkeypatch):
        path = tmp_path / "gm_data.json"
        path.write_text('{"a": 1}', encoding="utf-8")
        monkeypatch.setattr(gm_map, "GM_DATA_PATH", str(path))

        with pytest.raises(ValueError, match="массив"):
            gm_map.load_gm_data()


# =========================================================
# get_unique_cities
# =========================================================
class TestGetUniqueCities:

    def test_unique_and_sorted(self):
        data = [
            {"Название": "Москва 1 Ярославское шоссе"},
            {"Название": "Альметьевск 1 Шевченко"},
            {"Название": "Москва 2 Ярославское шоссе"},
            {"Название": "Без цифры"},
        ]
        result = gm_map.get_unique_cities(data)
        assert result == ["Альметьевск", "Москва"]

    def test_empty(self):
        assert gm_map.get_unique_cities([]) == []


# =========================================================
# get_stores_by_city
# =========================================================
class TestGetStoresByCity:

    def test_groups(self):
        data = [
            {"Название": "Москва 1 Ярославское шоссе", "Код": "1"},
            {"Название": "Москва 2 Ярославское шоссе", "Код": "2"},
            {"Название": "Альметьевск 1 Шевченко", "Код": "3"},
        ]
        result = gm_map.get_stores_by_city(data)
        assert len(result["Москва"]) == 2
        assert len(result["Альметьевск"]) == 1

    def test_skips_bad_names(self):
        data = [
            {"Название": "Без цифры"},
            {"Название": "Москва 1 Тест"},
        ]
        result = gm_map.get_stores_by_city(data)
        assert "Москва" in result
        assert len(result) == 1

    def test_empty(self):
        assert gm_map.get_stores_by_city([]) == {}


# =========================================================
# find_store_by_text
# =========================================================
@pytest.fixture
def stores():
    return [
        {"Название": "Москва 1 Ярославское шоссе", "Адрес": "ул. Ленина 1"},
        {"Название": "Альметьевск 1 Шевченко", "Адрес": "ул. Шевченко 5"},
    ]


class TestFindStoreByText:

    def test_exact_name(self, stores):
        result = gm_map.find_store_by_text("Москва 1 Ярославское шоссе", stores)
        assert result is not None
        assert result["Название"] == "Москва 1 Ярославское шоссе"

    def test_exact_name_case_insensitive(self, stores):
        result = gm_map.find_store_by_text("москва 1 ярославское шоссе", stores)
        assert result is not None

    def test_partial_name(self, stores):
        result = gm_map.find_store_by_text("Альметьевск", stores)
        assert result is not None
        assert result["Название"].startswith("Альметьевск")

    def test_partial_address(self, stores):
        result = gm_map.find_store_by_text("Шевченко", stores)
        assert result is not None

    def test_not_found(self, stores):
        assert gm_map.find_store_by_text("Несуществующий", stores) is None

    def test_empty_text(self, stores):
        assert gm_map.find_store_by_text("", stores) is None


# =========================================================
# geocode_city (замокан urllib)
# =========================================================
class TestGeocodeCity:

    def test_success(self, monkeypatch):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b'[{"lat": "55.75", "lon": "37.61"}]'

        def fake_urlopen(req, timeout=10):
            return FakeResponse()

        monkeypatch.setattr(gm_map.urllib.request, "urlopen", fake_urlopen)

        result = gm_map.geocode_city("Москва")
        assert result == (55.75, 37.61)

    def test_empty_result(self, monkeypatch):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b'[]'

        monkeypatch.setattr(
            gm_map.urllib.request, "urlopen",
            lambda req, timeout=10: FakeResponse()
        )

        assert gm_map.geocode_city("НесуществующийГород") is None

    def test_exception_returns_none(self, monkeypatch):
        def fake_urlopen(req, timeout=10):
            raise Exception("Network error")

        monkeypatch.setattr(gm_map.urllib.request, "urlopen", fake_urlopen)

        assert gm_map.geocode_city("Москва") is None


# =========================================================
# get_city_coords (кэш)
# =========================================================
class TestGetCityCoords:

    def test_loads_from_cache(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "cache.json"
        cache_data = {"Москва": {"lat": 55.75, "lon": 37.61}}
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        monkeypatch.setattr(gm_map, "CACHE_PATH", str(cache_path))

        result = gm_map.get_city_coords()
        assert result == cache_data

    def test_corrupted_cache_falls_back(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "cache.json"
        cache_path.write_text("not a json", encoding="utf-8")
        monkeypatch.setattr(gm_map, "CACHE_PATH", str(cache_path))

        # Заглушим load_gm_data / geocode_city / time.sleep
        monkeypatch.setattr(gm_map, "load_gm_data", lambda: [
            {"Название": "Москва 1 Тест"},
        ])
        monkeypatch.setattr(gm_map, "geocode_city",
                            lambda city: (55.75, 37.61) if city == "Москва" else None)
        monkeypatch.setattr(gm_map.time, "sleep", lambda x: None)

        result = gm_map.get_city_coords()
        assert "Москва" in result
        assert result["Москва"]["lat"] == 55.75


# =========================================================
# update_cache_if_needed
# =========================================================
class TestUpdateCacheIfNeeded:

    def test_returns_cache_if_complete(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "cache.json"
        cache_data = {"Москва": {"lat": 55.75, "lon": 37.61}}
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")
        monkeypatch.setattr(gm_map, "CACHE_PATH", str(cache_path))

        monkeypatch.setattr(gm_map, "load_gm_data", lambda: [
            {"Название": "Москва 1 Тест"},
        ])

        result = gm_map.update_cache_if_needed()
        assert result == cache_data

    def test_adds_missing_cities(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "cache.json"
        cache_data = {"Москва": {"lat": 55.75, "lon": 37.61}}
        cache_path.write_text(json.dumps(cache_data), encoding="utf-8")
        monkeypatch.setattr(gm_map, "CACHE_PATH", str(cache_path))

        monkeypatch.setattr(gm_map, "load_gm_data", lambda: [
            {"Название": "Москва 1 Тест"},
            {"Название": "Казань 1 Тест"},
        ])
        monkeypatch.setattr(gm_map, "geocode_city",
                            lambda city: (55.0, 49.0) if city == "Казань" else None)
        monkeypatch.setattr(gm_map.time, "sleep", lambda x: None)

        result = gm_map.update_cache_if_needed()
        assert "Москва" in result
        assert "Казань" in result

    def test_exception_falls_back(self, monkeypatch):
        monkeypatch.setattr(gm_map, "load_gm_data",
                            lambda: (_ for _ in ()).throw(Exception("fail")))
        monkeypatch.setattr(gm_map, "get_city_coords", lambda: {"fallback": 1})

        result = gm_map.update_cache_if_needed()
        assert result == {"fallback": 1}