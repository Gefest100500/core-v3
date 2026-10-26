# tests/test_email_parser.py
"""
Тесты для core/email_parser.py.

Проверяем парсинг тела письма от Krs_gk_gm_otchet@magnit.ru.

Покрываем:
- _parse_amount: числа с пробелами, запятыми, минусом
- _parse_gm_header: два формата (ежедневный / финальный)
- _parse_dates: даты начала и окончания
- _parse_duration_variant: длительность и вариант
- _parse_author: автор и дата
- _parse_executors: исполнители из шапки
- _parse_totals: промежуточные итоги (daily + cumulative)
- _parse_final_totals: финальные суммы
- _parse_events_block: события (Да/Нет/Не приступали + сумма)
- _parse_time_log: учёт рабочего времени
- _parse_comments: комментарии с датами
- parse_email_body: полный парсинг ежедневного и финального письма
- summarize_emails: сводка по списку писем
"""
import pytest

from core.email_parser import (
    _parse_amount,
    _parse_gm_header,
    _parse_dates,
    _parse_duration_variant,
    _parse_author,
    _parse_executors,
    _parse_totals,
    _parse_final_totals,
    _parse_events_block,
    _parse_time_log,
    _parse_comments,
    parse_email_body,
    summarize_emails,
)


# =========================================================
# ФИКСТУРЫ
# =========================================================
@pytest.fixture
def daily_email_body():
    """Ежедневное письмо (сокращённая версия example_email.txt)."""
    return (
        "\n"
        "Добрый день!\n"
        "\n"
        "Исполнители:\n"
        "           Хисматуллина Юлия Юрьевна | Самара(Стажер)\n"
        "           Сильченко Алексей Сергеевич | Волжский(Старший ревизор) +79057724186\n"
        "           Хисматуллин Руслан Ильдарович | Казань(Ревизор) 89874325442\n"
        "\n"
        "           Отчет отправил(a) Сильченко Алексей Сергеевич 05.10.2026 07:16\n"
        "\n"
        "Промежуточные итоги инвентаризации ГМ Балашов 1 Энтузиастов (996414, формат «S+»):\n"
        "\n"
        "           Итого за день (04.10.2026): 132 583 руб. недостачей.\n"
        "           Итого за день (05.10.2026): -3 397 руб. излишком.\n"
        "\n"
        "           Итого накопительно с РМ и МЦ: 129 186 руб. недостачей.\n"
        "           Итого накопительно без учета РМ и МЦ: 129 186 руб. недостачей.\n"
        "\n"
        "Информация о проведенных мероприятиях в рамках полной инвентаризации ГМ Балашов 1 Энтузиастов:\n"
        "\n"
        "а. Подготовка к инвентаризации\n"
        "\n"
        "           -Проведение выверки баффер-стока: Да , 04.10.2026\n"
        "           -Проверка всех паллет вне баффер-стока: Да , 04.10.2026\n"
        "\n"
        "б. Проведение инвентаризации\n"
        "\n"
        "           -Проведение инвентаризации ДС в ГК БФ: Нет\n"
        "           -Обработка сверки баз данных ГК, РЦ и ГМ - Не приступали\n"
        "           -Проверка статусов операций: Да , 04.10.2026\n"
        "           -Инвентаризация зоны \"Охлажденная продукция\": Да , 04.10.2026, 312 500 руб недостачей\n"
        "           -Инвентаризация зоны \"Алкоголь\": Да , 04.10.2026, -271 060 руб излишком\n"
        "           -Перепроверка расхождений: Да , 05.10.2026, -9 885 руб излишком (Комментарий: Перепроверка: Заморозка)\n"
        "           -Перепроверка расхождений: Да , 05.10.2026, 6 488 руб недостачей (Комментарий: Перепроверка: Сигареты)\n"
        "\n"
        "в. Учет рабочего времени ревизионной комиссии\n"
        "\n"
        "           -1 сутки, вс. день (8:00-20:00): Да , 04.10.2026 08:00 - 04.10.2026 20:00, (12:00), Хисматуллин Р.И.,Хисматуллина Ю.Ю.\n"
        "           -1 сутки, вс. ночь (20:00-8:00): Да , 04.10.2026 20:00 - 05.10.2026 08:00, (12:00), Сильченко А.С.\n"
        "\n"
        "Дополнительный комментарий:\n"
        "\n"
        "Комментарий\tДата\t\n"
        "Первая дневная смена пересчета ГМ Балашов 1 Энтузиастов прошла по плану.04.10.2026\n"
        "Первая ночь пересчета ГМ Балашов 1 Энтузиастов, не закончили перепроверку по АЗ Охлажденка и Алкоголь.05.10.2026\n"
        "-\n"
        "С уважением, Сильченко Алексей Сергеевич\n"
        "05.10.2026 07:16\n"
    )


@pytest.fixture
def final_email_body():
    """Финальное письмо (сокращённая версия из emails.json)."""
    return (
        "\n"
        "Добрый день!\n"
        "\n"
        "1. Общая информация о полной инвентаризации ГМ:\n"
        "\n"
        "       Гипермаркет (ГМ): Энгельс 1 Колотилова (996408).\n"
        "       Формат ГМ: L+\n"
        "       Дата начала инвентаризации ГМ: 26.07.2026\n"
        "       Дата окончания инвентаризации ГМ: 31.07.2026\n"
        "       Номер последнего учетного периода: 19\n"
        "       Длительность интенсивного пересчета товара: 4 суток (Вариант Ж)\n"
        "\n"
        "2. Качество подготовки ГМ к полной инвентаризации:\n"
        "\n"
        "       2.1.Техническая часть\n"
        "       Замечаний нет\n"
        "\n"
        "3. Тех. процессы ГМ: проблемы, замечания:\n"
        "\n"
        "       3.1. Дополнительная информация\n"
        "\n"
        "Комментарий\tДата\t\n"
        "Первый день пересчета ГМ Энгельс 1 Колотилова прошел по плану.\t27.07.2026\n"
        "-\n"
        "С уважением, Хисматуллин Руслан Ильдарович\n"
        "31.07.2026 01:37\n"
        "\n"
        "4. Итоги полной инвентаризации ГМ:\n"
        "\n"
        "       Сумма полной инвентаризации c РМ и МЦ: 1 898 372,72 руб. недостачей,\n"
        "       Сумма полной инвентаризации без учета РМ и МЦ: 2 420 549,13 руб. недостачей\n"
    )


# =========================================================
# _parse_amount
# =========================================================
class TestParseAmount:
    def test_simple_int(self):
        assert _parse_amount("132583") == 132583.0

    def test_spaces_thousands(self):
        assert _parse_amount("132 583") == 132583.0

    def test_nbsp_thousands(self):
        assert _parse_amount("132\xa0583") == 132583.0

    def test_comma_decimal(self):
        assert _parse_amount("1 898 372,72") == 1898372.72

    def test_negative(self):
        assert _parse_amount("-3 397") == -3397.0

    def test_negative_with_decimal(self):
        assert _parse_amount("-271 060") == -271060.0

    def test_empty(self):
        assert _parse_amount("") is None

    def test_garbage(self):
        assert _parse_amount("abc") is None


# =========================================================
# _parse_gm_header
# =========================================================
class TestParseGmHeader:
    def test_daily_format(self):
        text = "инвентаризации ГМ Балашов 1 Энтузиастов (996414, формат «S+»):"
        result = _parse_gm_header(text)
        assert result["gm_code"] == "996414"
        assert result["gm_name"] == "Балашов 1 Энтузиастов"
        assert result["format"] == "S+"

    def test_final_format(self):
        text = (
            "Гипермаркет (ГМ): Энгельс 1 Колотилова (996408).\n"
            "Формат ГМ: L+"
        )
        result = _parse_gm_header(text)
        assert result["gm_code"] == "996408"
        assert result["gm_name"] == "Энгельс 1 Колотилова"
        assert result["format"] == "L+"

    def test_not_found(self):
        result = _parse_gm_header("текст без ГМ")
        assert result == {}


# =========================================================
# _parse_dates
# =========================================================
class TestParseDates:
    def test_both_dates(self):
        text = (
            "Дата начала инвентаризации ГМ: 26.07.2026\n"
            "Дата окончания инвентаризации ГМ: 31.07.2026"
        )
        result = _parse_dates(text)
        assert result["start_date"] == "26.07.2026"
        assert result["end_date"] == "31.07.2026"

    def test_no_dates(self):
        result = _parse_dates("текст без дат")
        assert result["start_date"] == ""
        assert result["end_date"] == ""


# =========================================================
# _parse_duration_variant
# =========================================================
class TestParseDurationVariant:
    def test_simple(self):
        text = "Длительность интенсивного пересчета товара: 4 суток (Вариант Ж)"
        result = _parse_duration_variant(text)
        assert result["duration_days"] == 4
        assert result["variant"] == "Ж"

    def test_lowercase_variant(self):
        text = "Длительность интенсивного пересчета товара: 5 суток (Вариант е)"
        result = _parse_duration_variant(text)
        assert result["duration_days"] == 5
        assert result["variant"] == "Е"

    def test_not_found(self):
        result = _parse_duration_variant("текст без длительности")
        assert result["duration_days"] is None
        assert result["variant"] == ""


# =========================================================
# _parse_author
# =========================================================
class TestParseAuthor:
    def test_simple(self):
        text = "Отчет отправил(a) Сильченко Алексей Сергеевич 05.10.2026 07:16"
        result = _parse_author(text)
        assert result["author"] == "Сильченко Алексей Сергеевич"
        assert result["author_date"] == "05.10.2026 07:16"

    def test_not_found(self):
        result = _parse_author("текст без автора")
        assert result == {}


# =========================================================
# _parse_executors
# =========================================================
class TestParseExecutors:
    def test_three_executors(self):
        lines = [
            "Исполнители:",
            "           Хисматуллина Юлия Юрьевна | Самара(Стажер)",
            "           Сильченко Алексей Сергеевич | Волжский(Старший ревизор) +79057724186",
            "           Хисматуллин Руслан Ильдарович | Казань(Ревизор) 89874325442",
        ]
        result = _parse_executors(lines)
        assert len(result) == 3
        assert result[0]["name"] == "Хисматуллина Юлия Юрьевна"
        assert result[0]["city"] == "Самара"
        assert result[0]["role"] == "Стажер"

        assert result[1]["name"] == "Сильченко Алексей Сергеевич"
        assert result[1]["city"] == "Волжский"
        assert result[1]["role"] == "Старший ревизор"
        assert result[1]["phone"] == "+79057724186"

    def test_empty(self):
        assert _parse_executors([]) == []


# =========================================================
# _parse_totals
# =========================================================
class TestParseTotals:
    def test_daily_and_cumulative(self):
        text = (
            "Итого за день (04.10.2026): 132 583 руб. недостачей.\n"
            "Итого за день (05.10.2026): -3 397 руб. излишком.\n"
            "Итого накопительно с РМ и МЦ: 129 186 руб. недостачей.\n"
            "Итого накопительно без учета РМ и МЦ: 129 186 руб. недостачей."
        )
        result = _parse_totals(text)

        assert len(result["daily"]) == 2
        assert result["daily"][0]["date"] == "04.10.2026"
        assert result["daily"][0]["amount"] == 132583.0
        assert result["daily"][0]["type"] == "недостачей"

        assert result["daily"][1]["date"] == "05.10.2026"
        assert result["daily"][1]["amount"] == -3397.0
        assert result["daily"][1]["type"] == "излишком"

        assert result["cumulative_with_rm"]["amount"] == 129186.0
        assert result["cumulative_without_rm"]["amount"] == 129186.0

    def test_empty(self):
        result = _parse_totals("текст без итогов")
        assert result["daily"] == []
        assert result["cumulative_with_rm"] is None
        assert result["cumulative_without_rm"] is None


# =========================================================
# _parse_final_totals
# =========================================================
class TestParseFinalTotals:
    def test_both(self):
        text = (
            "Сумма полной инвентаризации c РМ и МЦ: 1 898 372,72 руб. недостачей,\n"
            "Сумма полной инвентаризации без учета РМ и МЦ: 2 420 549,13 руб. недостачей"
        )
        result = _parse_final_totals(text)
        assert result["with_rm"]["amount"] == 1898372.72
        assert result["with_rm"]["type"] == "недостачей"
        assert result["without_rm"]["amount"] == 2420549.13
        assert result["without_rm"]["type"] == "недостачей"

    def test_surplus(self):
        text = "Сумма полной инвентаризации без учета РМ и МЦ: 100 руб. излишком"
        result = _parse_final_totals(text)
        assert result["with_rm"] is None
        assert result["without_rm"]["amount"] == 100.0
        assert result["without_rm"]["type"] == "излишком"

    def test_not_final(self):
        result = _parse_final_totals("обычный текст")
        assert result["with_rm"] is None
        assert result["without_rm"] is None


# =========================================================
# _parse_events_block
# =========================================================
class TestParseEventsBlock:
    def test_status_date_amount(self):
        lines = [
            "-Проверка статусов операций: Да , 04.10.2026",
            "-Инвентаризация зоны \"Охлажденная продукция\": Да , 04.10.2026, 312 500 руб недостачей",
            "-Инвентаризация зоны \"Алкоголь\": Да , 04.10.2026, -271 060 руб излишком",
        ]
        result = _parse_events_block(lines)
        assert len(result) == 3

        assert result[0]["label"] == "Проверка статусов операций"
        assert result[0]["status"] == "Да"
        assert result[0]["date"] == "04.10.2026"
        assert result[0]["amount"] is None

        assert result[1]["amount"] == 312500.0
        assert result[1]["type"] == "недостачей"

        assert result[2]["amount"] == -271060.0
        assert result[2]["type"] == "излишком"

    def test_not_started(self):
        lines = ["-Обработка сверки баз данных ГК, РЦ и ГМ - Не приступали"]
        result = _parse_events_block(lines)
        assert len(result) == 1
        assert result[0]["status"] == "Не приступали"
        assert result[0]["amount"] is None

    def test_with_comment(self):
        lines = [
            "-Перепроверка расхождений: Да , 05.10.2026, -9 885 руб излишком "
            "(Комментарий: Перепроверка: Заморозка)"
        ]
        result = _parse_events_block(lines)
        assert len(result) == 1
        assert result[0]["comment"] == "Перепроверка: Заморозка"
        assert result[0]["amount"] == -9885.0

    def test_empty(self):
        assert _parse_events_block([]) == []


# =========================================================
# _parse_time_log
# =========================================================
class TestParseTimeLog:
    def test_full_line(self):
        lines = [
            "-1 сутки, вс. день (8:00-20:00): Да , "
            "04.10.2026 08:00 - 04.10.2026 20:00, (12:00), "
            "Хисматуллин Р.И.,Хисматуллина Ю.Ю."
        ]
        result = _parse_time_log(lines)
        assert len(result) == 1
        assert result[0]["status"] == "Да"
        assert result[0]["hours"] == "12:00"
        assert len(result[0]["people"]) == 2
        assert "Хисматуллин Р.И." in result[0]["people"]

    def test_not_started(self):
        lines = ["-2 сутки, пн. день (8:00-20:00) - Не приступали"]
        result = _parse_time_log(lines)
        assert len(result) == 1
        assert result[0]["status"] == "Не приступали"

    def test_empty(self):
        assert _parse_time_log([]) == []


# =========================================================
# _parse_comments
# =========================================================
class TestParseComments:
    def test_two_comments(self):
        lines = [
            "Комментарий\tДата\t",
            "Первая дневная смена пересчета прошла по плану.04.10.2026",
            "Первая ночь пересчета, не закончили перепроверку.05.10.2026",
            "-",
            "С уважением, Сильченко Алексей Сергеевич",
        ]
        result = _parse_comments(lines)
        assert len(result) == 2
        assert result[0]["date"] == "04.10.2026"
        assert "Первая дневная смена" in result[0]["text"]
        assert result[1]["date"] == "05.10.2026"

    def test_stops_at_signature(self):
        lines = [
            "Комментарий.05.10.2026",
            "С уважением, кто-то",
            "Ещё комментарий.06.10.2026",
        ]
        result = _parse_comments(lines)
        assert len(result) == 1

    def test_empty(self):
        assert _parse_comments([]) == []


# =========================================================
# parse_email_body — ИНТЕГРАЦИОННЫЕ
# =========================================================
class TestParseEmailBodyDaily:
    def test_daily_parses(self, daily_email_body):
        result = parse_email_body(
            daily_email_body,
            "Отчет о ходе проведения полной инвентаризации ГМ Балашов 1 Энтузиастов — 04.10.2026"
        )

        assert result["gm_code"] == "996414"
        assert result["gm_name"] == "Балашов 1 Энтузиастов"
        assert result["report_date"] == "04.10.2026"
        assert result["is_final"] is False

        assert len(result["executors"]) == 3
        assert result["author"] == "Сильченко Алексей Сергеевич"

        assert len(result["totals"]["daily"]) == 2
        assert result["totals"]["cumulative_with_rm"]["amount"] == 129186.0

        assert len(result["preparation"]) == 2
        assert len(result["time_log"]) == 2
        assert len(result["comments"]) == 2


class TestParseEmailBodyFinal:
    def test_final_parses(self, final_email_body):
        result = parse_email_body(
            final_email_body,
            "Отчет о завершении полной инвентаризации ГМ Энгельс 1 Колотилова (26.07.2026 — 31.07.2026)"
        )

        assert result["gm_code"] == "996408"
        assert result["gm_name"] == "Энгельс 1 Колотилова"
        assert result["is_final"] is True

        # Для финального — report_date = end_date
        assert result["report_date"] == "31.07.2026"

        assert result["final_totals"]["with_rm"]["amount"] == 1898372.72
        assert result["final_totals"]["without_rm"]["amount"] == 2420549.13

        # events у финального — пустые (нет секции "Проведение")
        assert result["preparation"] == []
        assert result["events"] == []


class TestParseEmailBodyEmpty:
    def test_empty_body(self):
        result = parse_email_body("", "")
        assert result["gm_code"] == ""
        assert result["report_date"] == ""
        assert "Тело письма пустое" in result["parse_warnings"]


# =========================================================
# summarize_emails
# =========================================================
class TestSummarizeEmails:
    def test_empty_list(self):
        result = summarize_emails([])
        assert result["gm_code"] == ""
        assert result["daily"] == []
        assert result["top_events"] == []
        assert result["not_started"] == []
        assert result["time_total"] == {}

    def test_daily_merge(self, daily_email_body):
        """Два письма с одинаковыми днями — берётся последняя версия."""
        parsed = parse_email_body(
            daily_email_body,
            "Отчет о ходе проведения полной инвентаризации ГМ Балашов 1 Энтузиастов — 04.10.2026"
        )
        result = summarize_emails([parsed, parsed])

        assert result["gm_code"] == "996414"
        assert result["gm_name"] == "Балашов 1 Энтузиастов"
        # daily уникализируется по дате, а не по письму
        dates = [d["date"] for d in result["daily"]]
        assert len(dates) == len(set(dates))

    def test_time_total_accumulates(self, daily_email_body):
        parsed = parse_email_body(
            daily_email_body,
            "Отчет о ходе проведения полной инвентаризации ГМ Балашов 1 Энтузиастов — 04.10.2026"
        )
        result = summarize_emails([parsed, parsed])

        # Хисматуллин Р.И. отработал 12:00 в каждом письме → 24 часа
        assert "Хисматуллин Р.И." in result["time_total"]
        assert result["time_total"]["Хисматуллин Р.И."] == 24.0