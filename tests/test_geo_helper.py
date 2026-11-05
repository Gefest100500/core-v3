# tests/test_geo_helper.py
"""
Тесты для core/geo_helper.py.

Проверяем:
- get_local_ip (через мок сокета)
- find_gm_by_ip (поиск кода ГМ по подсети)
- get_city_by_gm_code (поиск города по коду ГМ)
- get_coords_by_city (поиск координат по городу)
"""
import json
import socket
from pathlib import Path

import pytest

from core import geo_helper


# =========================================================
# Вспомогательные функции для создания временных файлов
# =========================================================
def _create_gm_ip_file(tmp_path: Path, data: dict) -> Path:
    file_path = tmp_path / "gm_ip.json"
    file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return file_path


def _create_gm_data_file(tmp_path: Path, data: list) -> Path:
    file_path = tmp_path / "gm_data.json"
    file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return file_path


@pytest.fixture
def fake_base_dir(tmp_path, monkeypatch):
    """Подменяет Path(__file__).parent.parent на tmp_path."""
    # В geo_helper.py используется Path(__file__).parent.parent
    # Мы подменяем вычисление base_dir через monkeypatch на функцию
    def _fake_base():
        return tmp_path

    # Патчим напрямую конструирование пути внутри функций
    # Проще всего подменить __file__ в модуле, но так как это глобально,
    # лучше сделать фикстуру, которая создаёт структуру папок.
    (tmp_path / "data").mkdir()
    return tmp_path


# =========================================================
# get_local_ip
# =========================================================
class TestGetLocalIp:

    def test_returns_ip(self, monkeypatch):
        # Мокаем сокет, чтобы он возвращал конкретный IP
        class FakeSocket:
            def __init__(self, *args, **kwargs):
                pass
            def connect(self, *args, **kwargs):
                pass
            def getsockname(self):
                return ("10.4.90.31", 12345)
            def close(self):
                pass

        monkeypatch.setattr(socket, "socket", lambda *a, **kw: FakeSocket())
        ip = geo_helper.get_local_ip()
        assert ip == "10.4.90.31"

    def test_returns_empty_on_error(self, monkeypatch):
        # Если всё падает — возвращает пустую строку
        monkeypatch.setattr(socket, "socket", lambda *a, **kw: (_ for _ in ()).throw(OSError))
        monkeypatch.setattr(socket, "gethostbyname", lambda *a, **kw: (_ for _ in ()).throw(OSError))
        ip = geo_helper.get_local_ip()
        assert ip == ""


# =========================================================
# find_gm_by_ip
# =========================================================
class TestFindGmByIp:

    def test_finds_by_subnet(self, tmp_path, monkeypatch, fake_base_dir):
        ip_data = {
            "991602": "10.4.90.1",
            "992320": "10.2.68.1",
        }
        _create_gm_ip_file(fake_base_dir / "data", ip_data)

        # Подменяем Path(__file__).parent.parent на fake_base_dir
        monkeypatch.setattr(
            geo_helper, "__file__", str(fake_base_dir / "core" / "geo_helper.py")
        )
        # Создаём папку core, чтобы Path(__file__).parent.parent == fake_base_dir
        (fake_base_dir / "core").mkdir(exist_ok=True)

        code = geo_helper.find_gm_by_ip("10.4.90.31")
        assert code == "991602"

    def test_not_found(self, tmp_path, monkeypatch, fake_base_dir):
        ip_data = {"991602": "10.4.90.1"}
        _create_gm_ip_file(fake_base_dir / "data", ip_data)
        (fake_base_dir / "core").mkdir(exist_ok=True)
        monkeypatch.setattr(
            geo_helper, "__file__", str(fake_base_dir / "core" / "geo_helper.py")
        )

        code = geo_helper.find_gm_by_ip("192.168.1.100")
        assert code == ""

    def test_empty_ip(self):
        assert geo_helper.find_gm_by_ip("") == ""


# =========================================================
# get_city_by_gm_code
# =========================================================
class TestGetCityByGmCode:

    def test_finds_city(self, tmp_path, monkeypatch, fake_base_dir):
        gm_data = [
            {"Код": "991602", "Название": "Бугульма 1 Советская"},
            {"Код": "992320", "Название": "Киров 2 Ленина"},
        ]
        _create_gm_data_file(fake_base_dir / "data", gm_data)
        (fake_base_dir / "core").mkdir(exist_ok=True)
        monkeypatch.setattr(
            geo_helper, "__file__", str(fake_base_dir / "core" / "geo_helper.py")
        )

        city = geo_helper.get_city_by_gm_code("991602")
        assert city == "бугульма"

    def test_not_found(self, tmp_path, monkeypatch, fake_base_dir):
        gm_data = [{"Код": "991602", "Название": "Бугульма 1"}]
        _create_gm_data_file(fake_base_dir / "data", gm_data)
        (fake_base_dir / "core").mkdir(exist_ok=True)
        monkeypatch.setattr(
            geo_helper, "__file__", str(fake_base_dir / "core" / "geo_helper.py")
        )

        city = geo_helper.get_city_by_gm_code("999999")
        assert city == ""


# =========================================================
# get_coords_by_city
# =========================================================
class TestGetCoordsByCity:

    def test_known_city(self):
        coords = geo_helper.get_coords_by_city("бугульма")
        assert coords == (54.53, 52.79)

    def test_unknown_city(self):
        coords = geo_helper.get_coords_by_city("неизвестный_город")
        assert coords is None

    def test_empty(self):
        assert geo_helper.get_coords_by_city("") is None