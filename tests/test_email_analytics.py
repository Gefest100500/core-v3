# tests/test_email_analytics.py
"""
Тесты для core/email_analytics.py.

Покрываем:
- _normalize_label_text: кавычки, регистр, пробелы
- extract_zone: порядок маркеров, кавычки, перепроверка
- _normalize_label: перепроверка с комментарием
- _extract_grand_total: приоритет final_totals, знак
- _parse_ddmmyyyy / _date_in_range
- short_label
- get_zone_color
- get_filtered_emails / get_last_email / get_last_email_with_events
- get_daily_emails / get_final_emails — разделение по is_final
- split_events / top_zones / top_other_events
- time_total / not_started
- summary / summary_prev / summary_history
- summary с финальным письмом

Все интеграционные тесты работают через monkeypatch на load_emails,
чтобы не зависеть от реального emails.json.
"""
import pytest

from core import email_analytics as ea


# =========================================================
# ФИКСТУРЫ
# =========================================================
@pytest.fixture
def fake_emails(monkeypatch):
    """Подменяет load_emails() на возврат тестового списка.

    Используется как фабрика:
        fake_emails([...])
    Возвращает список, чтобы можно было проверить его в тесте.
    """
    def _install(emails):
        monkeypatch.setattr(ea, "load_emails", lambda: emails)
        return emails
    return _install


@pytest.fixture
def empty_emails(fake_emails):
    """Пустой список писем."""
    return fake_emails([])


# =========================================================
# ХЕЛПЕР
# =========================================================
def _make_email(gm_code="996414", gm_name="Балашов 1",
                report_date="04.10.2026", events=None,
                final_amount=None, cum_amount=None,
                is_final=False):
    """Сборка тестового письма.

    is_final=True помечает письмо как финальное:
    оно попадёт в get_final_emails(), но НЕ в get_daily_emails().
    """
    email = {
        "gm_code": gm_code,
        "gm_name": gm_name,
        "report_date": report_date,
        "events": events or [],
        "time_log": [],
        "is_final": is_final,
    }
    if final_amount is not None:
        email["final_totals"] = {
            "with_rm": {"amount": final_amount, "type": "недостачей"},
        }
    if cum_amount is not None:
        email["totals"] = {
            "cumulative_with_rm": {"amount": cum_amount, "type": "недостачей"},
        }
    return email


# =========================================================
# _normalize_label_text
# =========================================================
class TestNormalizeLabelText:
    def test_lowercase(self):
        assert ea._normalize_label_text("АЛКОГОЛЬ") == "алкоголь"

    def test_strip_double_quotes(self):
        assert ea._normalize_label_text('Алкоголь" НД') == "алкоголь нд"

    def test_strip_guillemets(self):
        assert ea._normalize_label_text("«Алкоголь» НД") == "алкоголь нд"

    def test_strip_single_quotes(self):
        assert ea._normalize_label_text("'Алкоголь' НД") == "алкоголь нд"

    def test_strip_typographic_quotes(self):
        assert ea._normalize_label_text("“Алкоголь” НД") == "алкоголь нд"

    def test_strip_backtick(self):
        assert ea._normalize_label_text("`Алкоголь`") == "алкоголь"

    def test_collapse_spaces(self):
        assert ea._normalize_label_text("Алкоголь    НД") == "алкоголь нд"

    def test_strip_newlines_and_tabs(self):
        assert ea._normalize_label_text("Алкоголь\n\tНД") == "алкоголь нд"

    def test_empty(self):
        assert ea._normalize_label_text("") == ""

    def test_none(self):
        assert ea._normalize_label_text(None) == ""


# =========================================================
# extract_zone
# =========================================================
class TestExtractZone:
    def test_alcohol_nd_priority(self):
        """«Алкоголь НД» должно срабатывать раньше «Алкоголь»."""
        assert ea.extract_zone("Инвентаризация зоны Алкоголь НД") == "Алкоголь НД"

    def test_alcohol_nd_with_double_quote(self):
        """Баг: «Алкоголь\" НД» раньше схлопывалось в «Алкоголь»."""
        assert ea.extract_zone('Инвентаризация зоны "Алкоголь" НД') == "Алкоголь НД"

    def test_alcohol_nd_with_guillemets(self):
        assert ea.extract_zone("Инвентаризация зоны «Алкоголь НД»") == "Алкоголь НД"

    def test_alcohol_plain(self):
        assert ea.extract_zone("Инвентаризация зоны Алкоголь") == "Алкоголь"

    def test_cosmetics_and_household(self):
        assert ea.extract_zone("Косметика и Бытовая химия") == \
            "Косметика и Бытовая химия"

    def test_cosmetics_short(self):
        assert ea.extract_zone("Инвентаризация зоны Косметика") == \
            "Косметика и Бытовая химия"

    def test_household_short(self):
        assert ea.extract_zone("Инвентаризация Бытовая химия") == \
            "Косметика и Бытовая химия"

    def test_frozen_canonical(self):
        assert ea.extract_zone("Замороженная продукция") == "Заморозка"

    def test_frozen_short(self):
        assert ea.extract_zone("Инвентаризация Заморозка") == "Заморозка"

    def test_chilled_canonical(self):
        assert ea.extract_zone("Охлажденная продукция") == "Охлажденка"

    def test_chilled_short(self):
        assert ea.extract_zone("Охлажденка") == "Охлажденка"

    def test_tobacco_canonical(self):
        assert ea.extract_zone("Табачные изделия") == "Сигареты"

    def test_tobacco_short(self):
        assert ea.extract_zone("Сигареты") == "Сигареты"

    def test_simple_zones(self):
        assert ea.extract_zone("Весовые конфеты") == "Весовые конфеты"
        assert ea.extract_zone("Непрофиль") == "Непрофиль"
        assert ea.extract_zone("Продукты") == "Продукты"
        assert ea.extract_zone("Фреш") == "Фреш"

    def test_case_insensitive(self):
        assert ea.extract_zone("алкоголь") == "Алкоголь"

    def test_perepproverka_returns_none(self):
        """Перепроверка — не зона, отдельное мероприятие."""
        assert ea.extract_zone("Перепроверка расхождений") is None

    def test_perepproverka_with_zone_still_none(self):
        """Даже с указанной зоной — это НЕ зона."""
        assert ea.extract_zone("Перепроверка: Заморозка") is None

    def test_unknown_label(self):
        assert ea.extract_zone("Что-то неизвестное") is None

    def test_empty(self):
        assert ea.extract_zone("") is None

    def test_none(self):
        assert ea.extract_zone(None) is None


# =========================================================
# _normalize_label
# =========================================================
class TestNormalizeLabel:
    def test_regular_label_untouched(self):
        assert ea._normalize_label("Алкоголь", "") == "Алкоголь"

    def test_perepproverka_with_zone(self):
        result = ea._normalize_label(
            "Перепроверка расхождений",
            "Перепроверка: Заморозка",
        )
        assert result == "Перепроверка расхождений (Заморозка)"

    def test_perepproverka_no_zone_in_comment(self):
        result = ea._normalize_label(
            "Перепроверка расхождений",
            "перепроверка",
        )
        assert result == "Перепроверка расхождений"

    def test_perepproverka_empty_comment(self):
        result = ea._normalize_label("Перепроверка расхождений", "")
        assert result == "Перепроверка расхождений"

    def test_perepproverka_case_insensitive(self):
        result = ea._normalize_label(
            "Перепроверка расхождений",
            "ПЕРЕПРОВЕРКА: Сигареты",
        )
        assert result == "Перепроверка расхождений (Сигареты)"

    def test_none_label(self):
        assert ea._normalize_label(None, "что-то") is None


# =========================================================
# _extract_grand_total
# =========================================================
class TestExtractGrandTotal:
    def test_empty_email(self):
        assert ea._extract_grand_total({}) == 0.0

    def test_none_email(self):
        assert ea._extract_grand_total(None) == 0.0

    def test_final_totals_priority(self):
        """final_totals.with_rm приоритетнее totals.cumulative_with_rm."""
        email = {
            "final_totals": {
                "with_rm": {"amount": 1000.0, "type": "недостачей"},
            },
            "totals": {
                "cumulative_with_rm": {"amount": 999.0, "type": "недостачей"},
            },
        }
        assert ea._extract_grand_total(email) == 1000.0

    def test_final_deficit_positive(self):
        email = {
            "final_totals": {
                "with_rm": {"amount": 1898372.72, "type": "недостачей"},
            },
        }
        assert ea._extract_grand_total(email) == 1898372.72

    def test_final_surplus_negative(self):
        email = {
            "final_totals": {
                "with_rm": {"amount": 100.0, "type": "излишком"},
            },
        }
        assert ea._extract_grand_total(email) == -100.0

    def test_final_surplus_already_negative(self):
        """Если amount отрицательный и тип «излишком» — оставляем -abs()."""
        email = {
            "final_totals": {
                "with_rm": {"amount": -50.0, "type": "излишком"},
            },
        }
        assert ea._extract_grand_total(email) == -50.0

    def test_cumulative_deficit(self):
        email = {
            "totals": {
                "cumulative_with_rm": {"amount": 129186.0, "type": "недостачей"},
            },
        }
        assert ea._extract_grand_total(email) == 129186.0

    def test_cumulative_surplus(self):
        email = {
            "totals": {
                "cumulative_with_rm": {"amount": 300.0, "type": "излишком"},
            },
        }
        assert ea._extract_grand_total(email) == -300.0

    def test_amount_invalid_string(self):
        email = {
            "final_totals": {
                "with_rm": {"amount": "не число", "type": "недостачей"},
            },
        }
        assert ea._extract_grand_total(email) == 0.0

    def test_amount_missing(self):
        email = {"final_totals": {"with_rm": {}}}
        assert ea._extract_grand_total(email) == 0.0


# =========================================================
# _parse_ddmmyyyy / _date_in_range
# =========================================================
class TestParseDdmmyyyy:
    def test_valid(self):
        from datetime import datetime
        assert ea._parse_ddmmyyyy("17.09.2026") == datetime(2026, 9, 17)

    def test_invalid(self):
        assert ea._parse_ddmmyyyy("2026-09-17") is None

    def test_empty(self):
        assert ea._parse_ddmmyyyy("") is None

    def test_none(self):
        assert ea._parse_ddmmyyyy(None) is None


class TestDateInRange:
    def test_inside_range(self):
        assert ea._date_in_range("15.09.2026", "10.09.2026", "20.09.2026")

    def test_on_lower_boundary(self):
        assert ea._date_in_range("10.09.2026", "10.09.2026", "20.09.2026")

    def test_on_upper_boundary(self):
        assert ea._date_in_range("20.09.2026", "10.09.2026", "20.09.2026")

    def test_before_range(self):
        assert not ea._date_in_range("01.09.2026", "10.09.2026", "20.09.2026")

    def test_after_range(self):
        assert not ea._date_in_range("25.09.2026", "10.09.2026", "20.09.2026")

    def test_no_bounds(self):
        assert ea._date_in_range("15.09.2026", None, None)

    def test_only_from(self):
        assert ea._date_in_range("15.09.2026", "10.09.2026", None)
        assert not ea._date_in_range("05.09.2026", "10.09.2026", None)

    def test_only_to(self):
        assert ea._date_in_range("15.09.2026", None, "20.09.2026")
        assert not ea._date_in_range("25.09.2026", None, "20.09.2026")

    def test_invalid_date_returns_false(self):
        assert not ea._date_in_range("garbage", "10.09.2026", "20.09.2026")

    def test_empty_date_returns_false(self):
        assert not ea._date_in_range("", None, None)


# =========================================================
# short_label
# =========================================================
class TestShortLabel:
    def test_simple(self):
        assert ea.short_label("Инвентаризация зоны Алкоголь") == \
            "Инвентаризация зоны Алкоголь"

    def test_cuts_at_comma(self):
        assert ea.short_label("Инвентаризация, зоны Алкоголь") == \
            "Инвентаризация"

    def test_truncates_long(self):
        result = ea.short_label("a" * 100, max_len=10)
        assert result == "a" * 10 + "…"

    def test_empty(self):
        assert ea.short_label("") == ""

    def test_none(self):
        assert ea.short_label(None) == ""

    def test_strip(self):
        assert ea.short_label("  Алкоголь  ") == "Алкоголь"


# =========================================================
# get_zone_color
# =========================================================
class TestGetZoneColor:
    def test_deterministic(self):
        assert ea.get_zone_color("Алкоголь") == ea.get_zone_color("Алкоголь")

    def test_empty_returns_first(self):
        assert ea.get_zone_color("") == ea.ZONE_COLORS[0]

    def test_none_returns_first(self):
        assert ea.get_zone_color(None) == ea.ZONE_COLORS[0]

    def test_returns_valid_color(self):
        assert ea.get_zone_color("Заморозка") in ea.ZONE_COLORS

    def test_different_zones_may_differ(self):
        """Не гарантия, но проверяем, что хэш работает."""
        colors = {ea.get_zone_color(z) for z in ea.ZONES_CANONICAL}
        assert len(colors) > 1


# =========================================================
# get_filtered_emails / get_last_email / get_last_email_with_events
# =========================================================
class TestGetFilteredEmails:
    def test_filters_by_gm_code(self, fake_emails):
        fake_emails([
            _make_email(gm_code="111"),
            _make_email(gm_code="222"),
            _make_email(gm_code="111"),
        ])
        result = ea.get_filtered_emails(gm_code="111")
        assert len(result) == 2
        assert all(e["gm_code"] == "111" for e in result)

    def test_filters_by_date_range(self, fake_emails):
        fake_emails([
            _make_email(report_date="01.10.2026"),
            _make_email(report_date="15.10.2026"),
            _make_email(report_date="25.10.2026"),
        ])
        result = ea.get_filtered_emails(
            date_from="10.10.2026", date_to="20.10.2026"
        )
        assert len(result) == 1
        assert result[0]["report_date"] == "15.10.2026"

    def test_sorted_by_date(self, fake_emails):
        fake_emails([
            _make_email(report_date="15.10.2026"),
            _make_email(report_date="01.10.2026"),
            _make_email(report_date="10.10.2026"),
        ])
        result = ea.get_filtered_emails()
        dates = [e["report_date"] for e in result]
        assert dates == sorted(dates)

    def test_empty(self, empty_emails):
        assert ea.get_filtered_emails() == []


class TestGetLastEmail:
    def test_returns_last(self, fake_emails):
        fake_emails([
            _make_email(report_date="01.10.2026"),
            _make_email(report_date="05.10.2026"),
            _make_email(report_date="03.10.2026"),
        ])
        result = ea.get_last_email()
        assert result["report_date"] == "05.10.2026"

    def test_empty_returns_none(self, empty_emails):
        assert ea.get_last_email() is None


class TestGetLastEmailWithEvents:
    def test_skips_final_with_empty_events(self, fake_emails):
        fake_emails([
            _make_email(
                report_date="01.10.2026",
                events=[{"label": "A", "amount": 10}],
            ),
            _make_email(
                report_date="05.10.2026",
                events=[],
                is_final=True,
            ),
        ])
        result = ea.get_last_email_with_events()
        assert result["report_date"] == "01.10.2026"

    def test_returns_last_daily(self, fake_emails):
        fake_emails([
            _make_email(
                report_date="01.10.2026",
                events=[{"label": "A", "amount": 10}],
            ),
            _make_email(
                report_date="03.10.2026",
                events=[{"label": "B", "amount": 20}],
            ),
            _make_email(
                report_date="05.10.2026",
                events=[],
                is_final=True,
            ),
        ])
        result = ea.get_last_email_with_events()
        assert result["report_date"] == "03.10.2026"

    def test_all_empty_events_returns_last(self, fake_emails):
        fake_emails([
            _make_email(report_date="01.10.2026", events=[]),
            _make_email(report_date="05.10.2026", events=[]),
        ])
        result = ea.get_last_email_with_events()
        assert result["report_date"] == "05.10.2026"

    def test_empty_returns_none(self, empty_emails):
        assert ea.get_last_email_with_events() is None


# =========================================================
# РАЗДЕЛЕНИЕ ДНЕВНЫХ И ФИНАЛЬНЫХ
# =========================================================
class TestDailyFinalFiltering:
    def test_get_daily_emails_excludes_final(self, fake_emails):
        fake_emails([
            _make_email(report_date="01.10.2026"),
            _make_email(report_date="02.10.2026"),
            _make_email(report_date="05.10.2026", is_final=True),
        ])
        result = ea.get_daily_emails()
        assert len(result) == 2
        assert all(not e.get("is_final") for e in result)

    def test_get_final_emails_only_final(self, fake_emails):
        fake_emails([
            _make_email(report_date="01.10.2026"),
            _make_email(report_date="02.10.2026"),
            _make_email(report_date="05.10.2026", is_final=True),
        ])
        result = ea.get_final_emails()
        assert len(result) == 1
        assert result[0]["is_final"] is True

    def test_no_final_returns_empty(self, fake_emails):
        fake_emails([
            _make_email(report_date="01.10.2026"),
            _make_email(report_date="02.10.2026"),
        ])
        assert ea.get_final_emails() == []

    def test_all_final_returns_empty_daily(self, fake_emails):
        fake_emails([
            _make_email(report_date="05.10.2026", is_final=True),
        ])
        assert ea.get_daily_emails() == []
        assert len(ea.get_final_emails()) == 1

    def test_missing_is_final_field_treated_as_daily(self, fake_emails):
        """Письма без поля is_final считаются дневными."""
        fake_emails([
            {
                "gm_code": "111",
                "gm_name": "Test",
                "report_date": "01.10.2026",
                "events": [],
                "time_log": [],
                # is_final отсутствует
            },
        ])
        assert len(ea.get_daily_emails()) == 1
        assert ea.get_final_emails() == []

    def test_get_last_daily_email(self, fake_emails):
        fake_emails([
            _make_email(report_date="01.10.2026"),
            _make_email(report_date="03.10.2026"),
            _make_email(report_date="05.10.2026", is_final=True),
        ])
        result = ea.get_last_daily_email()
        assert result["report_date"] == "03.10.2026"

    def test_get_last_daily_email_empty(self, fake_emails):
        fake_emails([
            _make_email(report_date="05.10.2026", is_final=True),
        ])
        assert ea.get_last_daily_email() is None


# =========================================================
# split_events
# =========================================================
class TestSplitEvents:
    def test_zones_and_others_separated(self, fake_emails):
        fake_emails([
            _make_email(events=[
                {"label": "Инвентаризация зоны Алкоголь",
                 "amount": 100.0},
                {"label": "Что-то неизвестное",
                 "amount": 50.0},
            ]),
        ])
        result = ea.split_events()
        assert "Алкоголь" in result["zones"]
        assert "Что-то неизвестное" in result["other_events"]

    def test_sign_deficit(self, fake_emails):
        fake_emails([
            _make_email(events=[
                {"label": "Алкоголь", "amount": 100.0},
            ]),
        ])
        zones = ea.split_events()["zones"]
        assert zones["Алкоголь"]["deficit"] == 100.0
        assert zones["Алкоголь"]["surplus"] == 0.0
        assert zones["Алкоголь"]["total"] == 100.0

    def test_sign_surplus(self, fake_emails):
        fake_emails([
            _make_email(events=[
                {"label": "Алкоголь", "amount": -100.0},
            ]),
        ])
        zones = ea.split_events()["zones"]
        assert zones["Алкоголь"]["deficit"] == 0.0
        assert zones["Алкоголь"]["surplus"] == 100.0
        assert zones["Алкоголь"]["total"] == -100.0

    def test_accumulates_same_zone(self, fake_emails):
        fake_emails([
            _make_email(events=[
                {"label": "Алкоголь", "amount": 100.0},
                {"label": "Алкоголь", "amount": 50.0},
                {"label": "Алкоголь", "amount": -30.0},
            ]),
        ])
        zones = ea.split_events()["zones"]
        assert zones["Алкоголь"]["deficit"] == 150.0
        assert zones["Алкоголь"]["surplus"] == 30.0
        assert zones["Алкоголь"]["total"] == 120.0

    def test_perepproverka_goes_to_others(self, fake_emails):
        """Перепроверка: Заморозка — не зона, а other_event."""
        fake_emails([
            _make_email(events=[
                {"label": "Перепроверка расхождений",
                 "comment": "Перепроверка: Заморозка",
                 "amount": 100.0},
            ]),
        ])
        result = ea.split_events()
        assert "Заморозка" not in result["zones"]
        assert "Перепроверка расхождений (Заморозка)" in result["other_events"]

    def test_skips_events_without_amount(self, fake_emails):
        fake_emails([
            _make_email(events=[
                {"label": "Алкоголь", "amount": None},
                {"label": "Заморозка", "amount": 50.0},
            ]),
        ])
        zones = ea.split_events()["zones"]
        assert "Алкоголь" not in zones
        assert "Заморозка" in zones

    def test_skips_events_without_label(self, fake_emails):
        fake_emails([
            _make_email(events=[
                {"label": "", "amount": 100.0},
            ]),
        ])
        result = ea.split_events()
        assert result["zones"] == {}
        assert result["other_events"] == {}

    def test_no_email(self, empty_emails):
        result = ea.split_events()
        assert result == {"zones": {}, "other_events": {}}


# =========================================================
# top_zones / top_other_events
# =========================================================
class TestTopZones:
    def test_returns_all_canonical_zones(self, fake_emails):
        fake_emails([_make_email(events=[])])
        result = ea.top_zones()
        names = [z[0] for z in result]
        assert set(names) == set(ea.ZONES_CANONICAL)

    def test_sorted_by_abs_total(self, fake_emails):
        fake_emails([
            _make_email(events=[
                {"label": "Алкоголь", "amount": 100.0},
                {"label": "Заморозка", "amount": -500.0},
                {"label": "Фреш", "amount": 50.0},
            ]),
        ])
        result = ea.top_zones()
        # Заморозка (|-500|) → Алкоголь (|100|) → Фреш (|50|)
        assert result[0][0] == "Заморозка"
        assert result[1][0] == "Алкоголь"
        assert result[2][0] == "Фреш"

    def test_empty_zones_give_zero(self, fake_emails):
        fake_emails([_make_email(events=[])])
        result = ea.top_zones()
        for name, total, deficit, surplus in result:
            assert total == 0.0
            assert deficit == 0.0
            assert surplus == 0.0


class TestTopOtherEvents:
    def test_sorted_and_limited(self, fake_emails):
        fake_emails([
            _make_email(events=[
                {"label": "Event A", "amount": 100.0},
                {"label": "Event B", "amount": -500.0},
                {"label": "Event C", "amount": 50.0},
            ]),
        ])
        result = ea.top_other_events(limit=2)
        assert len(result) == 2
        assert result[0][0] == "Event B"
        assert result[1][0] == "Event A"

    def test_empty(self, empty_emails):
        assert ea.top_other_events() == []


# =========================================================
# time_total
# =========================================================
class TestTimeTotal:
    def test_accumulates_by_person(self, fake_emails):
        fake_emails([
            _make_email(events=[{"label": "X", "amount": 1}]),
        ])
        emails = ea.load_emails()
        emails[0]["time_log"] = [
            {"status": "Да", "hours": "12:00",
             "people": ["Хисматуллин Р.И.", "Хисматуллина Ю.Ю."]},
            {"status": "Да", "hours": "08:30",
             "people": ["Хисматуллин Р.И."]},
        ]
        result = ea.time_total()
        assert result[0][0] == "Хисматуллин Р.И."
        assert result[0][1] == pytest.approx(20.5)
        assert result[1][0] == "Хисматуллина Ю.Ю."
        assert result[1][1] == pytest.approx(12.0)

    def test_skips_status_not_da(self, fake_emails):
        fake_emails([
            _make_email(events=[{"label": "X", "amount": 1}]),
        ])
        emails = ea.load_emails()
        emails[0]["time_log"] = [
            {"status": "Нет", "hours": "12:00", "people": ["A"]},
        ]
        assert ea.time_total() == []

    def test_skips_empty_hours(self, fake_emails):
        fake_emails([
            _make_email(events=[{"label": "X", "amount": 1}]),
        ])
        emails = ea.load_emails()
        emails[0]["time_log"] = [
            {"status": "Да", "hours": "", "people": ["A"]},
        ]
        assert ea.time_total() == []

    def test_skips_broken_hours(self, fake_emails):
        fake_emails([
            _make_email(events=[{"label": "X", "amount": 1}]),
        ])
        emails = ea.load_emails()
        emails[0]["time_log"] = [
            {"status": "Да", "hours": "abc", "people": ["A"]},
        ]
        assert ea.time_total() == []

    def test_empty_no_email(self, empty_emails):
        assert ea.time_total() == []


# =========================================================
# not_started
# =========================================================
class TestNotStarted:
    def test_collects_unique(self, fake_emails):
        fake_emails([
            _make_email(events=[
                {"label": "Обработка сверки", "status": "Не приступали"},
                {"label": "Обработка сверки", "status": "Не приступали"},
                {"label": "Другое", "status": "Не приступали"},
                {"label": "Сделано", "status": "Да"},
            ]),
        ])
        result = ea.not_started()
        assert set(result) == {"Обработка сверки", "Другое"}

    def test_empty_events(self, fake_emails):
        fake_emails([_make_email(events=[])])
        assert ea.not_started() == []

    def test_no_email(self, empty_emails):
        assert ea.not_started() == []


# =========================================================
# summary / summary_prev / summary_history
# =========================================================
class TestSummary:
    def test_uses_last_for_total_daily_for_events(self, fake_emails):
        """Итог — из финального. События — из последнего дневного.

        Сценарий: 2 дневных + 1 финальное.
        - emails_count = 2 (только дневные)
        - grand_total = 5000.0 (из финального)
        - zones — из последнего дневного с events
        - report_date — из финального
        """
        fake_emails([
            _make_email(
                report_date="01.10.2026",
                events=[{"label": "Алкоголь", "amount": 100.0}],
                cum_amount=100.0,
            ),
            _make_email(
                report_date="03.10.2026",
                events=[{"label": "Заморозка", "amount": 200.0}],
                cum_amount=300.0,
            ),
            _make_email(
                report_date="05.10.2026",
                events=[],
                final_amount=5000.0,
                is_final=True,
            ),
        ])
        result = ea.summary()

        # Итог — из финального
        assert result["totals"]["grand_total"] == 5000.0

        # Счётчик — только дневные
        assert result["emails_count"] == 2

        # Метаданные — из финального
        assert result["report_date"] == "05.10.2026"

        # События — из последнего дневного с events
        assert "Заморозка" in result["zones"]
        assert "Алкоголь" not in result["zones"]

    def test_emails_count_only_daily(self, fake_emails):
        """emails_count считает ТОЛЬКО дневные письма."""
        fake_emails([
            _make_email(report_date="01.10.2026"),
            _make_email(report_date="02.10.2026"),
            _make_email(report_date="03.10.2026"),
            _make_email(
                report_date="05.10.2026",
                final_amount=5000.0,
                is_final=True,
            ),
        ])
        assert ea.summary()["emails_count"] == 3

    def test_empty(self, empty_emails):
        result = ea.summary()
        assert result["emails_count"] == 0
        assert result["gm_code"] == ""
        assert result["totals"]["grand_total"] == 0.0
        assert result["zones"] == {}


class TestSummaryWithFinal:
    def test_grand_total_from_final(self, fake_emails):
        """grand_total — из финального письма."""
        fake_emails([
            _make_email(report_date="01.10.2026", cum_amount=100.0),
            _make_email(report_date="02.10.2026", cum_amount=200.0),
            _make_email(
                report_date="05.10.2026",
                final_amount=9999.0,
                is_final=True,
            ),
        ])
        assert ea.summary()["totals"]["grand_total"] == 9999.0

    def test_grand_total_fallback_to_daily(self, fake_emails):
        """Если финального нет — grand_total из последнего дневного."""
        fake_emails([
            _make_email(report_date="01.10.2026", cum_amount=100.0),
            _make_email(report_date="02.10.2026", cum_amount=777.0),
        ])
        assert ea.summary()["totals"]["grand_total"] == 777.0

    def test_report_date_from_final(self, fake_emails):
        """report_date — из финального, если есть."""
        fake_emails([
            _make_email(report_date="01.10.2026", cum_amount=100.0),
            _make_email(
                report_date="05.10.2026",
                final_amount=5000.0,
                is_final=True,
            ),
        ])
        assert ea.summary()["report_date"] == "05.10.2026"

    def test_zones_from_last_daily_not_final(self, fake_emails):
        """Зоны — из последнего дневного, не из финального."""
        fake_emails([
            _make_email(
                report_date="01.10.2026",
                events=[{"label": "Алкоголь", "amount": 100.0}],
                cum_amount=100.0,
            ),
            _make_email(
                report_date="05.10.2026",
                events=[],
                final_amount=5000.0,
                is_final=True,
            ),
        ])
        result = ea.summary()
        assert "Алкоголь" in result["zones"]


class TestSummaryPrev:
    def test_returns_prev(self, fake_emails):
        fake_emails([
            _make_email(report_date="01.10.2026", cum_amount=100.0),
            _make_email(report_date="05.10.2026", cum_amount=500.0),
        ])
        result = ea.summary_prev()
        assert result["report_date"] == "01.10.2026"
        assert result["grand_total"] == 100.0

    def test_one_email_returns_none(self, fake_emails):
        fake_emails([_make_email(report_date="01.10.2026")])
        assert ea.summary_prev() is None

    def test_empty_returns_none(self, empty_emails):
        assert ea.summary_prev() is None

    def test_ignores_final(self, fake_emails):
        """Финальное письмо не считается в summary_prev."""
        fake_emails([
            _make_email(report_date="01.10.2026", cum_amount=100.0),
            _make_email(
                report_date="05.10.2026",
                final_amount=5000.0,
                is_final=True,
            ),
        ])
        # Только 1 дневное — prev не из чего брать
        assert ea.summary_prev() is None


class TestSummaryHistory:
    def test_points_have_day_index(self, fake_emails):
        fake_emails([
            _make_email(report_date="01.10.2026", cum_amount=100.0),
            _make_email(report_date="02.10.2026", cum_amount=200.0),
            _make_email(report_date="03.10.2026", cum_amount=300.0),
        ])
        result = ea.summary_history()
        assert len(result) == 3
        assert result[0]["day_index"] == 1
        assert result[0]["label"] == "1 сутки"
        assert result[0]["total"] == 100.0
        assert result[2]["day_index"] == 3
        assert result[2]["total"] == 300.0

    def test_history_excludes_final(self, fake_emails):
        """График динамики НЕ включает финальное письмо."""
        fake_emails([
            _make_email(report_date="01.10.2026", cum_amount=100.0),
            _make_email(report_date="02.10.2026", cum_amount=200.0),
            _make_email(report_date="03.10.2026", cum_amount=300.0),
            _make_email(
                report_date="05.10.2026",
                final_amount=5000.0,
                is_final=True,
            ),
        ])
        result = ea.summary_history()
        # 3 точки (только дневные), не 4
        assert len(result) == 3
        # Последняя точка — 03.10.2026
        assert result[-1]["date"] == "03.10.2026"
        assert result[-1]["total"] == 300.0

    def test_empty(self, empty_emails):
        assert ea.summary_history() == []

    def test_only_final_returns_empty(self, fake_emails):
        """Если есть только финальное — график пустой."""
        fake_emails([
            _make_email(
                report_date="05.10.2026",
                final_amount=5000.0,
                is_final=True,
            ),
        ])
        assert ea.summary_history() == []


# =========================================================
# gm_list
# =========================================================
class TestGmList:
    def test_unique_gms(self, fake_emails):
        fake_emails([
            _make_email(gm_code="111", gm_name="Балашов 1"),
            _make_email(gm_code="222", gm_name="Энгельс 1"),
            _make_email(gm_code="111", gm_name="Балашов 1"),
        ])
        result = ea.gm_list()
        assert len(result) == 2
        codes = {g["code"] for g in result}
        assert codes == {"111", "222"}

    def test_display_format(self, fake_emails):
        fake_emails([
            _make_email(gm_code="111", gm_name="Балашов 1"),
        ])
        result = ea.gm_list()
        assert result[0]["display"] == "111 — Балашов 1"

    def test_empty(self, empty_emails):
        assert ea.gm_list() == []

    def test_sorted_by_name(self, fake_emails):
        fake_emails([
            _make_email(gm_code="111", gm_name="Яблонька"),
            _make_email(gm_code="222", gm_name="Абрикос"),
        ])
        result = ea.gm_list()
        assert result[0]["name"] == "Абрикос"
        assert result[1]["name"] == "Яблонька"