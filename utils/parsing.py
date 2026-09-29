# utils/parsing.py
"""
Парсинг и нормализация значений.

Чистые функции, без PyQt — можно тестировать без QApplication.
Вынесены из ui/frames/kv_frame.py и ui/frames/comments_frame.py,
чтобы тесты не тянули PyQt6.
"""
import re

import pandas as pd


# =========================================================
# ЧИСЛА ИЗ РУССКИХ СТРОК
# =========================================================
def to_float_ru(value):
    """Парсит русское число: '1 234,56' -> 1234.56.

    Поддерживает:
    - пробелы и неразрывные пробелы как разделители тысяч
    - запятую как десятичный разделитель
    - точку как десятичный разделитель
    - минус

    Returns:
        float или None, если распарсить не удалось.
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (ValueError, TypeError):
        pass

    s = str(value).strip()
    if not s:
        return None

    s = s.replace("\xa0", "").replace(" ", "")

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")

    s = re.sub(r"[^\d\.\-]", "", s)

    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def to_float(value):
    """Простой парсер числа: '1234.56' или '1234,56' -> 1234.56.

    Отличие от to_float_ru — не убирает пробелы-разделители тысяч,
    только заменяет запятую на точку.

    Returns:
        float или None.
    """
    if value is None:
        return None

    try:
        if isinstance(value, str):
            value = value.replace(",", ".").replace(" ", "").strip()
            if not value:
                return None
        return float(value)
    except (ValueError, TypeError):
        return None


# =========================================================
# НОМЕРА ДОКУМЕНТОВ
# =========================================================
def norm_number(value):
    """Нормализует номер документа к строке без пробелов и '.0' на конце.

    ' 12345.0 ' -> '12345'
    None -> ''
    """
    if value is None:
        return ""

    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


# =========================================================
# ПОИСК СТОЛБЦА В DATAFRAME
# =========================================================
def find_column_ci(df, name):
    """Ищет столбец в DataFrame по имени без учёта регистра, пробелов и ё/е.

    Args:
        df: pandas.DataFrame
        name: str — имя столбца

    Returns:
        Найденное имя столбца или None.
    """
    target = _normalize_col_name(name)
    for col in df.columns:
        c = _normalize_col_name(col)
        if c == target:
            return col
    return None


def _normalize_col_name(name):
    """Нормализует имя столбца: нижний регистр, без пробелов, ё -> е."""
    return str(name).strip().lower().replace("ё", "е").replace(" ", "")


# =========================================================
# СУММА СПИСКА ЗНАЧЕНИЙ ИЗ СЛОВАРЯ
# =========================================================
def sum_values(values, keys, parser=to_float):
    """Суммирует значения из словаря по списку ключей.

    Args:
        values: dict {key: value}
        keys: list ключей
        parser: функция парсинга (по умолчанию to_float)

    Returns:
        Сумма (float) или None, если хотя бы одно значение не распарсилось.
    """
    total = 0.0
    found = False
    for k in keys:
        v = parser(values.get(k, ""))
        if v is None:
            return None
        total += v
        found = True
    return total if found else None