# core/comments_builder.py
"""
Логика сборки стандартных комментариев.

Чистые функции, без PyQt.
Вынесено из ui/frames/comments_frame.py.

- resolve_conditional_block — логика условий (минус/плюс/ноль)
- build_comment_text — сборка текста из шаблона и значений

ИЗМЕНЕНИЯ:
- conditional_block: добавлено третье состояние zero_text (сумма 0 или пусто).
- Добавлен тип abs_formatted — подставляет модуль числа (без минуса).
"""
import re

from utils.parsing import to_float, sum_values
from utils.formatting import format_number_ru, format_percent_ru


def resolve_conditional_block(cfg, values, for_copy=True):
    """Выбирает текст условного блока по знаку.

    Args:
        cfg: dict — конфиг special-блока
        values: dict {key: text}
        for_copy: bool — для копирования или предпросмотра

    Returns:
        str — выбранный текст.
    """
    sign_keys = cfg.get("sign_keys", [])
    sign_mode = cfg.get("sign_mode", "sum")

    has_minus = False
    is_zero_or_empty = False

    if sign_mode == "sum":
        total = 0.0
        found = False
        for k in sign_keys:
            v = to_float(values.get(k, ""))
            if v is not None:
                total += v
                found = True
        has_minus = found and total < 0
        is_zero_or_empty = (not found) or (found and total == 0)
    else:
        for k in sign_keys:
            v = to_float(values.get(k, ""))
            if v is not None and v < 0:
                has_minus = True
                break
        is_zero_or_empty = not has_minus

    if has_minus:
        return cfg.get("surplus_text", "")
    if is_zero_or_empty and "zero_text" in cfg:
        return cfg.get("zero_text", "")
    return cfg.get("deficit_text", "")


def build_comment_text(item, values, for_copy=True):
    """Собирает текст комментария из шаблона и значений.

    Args:
        item: dict — комментарий (template, variables, special)
        values: dict {key: text} — введённые значения
        for_copy: bool — для копирования (True) или предпросмотра (False)

    Returns:
        str — готовый текст.
    """
    template = item.get("template", "")
    variables = item.get("variables", [])
    special = item.get("special", {})

    result = template

    # 1. Условные блоки
    for spec_key, spec_cfg in special.items():
        placeholder = "{" + spec_key + "}"
        if placeholder not in result:
            continue
        if spec_cfg.get("type") == "conditional_block":
            block_text = resolve_conditional_block(spec_cfg, values, for_copy)
            result = result.replace(placeholder, block_text)

    # 2. гм_part
    if "{гм_part}" in result:
        cfg = special.get("гм_part", {})
        var_key = cfg.get("variable", "гм")
        prefix = cfg.get("prefix", " ГМ ")
        gm_value = values.get(var_key, "")
        if gm_value:
            result = result.replace("{гм_part}", prefix + gm_value)
        else:
            result = result.replace("{гм_part}", "")

    # 3. Суммы, проценты и модули
    for spec_key, spec_cfg in special.items():
        placeholder = "{" + spec_key + "}"
        if placeholder not in result:
            continue

        spec_type = spec_cfg.get("type", "")

        if spec_type == "sum_formatted":
            keys = spec_cfg.get("keys", [])
            total = sum_values(values, keys)
            if total is not None:
                result = result.replace(placeholder, format_number_ru(total))
            else:
                result = result.replace(placeholder, "—" if for_copy else "…")

        elif spec_type == "abs_formatted":
            key = spec_cfg.get("key", "")
            val = to_float(values.get(key, ""))
            if val is not None:
                result = result.replace(
                    placeholder,
                    format_number_ru(abs(val))
                )
            else:
                result = result.replace(placeholder, "" if for_copy else "…")

        elif spec_type == "percent_formatted":
            num_key = spec_cfg.get("numerator", "")
            den_key = spec_cfg.get("denominator", "")
            decimals = spec_cfg.get("decimals", 2)

            num_val = to_float(values.get(num_key, ""))
            den_val = to_float(values.get(den_key, ""))

            if num_val is not None and den_val is not None and den_val != 0:
                percent = num_val / den_val * 100
                result = result.replace(
                    placeholder,
                    format_percent_ru(percent, decimals)
                )
            else:
                result = result.replace(placeholder, "—" if for_copy else "…")

    # 4. Простые переменные
    for var in variables:
        key = var.get("key", "")
        placeholder = "{" + key + "}"
        if placeholder in result:
            value = values.get(key, "")
            if value:
                result = result.replace(placeholder, value)
            else:
                if not for_copy:
                    result = result.replace(placeholder, "…")

    # 5. Чистка
    result = re.sub(r"\s+([.,;:!?])", r"\1", result)
    result = re.sub(r"\s{2,}", " ", result)
    result = result.strip()

    return result