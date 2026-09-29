# utils/formatting.py
"""
Форматирование чисел для отчётов и комментариев.

Чистые функции, без PyQt.
Вынесены из ui/frames/comments_frame.py.
"""


def format_number_ru(value):
    """Форматирует число в русский формат: 1234567.89 -> '1 234 567,89'.

    - Разделитель тысяч — пробел
    - Десятичный разделитель — запятая
    - Два знака после запятой

    Args:
        value: float, int или строка

    Returns:
        Строка или str(value) при ошибке.
    """
    try:
        negative = value < 0
        v = abs(value)
        int_part = int(v)
        frac_part = round((v - int_part) * 100)

        if frac_part == 100:
            int_part += 1
            frac_part = 0

        int_str = f"{int_part:,}".replace(",", " ")
        result = f"{int_str},{frac_part:02d}"

        return ("-" + result) if negative else result
    except (ValueError, TypeError):
        return str(value)


def format_percent_ru(value, decimals=2):
    """Форматирует процент: 12.3456 -> '12,35'.

    Args:
        value: float или строка
        decimals: число знаков после запятой

    Returns:
        Строка или str(value) при ошибке.
    """
    try:
        formatted = f"{value:.{decimals}f}".replace(".", ",")
        return formatted
    except (ValueError, TypeError):
        return str(value)