# tests/test_terminal_helper.py
"""
Тесты для core/terminal_helper.py.

Проверяем:
- Шифрование/дешифрование пароля (обратимость, устойчивость к мусору).
- Генерацию ключа.
- Формирование цели подключения (build_target).
- Поиск ГМ (resolve_gm) по коду, названию, IP, шаблону, частичному вхождению.
- Извлечение списка названий для QCompleter (get_gm_names).
"""
import pytest

from core.terminal_helper import (
    xor_encrypt, xor_decrypt, get_password_key,
    build_target, resolve_gm, get_gm_names,
)


# =========================================================
# ШИФРОВАНИЕ ПАРОЛЯ
# =========================================================
class TestXorEncryptDecrypt:

    def test_encrypt_decrypt_roundtrip(self):
        key = "test_key_12345"
        password = "MySuperSecretPassword!@#"
        token = xor_encrypt(password, key)
        decrypted = xor_decrypt(token, key)
        assert decrypted == password

    def test_encrypt_produces_base64(self):
        key = "key"
        token = xor_encrypt("hello", key)
        # base64-строка состоит из ASCII-символов
        assert isinstance(token, str)
        assert all(ord(c) < 128 for c in token)

    def test_encrypt_different_passwords_different_tokens(self):
        key = "key"
        t1 = xor_encrypt("password1", key)
        t2 = xor_encrypt("password2", key)
        assert t1 != t2

    def test_decrypt_with_wrong_key_returns_empty(self):
        key1 = "key1"
        key2 = "key2"
        token = xor_encrypt("secret", key1)
        result = xor_decrypt(token, key2)
        # Либо пустая строка, либо мусор — главное, не исходный пароль
        assert result != "secret"

    def test_decrypt_garbage_returns_empty(self):
        assert xor_decrypt("not_base64!!!", "key") == ""

    def test_decrypt_empty_string_returns_empty(self):
        assert xor_decrypt("", "key") == ""


# =========================================================
# КЛЮЧ ШИФРОВАНИЯ
# =========================================================
class TestPasswordKey:

    def test_key_is_string(self):
        key = get_password_key()
        assert isinstance(key, str)
        assert len(key) > 0

    def test_key_length_32(self):
        key = get_password_key()
        assert len(key) == 32

    def test_key_is_stable(self):
        # В рамках одного процесса ключ должен быть одинаковым
        assert get_password_key() == get_password_key()


# =========================================================
# ФОРМИРОВАНИЕ ЦЕЛИ
# =========================================================
class TestBuildTarget:

    def test_simple_code(self):
        assert build_target("996411") == "S996411term"

    def test_code_with_spaces(self):
        assert build_target("  996411  ") == "S996411term"

    def test_already_wrapped(self):
        assert build_target("S996411term") == "S996411term"

    def test_already_wrapped_lowercase(self):
        assert build_target("s996411term") == "s996411term"

    def test_empty_code(self):
        assert build_target("") == ""

    def test_whitespace_only(self):
        assert build_target("   ") == ""


# =========================================================
# ПОИСК ГМ
# =========================================================
@pytest.fixture
def gm_data():
    return [
        {"Код": "996411", "Название": "Балаково 3 Саратовское шоссе",
         "Папка": "\\\\10.4.80.3\\krs_gm"},
        {"Код": "992320", "Название": "Абинск 1 Колхозная",
         "Папка": "\\\\10.2.68.3\\krs_gm"},
        {"Код": "997103", "Название": "Алексин 1 Дубравная",
         "Папка": "\\\\10.2.130.3\\krs_gm"},
    ]


class TestResolveGm:

    def test_by_exact_code(self, gm_data):
        result = resolve_gm("996411", gm_data)
        assert result is not None
        assert result["Код"] == "996411"

    def test_by_exact_name(self, gm_data):
        result = resolve_gm("Балаково 3 Саратовское шоссе", gm_data)
        assert result is not None
        assert result["Код"] == "996411"

    def test_by_name_case_insensitive(self, gm_data):
        result = resolve_gm("балаково 3 саратовское шоссе", gm_data)
        assert result is not None
        assert result["Код"] == "996411"

    def test_by_ip(self, gm_data):
        result = resolve_gm("10.4.80.3", gm_data)
        assert result is not None
        assert result["Код"] == "996411"

    def test_by_partial_name(self, gm_data):
        result = resolve_gm("Балаково", gm_data)
        assert result is not None
        assert result["Код"] == "996411"

    def test_by_partial_name_case_insensitive(self, gm_data):
        result = resolve_gm("балаково", gm_data)
        assert result is not None
        assert result["Код"] == "996411"

    def test_by_s_term_pattern(self, gm_data):
        result = resolve_gm("S996411term", gm_data)
        assert result is not None
        assert result["Код"] == "S996411term"

    def test_not_found(self, gm_data):
        assert resolve_gm("Несуществующий ГМ", gm_data) is None

    def test_empty_string(self, gm_data):
        assert resolve_gm("", gm_data) is None

    def test_whitespace_only(self, gm_data):
        assert resolve_gm("   ", gm_data) is None

    def test_empty_gm_data(self):
        assert resolve_gm("996411", []) is None

    def test_code_priority_over_name(self):
        # Если код одного ГМ совпадает с названием другого — приоритет у кода
        data = [
            {"Код": "123", "Название": "ГМ А", "Папка": "\\\\1.1.1.1\\"},
            {"Код": "456", "Название": "123", "Папка": "\\\\2.2.2.2\\"},
        ]
        result = resolve_gm("123", data)
        assert result["Код"] == "123"


# =========================================================
# СПИСОК НАЗВАНИЙ
# =========================================================
class TestGetGmNames:

    def test_returns_names(self, gm_data):
        names = get_gm_names(gm_data)
        assert "Балаково 3 Саратовское шоссе" in names
        assert "Абинск 1 Колхозная" in names
        assert "Алексин 1 Дубравная" in names

    def test_skips_empty_names(self):
        data = [
            {"Код": "1", "Название": "ГМ А"},
            {"Код": "2", "Название": ""},
            {"Код": "3", "Название": "   "},
            {"Код": "4"},  # нет ключа «Название»
        ]
        names = get_gm_names(data)
        assert names == ["ГМ А"]

    def test_empty_data(self):
        assert get_gm_names([]) == []

    def test_returns_only_names(self, gm_data):
        names = get_gm_names(gm_data)
        for name in names:
            # В названии не должно быть технических символов из «Код» или «Папка»
            assert "\\\\" not in name
            assert not name.isdigit()