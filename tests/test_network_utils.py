# tests/test_network_utils.py
"""
Тесты для utils/network_utils.py.

Проверяем:
- Извлечение IP из текста.
- Нормализацию IP.
- Валидацию IP.
- Пинг (замокан subprocess).
- Проверку портов (замокан socket).
- Полную проверку хоста (check_host).
"""
import subprocess
import pytest

from utils import network_utils
from utils.network_utils import (
    extract_ip_from_text, normalize_ip, is_valid_ip,
    ping_host, check_printer_port, check_host, PRINTER_PORTS,
)


# =========================================================
# extract_ip_from_text
# =========================================================
class TestExtractIpFromText:

    def test_plain(self):
        assert extract_ip_from_text("10.3.2.94") == "10.3.2.94"

    def test_with_leading_zeros(self):
        assert extract_ip_from_text("010.003.002.094") == "10.3.2.94"

    def test_in_unc_path(self):
        assert extract_ip_from_text(r"\\10.3.2.94\printer") == "10.3.2.94"

    def test_in_url(self):
        assert extract_ip_from_text("http://10.3.2.94:8080") == "10.3.2.94"

    def test_with_spaces_around_dots(self):
        assert extract_ip_from_text("10 . 3 . 2 . 94") == "10.3.2.94"

    def test_with_prefix(self):
        assert extract_ip_from_text("IP: 10.3.2.94") == "10.3.2.94"

    def test_multiple_ips_returns_first(self):
        assert extract_ip_from_text("10.3.2.94 и 192.168.1.1") == "10.3.2.94"

    def test_invalid_octet_returns_none(self):
        assert extract_ip_from_text("10.3.2.999") is None

    def test_no_ip(self):
        assert extract_ip_from_text("нет тут ip") is None

    def test_empty(self):
        assert extract_ip_from_text("") is None

    def test_none(self):
        assert extract_ip_from_text(None) is None


# =========================================================
# normalize_ip
# =========================================================
class TestNormalizeIp:

    def test_plain(self):
        assert normalize_ip("10.3.2.94") == "10.3.2.94"

    def test_with_zeros(self):
        assert normalize_ip("010.003.002.094") == "10.3.2.94"

    def test_invalid(self):
        assert normalize_ip("not an ip") == ""

    def test_empty(self):
        assert normalize_ip("") == ""

    def test_none(self):
        assert normalize_ip(None) == ""


# =========================================================
# is_valid_ip
# =========================================================
class TestIsValidIp:

    def test_valid(self):
        assert is_valid_ip("10.3.2.94") is True
        assert is_valid_ip("0.0.0.0") is True
        assert is_valid_ip("255.255.255.255") is True

    def test_too_many_parts(self):
        assert is_valid_ip("10.3.2.94.1") is False

    def test_too_few_parts(self):
        assert is_valid_ip("10.3.2") is False

    def test_out_of_range(self):
        assert is_valid_ip("10.3.2.256") is False
        assert is_valid_ip("256.0.0.1") is False

    def test_negative(self):
        assert is_valid_ip("-1.0.0.0") is False

    def test_not_a_number(self):
        assert is_valid_ip("abc.def.ghi.jkl") is False

    def test_empty(self):
        assert is_valid_ip("") is False

    def test_none(self):
        assert is_valid_ip(None) is False


# =========================================================
# ping_host (замокан subprocess)
# =========================================================
class TestPingHost:

    def test_success_with_time(self, monkeypatch):
        class FakeResult:
            returncode = 0
            stdout = "Ответ от 10.3.2.94: число байт=32 время=5мс TTL=64"
            stderr = ""

        monkeypatch.setattr(
            network_utils.subprocess, "run",
            lambda *a, **kw: FakeResult()
        )

        ok, info = ping_host("10.3.2.94")
        assert ok is True
        assert "5 мс" in info

    def test_success_without_time(self, monkeypatch):
        class FakeResult:
            returncode = 0
            stdout = "Ответ от 10.3.2.94: TTL=64"
            stderr = ""

        monkeypatch.setattr(
            network_utils.subprocess, "run",
            lambda *a, **kw: FakeResult()
        )

        ok, info = ping_host("10.3.2.94")
        assert ok is True
        assert info == "доступен"

    def test_no_response(self, monkeypatch):
        class FakeResult:
            returncode = 1
            stdout = "Превышен интервал ожидания для запроса."
            stderr = ""

        monkeypatch.setattr(
            network_utils.subprocess, "run",
            lambda *a, **kw: FakeResult()
        )

        ok, info = ping_host("10.3.2.94")
        assert ok is False
        assert info == "нет ответа"

    def test_timeout(self, monkeypatch):
        def fake_run(*a, **kw):
            raise subprocess.TimeoutExpired("ping", 3)

        monkeypatch.setattr(network_utils.subprocess, "run", fake_run)

        ok, info = ping_host("10.3.2.94")
        assert ok is False
        assert info == "таймаут"

    def test_exception(self, monkeypatch):
        def fake_run(*a, **kw):
            raise Exception("boom")

        monkeypatch.setattr(network_utils.subprocess, "run", fake_run)

        ok, info = ping_host("10.3.2.94")
        assert ok is False
        assert "boom" in info


# =========================================================
# check_printer_port (замокан socket)
# =========================================================
class TestCheckPrinterPort:

    def test_port_open(self, monkeypatch):
        class FakeSocket:
            def __init__(self, *a, **kw): pass
            def settimeout(self, t): pass
            def connect_ex(self, addr):
                # Открыт первый порт из списка
                return 0 if addr[1] == PRINTER_PORTS[0] else 1
            def close(self): pass

        monkeypatch.setattr(network_utils.socket, "socket", FakeSocket)

        ok, port = check_printer_port("10.3.2.94")
        assert ok is True
        assert port == PRINTER_PORTS[0]

    def test_all_ports_closed(self, monkeypatch):
        class FakeSocket:
            def __init__(self, *a, **kw): pass
            def settimeout(self, t): pass
            def connect_ex(self, addr): return 1
            def close(self): pass

        monkeypatch.setattr(network_utils.socket, "socket", FakeSocket)

        ok, port = check_printer_port("10.3.2.94")
        assert ok is False
        assert port is None

    def test_exception_continues(self, monkeypatch):
        class FakeSocket:
            def __init__(self, *a, **kw): pass
            def settimeout(self, t): pass
            def connect_ex(self, addr):
                raise Exception("boom")
            def close(self): pass

        monkeypatch.setattr(network_utils.socket, "socket", FakeSocket)

        ok, port = check_printer_port("10.3.2.94")
        assert ok is False
        assert port is None


# =========================================================
# check_host (комбинация)
# =========================================================
class TestCheckHost:

    def test_online_by_port(self, monkeypatch):
        monkeypatch.setattr(
            network_utils, "check_printer_port",
            lambda host, timeout=2: (True, 9100)
        )
        monkeypatch.setattr(
            network_utils, "ping_host",
            lambda host, timeout=3: (False, "нет ответа")
        )

        result = check_host("10.3.2.94")
        assert result["online"] is True
        assert result["port"] == 9100

    def test_online_by_ping(self, monkeypatch):
        monkeypatch.setattr(
            network_utils, "check_printer_port",
            lambda host, timeout=2: (False, None)
        )
        monkeypatch.setattr(
            network_utils, "ping_host",
            lambda host, timeout=3: (True, "5 мс")
        )

        result = check_host("10.3.2.94")
        assert result["online"] is True
        assert result["ping_ok"] is True
        assert result["ping_info"] == "5 мс"

    def test_offline(self, monkeypatch):
        monkeypatch.setattr(
            network_utils, "check_printer_port",
            lambda host, timeout=2: (False, None)
        )
        monkeypatch.setattr(
            network_utils, "ping_host",
            lambda host, timeout=3: (False, "нет ответа")
        )

        result = check_host("10.3.2.94")
        assert result["online"] is False
        assert result["port"] is None