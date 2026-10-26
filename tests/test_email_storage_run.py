# tests/test_email_storage_run.py
"""
Тесты для core/email_storage.py.

DataManager мокается in-memory — без файлов.
"""
from datetime import datetime

import pytest

from core.email_storage import (
    make_key,
    _find_index,
    add_to_archive,
    save_email,
    get_email,
    get_emails_by_gm,
    get_emails_by_date_range,
    get_unique_gm_codes,
    count_emails,
    clear_all,
    load_emails,
    load_archive,
)


# =========================================================
# FAKE DATA MANAGER
# =========================================================
class FakeDataManager:
    """In-memory замена DataManager для тестов."""

    def __init__(self):
        self._emails = []
        self._archive = []

    def get_emails(self):
        return list(self._emails)

    def set_emails(self, emails):
        self._emails = list(emails)

    def get_inventory_archive(self):
        return list(self._archive)

    def set_inventory_archive(self, archive):
        self._archive = list(archive)


@pytest.fixture
def fake_dm(monkeypatch):
    """Подменяет get_data_manager на in-memory объект."""
    dm = FakeDataManager()
    monkeypatch.setattr(
        "core.email_storage.get_data_manager",
        lambda: dm,
    )
    return dm


# =========================================================
# make_key
# =========================================================
class TestMakeKey:
    def test_simple(self):
        assert make_key("996414", "04.10.2026") == "996414_04.10.2026"

    def test_empty(self):
        assert make_key("", "") == "_"


# =========================================================
# _find_index
# =========================================================
class TestFindIndex:
    def test_found(self):
        emails = [
            {"gm_code": "111", "report_date": "01.01.2026"},
            {"gm_code": "222", "report_date": "02.01.2026"},
        ]
        assert _find_index(emails, "222", "02.01.2026") == 1

    def test_not_found(self):
        emails = [{"gm_code": "111", "report_date": "01.01.2026"}]
        assert _find_index(emails, "999", "01.01.2026") is None

    def test_empty(self):
        assert _find_index([], "111", "01.01.2026") is None


# =========================================================
# load_emails / load_archive
# =========================================================
class TestLoad:
    def test_load_emails_empty(self, fake_dm):
        assert load_emails() == []

    def test_load_emails_with_data(self, fake_dm):
        fake_dm.set_emails([{"gm_code": "111"}])
        result = load_emails()
        assert len(result) == 1

    def test_load_emails_not_list(self, fake_dm, monkeypatch):
        # Патчим get_emails, чтобы вернул dict
        monkeypatch.setattr(fake_dm, "get_emails", lambda: {"bad": "data"})
        result = load_emails()
        assert result == []

    def test_load_archive_empty(self, fake_dm):
        assert load_archive() == []

    def test_load_archive_with_data(self, fake_dm):
        fake_dm.set_inventory_archive([{"gm_code": "111"}])
        result = load_archive()
        assert len(result) == 1


# =========================================================
# save_email
# =========================================================
class TestSaveEmail:
    def test_save_new(self, fake_dm):
        parsed = {
            "gm_code": "111",
            "report_date": "01.01.2026",
            "gm_name": "Test GM",
        }
        result = save_email(parsed)

        assert result["saved"] is True
        assert result["overwritten"] is False
        assert result["key"] == "111_01.01.2026"
        assert len(fake_dm.get_emails()) == 1

    def test_save_duplicate_skipped(self, fake_dm):
        parsed = {"gm_code": "111", "report_date": "01.01.2026"}
        save_email(parsed)
        result = save_email(parsed)

        assert result["saved"] is False
        assert result["reason"] == "duplicate"
        assert len(fake_dm.get_emails()) == 1

    def test_save_duplicate_overwrite(self, fake_dm):
        parsed1 = {"gm_code": "111", "report_date": "01.01.2026", "v": 1}
        parsed2 = {"gm_code": "111", "report_date": "01.01.2026", "v": 2}
        save_email(parsed1)
        result = save_email(parsed2, overwrite=True)

        assert result["saved"] is True
        assert result["overwritten"] is True
        emails = fake_dm.get_emails()
        assert emails[0]["v"] == 2

    def test_save_no_gm_code(self, fake_dm):
        parsed = {"report_date": "01.01.2026"}
        result = save_email(parsed)

        assert result["saved"] is False
        assert result["reason"] == "no_gm_code_or_report_date"

    def test_save_no_report_date(self, fake_dm):
        parsed = {"gm_code": "111"}
        result = save_email(parsed)

        assert result["saved"] is False

    def test_save_with_raw(self, fake_dm):
        parsed = {"gm_code": "111", "report_date": "01.01.2026"}
        save_email(parsed, raw_subject="Subj", raw_body="Body")

        emails = fake_dm.get_emails()
        assert emails[0]["raw_subject"] == "Subj"
        assert emails[0]["raw_body"] == "Body"

    def test_save_sorted_by_date_desc(self, fake_dm):
        save_email({"gm_code": "111", "report_date": "01.01.2026"})
        save_email({"gm_code": "222", "report_date": "03.01.2026"})
        save_email({"gm_code": "333", "report_date": "02.01.2026"})

        emails = fake_dm.get_emails()
        dates = [e["report_date"] for e in emails]
        assert dates == ["03.01.2026", "02.01.2026", "01.01.2026"]


# =========================================================
# save_email + is_final → add_to_archive
# =========================================================
class TestSaveFinal:
    def test_final_triggers_archive(self, fake_dm):
        parsed = {
            "gm_code": "111",
            "report_date": "01.01.2026",
            "is_final": True,
            "start_date": "01.01.2026",
            "end_date": "05.01.2026",
            "final_totals": {
                "with_rm": {"deficit": 100},
                "without_rm": {"deficit": 50},
            },
        }
        save_email(parsed)

        archive = fake_dm.get_inventory_archive()
        assert len(archive) == 1
        assert archive[0]["gm_code"] == "111"

    def test_duplicate_final_still_archives(self, fake_dm):
        """Дубликат финального письма всё равно вызывает add_to_archive."""
        parsed = {
            "gm_code": "111",
            "report_date": "01.01.2026",
            "is_final": True,
            "start_date": "01.01.2026",
        }
        save_email(parsed)
        fake_dm.set_inventory_archive([])  # симулируем очистку архива

        result = save_email(parsed)
        assert result["saved"] is False
        # Архив восстановился
        assert len(fake_dm.get_inventory_archive()) == 1


# =========================================================
# add_to_archive
# =========================================================
class TestAddToArchive:
    def test_create_new(self, fake_dm):
        parsed = {
            "gm_code": "111",
            "gm_name": "Test",
            "start_date": "01.01.2026",
            "end_date": "05.01.2026",
            "final_totals": {"with_rm": {}, "without_rm": {}},
        }
        result = add_to_archive(parsed)

        assert result["created"] is True
        assert result["updated"] is False
        assert result["gm_code"] == "111"

    def test_update_existing(self, fake_dm):
        parsed = {
            "gm_code": "111",
            "start_date": "01.01.2026",
            "final_totals": {},
        }
        add_to_archive(parsed)

        # Обновляем
        parsed["gm_name"] = "Updated"
        result = add_to_archive(parsed)

        assert result["created"] is False
        assert result["updated"] is True
        archive = fake_dm.get_inventory_archive()
        assert archive[0]["gm_name"] == "Updated"

    def test_no_gm_code(self, fake_dm):
        result = add_to_archive({})
        assert result["created"] is False
        assert result["gm_code"] == ""


# =========================================================
# get_email / get_emails_by_gm
# =========================================================
class TestGet:
    def test_get_email(self, fake_dm):
        save_email({"gm_code": "111", "report_date": "01.01.2026", "v": 1})
        result = get_email("111", "01.01.2026")
        assert result is not None
        assert result["v"] == 1

    def test_get_email_not_found(self, fake_dm):
        assert get_email("999", "01.01.2026") is None

    def test_get_emails_by_gm(self, fake_dm):
        save_email({"gm_code": "111", "report_date": "01.01.2026"})
        save_email({"gm_code": "222", "report_date": "02.01.2026"})
        save_email({"gm_code": "111", "report_date": "03.01.2026"})

        result = get_emails_by_gm("111")
        assert len(result) == 2


# =========================================================
# get_emails_by_date_range
# =========================================================
class TestDateRange:
    def test_range(self, fake_dm):
        save_email({"gm_code": "111", "report_date": "01.01.2026"})
        save_email({"gm_code": "222", "report_date": "05.01.2026"})
        save_email({"gm_code": "333", "report_date": "10.01.2026"})

        result = get_emails_by_date_range("02.01.2026", "06.01.2026")
        assert len(result) == 1
        assert result[0]["gm_code"] == "222"

    def test_only_from(self, fake_dm):
        save_email({"gm_code": "111", "report_date": "01.01.2026"})
        save_email({"gm_code": "222", "report_date": "10.01.2026"})

        result = get_emails_by_date_range(date_from="05.01.2026")
        assert len(result) == 1

    def test_only_to(self, fake_dm):
        save_email({"gm_code": "111", "report_date": "01.01.2026"})
        save_email({"gm_code": "222", "report_date": "10.01.2026"})

        result = get_emails_by_date_range(date_to="05.01.2026")
        assert len(result) == 1

    def test_with_gm_filter(self, fake_dm):
        save_email({"gm_code": "111", "report_date": "01.01.2026"})
        save_email({"gm_code": "222", "report_date": "02.01.2026"})

        result = get_emails_by_date_range(
            date_from="01.01.2026",
            date_to="31.01.2026",
            gm_code="222",
        )
        assert len(result) == 1


# =========================================================
# get_unique_gm_codes / count_emails / clear_all
# =========================================================
class TestMisc:
    def test_unique_gm_codes(self, fake_dm):
        save_email({"gm_code": "111", "report_date": "01.01.2026"})
        save_email({"gm_code": "222", "report_date": "02.01.2026"})
        save_email({"gm_code": "111", "report_date": "03.01.2026"})

        codes = get_unique_gm_codes()
        assert codes == ["111", "222"]

    def test_count_emails(self, fake_dm):
        assert count_emails() == 0

        save_email({"gm_code": "111", "report_date": "01.01.2026"})
        save_email({"gm_code": "222", "report_date": "02.01.2026"})

        assert count_emails() == 2

    def test_clear_all(self, fake_dm):
        save_email({"gm_code": "111", "report_date": "01.01.2026"})
        assert count_emails() == 1

        clear_all()
        assert count_emails() == 0