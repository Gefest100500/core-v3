# ml/features.py
"""
Извлечение признаков из строки для будущей ML-модели.

Задача: превратить «сырую» строку в набор числовых/категориальных
признаков, по которым модель сможет предсказывать причину.

Пока модель не обучена — функции используются для:
- логирования (видно, какие признаки есть в строке)
- подготовки датасета (features → CSV)
- будущего train.py

ИЗМЕНЕНИЯ:
- Первая версия.
- extract_features(row) — главная функция.
- get_feature_names() — список имён признаков (для заголовка CSV).
"""
from typing import Any


# Список имён признаков — порядок важен для CSV
FEATURE_NAMES = [
    "tp_code",
    "gr20",
    "sign",
    "loss_amount",
    "name_length",
    "name_has_syre",
    "name_has_fruit",
    "name_has_veg",
    "rule_fired",
    "reason_code",  # числовая метка причины
]


# Словарь причин → числовые метки (для ML).
# Заполняется по мере появления новых причин.
REASON_TO_CODE = {
    "": 0,
    "Пересорт на кассе": 1,
    "Потери ТО (ошибки при работе с позициями сырья и готовой продукции)": 2,
    "Ошибки в работе (Местный поставщик)": 3,
    "Потери ТО (Местный поставщик)": 4,
    "Возможно хищение": 5,
    "Коробочный излишек - обычная приемка": 6,
    "Коробочный недовоз - обычная приемка": 7,
    "Нет потерь,  выявлено зеркальное отклонение": 8,
}


def extract_features(row: dict) -> dict:
    """Извлекает признаки из строки.

    Args:
        row: словарь с полями:
            - tp_code: код ТП (str)
            - gr20: группа 20 (str)
            - sign: «Излишек» / «Недостача» (str)
            - loss_amount: сумма потерь (float, может отсутствовать)
            - name: наименование ТП (str)
            - rule_fired: метка правила (str | None)
            - reason: типовая причина (str)

    Returns:
        Словарь {имя_признака: значение}.
    """
    tp_code = str(row.get("tp_code", "")).strip()
    gr20 = str(row.get("gr20", "")).strip()
    sign = str(row.get("sign", "")).strip()
    name = str(row.get("name", "")).strip()
    reason = str(row.get("reason", "")).strip()
    rule_fired = row.get("rule_fired") or ""

    # loss_amount может быть строкой или числом
    loss_amount = _to_float(row.get("loss_amount", 0))

    # Признаки по имени
    name_lower = name.lower()
    name_has_syre = int("сырь" in name_lower)
    name_has_fruit = int("фрукт" in name_lower)
    name_has_veg = int("овощ" in name_lower)

    # Числовая метка причины
    reason_code = REASON_TO_CODE.get(reason, -1)

    return {
        "tp_code": tp_code,
        "gr20": gr20,
        "sign": sign,
        "loss_amount": loss_amount,
        "name_length": len(name),
        "name_has_syre": name_has_syre,
        "name_has_fruit": name_has_fruit,
        "name_has_veg": name_has_veg,
        "rule_fired": rule_fired,
        "reason_code": reason_code,
    }


def get_feature_names() -> list:
    """Возвращает список имён признаков (порядок для CSV)."""
    return list(FEATURE_NAMES)


def _to_float(value: Any) -> float:
    """Безопасно преобразует в float."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError):
        return 0.0