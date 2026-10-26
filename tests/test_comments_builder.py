# tests/test_comments_builder.py
"""
Тесты для core/comments_builder.py.

Проверяем:
- resolve_conditional_block: sum / any, пустые значения, несколько ключей.
- build_comment_text: простые переменные, гм_part, условные блоки,
  sum_formatted, percent_formatted, чистка пробелов.
- Режимы for_copy=True / for_copy=False.
"""
import pytest

from core.comments_builder import (
    resolve_conditional_block, build_comment_text
)


# =========================================================
# resolve_conditional_block
# =========================================================
class TestResolveConditionalBlock:

    def test_deficit_no_minus(self):
        cfg = {
            "sign_keys": ["ing"],
            "sign_mode": "sum",
            "surplus_text": "излишек",
            "deficit_text": "недостача",
        }
        values = {"ing": "100"}
        assert resolve_conditional_block(cfg, values) == "недостача"

    def test_surplus_with_minus(self):
        cfg = {
            "sign_keys": ["ing"],
            "sign_mode": "sum",
            "surplus_text": "излишек",
            "deficit_text": "недостача",
        }
        values = {"ing": "-100"}
        assert resolve_conditional_block(cfg, values) == "излишек"

    def test_sum_mode(self):
        cfg = {
            "sign_keys": ["a", "b"],
            "sign_mode": "sum",
            "surplus_text": "излишек",
            "deficit_text": "недостача",
        }
        # 100 + (-200) = -100 → излишек
        values = {"a": "100", "b": "-200"}
        assert resolve_conditional_block(cfg, values) == "излишек"

    def test_sum_mode_zero(self):
        cfg = {
            "sign_keys": ["sum"],
            "sign_mode": "sum",
            "surplus_text": "излишек",
            "deficit_text": "недостача",
        }
        values = {"sum": "0"}
        assert resolve_conditional_block(cfg, values) == "недостача"

    def test_sum_mode_empty_values(self):
        cfg = {
            "sign_keys": ["sum"],
            "sign_mode": "sum",
            "surplus_text": "излишек",
            "deficit_text": "недостача",
        }
        assert resolve_conditional_block(cfg, {}) == "недостача"

    def test_any_mode_negative(self):
        cfg = {
            "sign_keys": ["a", "b"],
            "sign_mode": "any",
            "surplus_text": "излишек",
            "deficit_text": "недостача",
        }
        values = {"a": "100", "b": "-50"}
        assert resolve_conditional_block(cfg, values) == "излишек"

    def test_any_mode_all_positive(self):
        cfg = {
            "sign_keys": ["a", "b"],
            "sign_mode": "any",
            "surplus_text": "излишек",
            "deficit_text": "недостача",
        }
        values = {"a": "100", "b": "50"}
        assert resolve_conditional_block(cfg, values) == "недостача"

    def test_missing_text_returns_empty(self):
        cfg = {
            "sign_keys": ["sum"],
            "sign_mode": "sum",
        }
        values = {"sum": "-100"}
        assert resolve_conditional_block(cfg, values) == ""

    def test_default_sign_mode_is_sum(self):
        cfg = {
            "sign_keys": ["sum"],
            "surplus_text": "излишек",
            "deficit_text": "недостача",
        }
        values = {"sum": "-100"}
        assert resolve_conditional_block(cfg, values) == "излишек"


# =========================================================
# build_comment_text — простые переменные
# =========================================================
class TestBuildSimpleVariables:

    def test_simple_template(self):
        item = {
            "template": "Привет, {name}!",
            "variables": [{"key": "name", "label": "Имя"}],
            "special": {},
        }
        values = {"name": "Лёша"}
        assert build_comment_text(item, values) == "Привет, Лёша!"

    def test_empty_value_for_copy(self):
        item = {
            "template": "Привет, {name}!",
            "variables": [{"key": "name", "label": "Имя"}],
            "special": {},
        }
        values = {"name": ""}
        result = build_comment_text(item, values, for_copy=True)
        assert "Привет," in result

    def test_empty_value_for_preview(self):
        item = {
            "template": "Привет, {name}!",
            "variables": [{"key": "name", "label": "Имя"}],
            "special": {},
        }
        values = {"name": ""}
        result = build_comment_text(item, values, for_copy=False)
        assert "…" in result

    def test_unknown_placeholder_untouched(self):
        item = {
            "template": "ГМ: {gm}. {unknown}",
            "variables": [{"key": "gm", "label": "ГМ"}],
            "special": {},
        }
        result = build_comment_text(item, {"gm": "Москва"})
        assert "{unknown}" in result


# =========================================================
# build_comment_text — гм_part
# =========================================================
class TestGmPart:

    def test_gm_part(self):
        item = {
            "template": "Магазин{гм_part}",
            "variables": [{"key": "гм", "label": "ГМ"}],
            "special": {
                "гм_part": {"variable": "гм", "prefix": " "},
            },
        }
        values = {"гм": "Волжск 1"}
        assert build_comment_text(item, values) == "Магазин Волжск 1"

    def test_gm_part_empty(self):
        item = {
            "template": "Магазин{гм_part}.",
            "variables": [{"key": "гм", "label": "ГМ"}],
            "special": {
                "гм_part": {"variable": "гм", "prefix": " "},
            },
        }
        values = {"гм": ""}
        assert build_comment_text(item, values) == "Магазин."

    def test_gm_part_custom_prefix(self):
        item = {
            "template": "{гм_part}",
            "variables": [{"key": "гм", "label": "ГМ"}],
            "special": {
                "гм_part": {"variable": "гм", "prefix": " в "},
            },
        }
        values = {"гм": "Москва"}
        assert build_comment_text(item, values) == "в Москва"


# =========================================================
# build_comment_text — условные блоки
# =========================================================
class TestConditionalBlocks:

    def _make_item(self):
        return {
            "template": "Сумма: {cond}.",
            "special": {
                "cond": {
                    "type": "conditional_block",
                    "sign_mode": "sum",
                    "sign_keys": ["sum"],
                    "surplus_text": "излишек",
                    "deficit_text": "недостача",
                }
            },
            "variables": [],
        }

    def test_deficit(self):
        item = self._make_item()
        result = build_comment_text(item, {"sum": "100"})
        assert "недостача" in result

    def test_surplus(self):
        item = self._make_item()
        result = build_comment_text(item, {"sum": "-100"})
        assert "излишек" in result


# =========================================================
# build_comment_text — sum_formatted
# =========================================================
class TestSumFormatted:

    def test_sum_formatted(self):
        item = {
            "template": "Итого: {total}",
            "variables": [],
            "special": {
                "total": {
                    "type": "sum_formatted",
                    "keys": ["a", "b"],
                }
            },
        }
        values = {"a": "100,5", "b": "200,5"}
        assert "301,00" in build_comment_text(item, values)

    def test_sum_formatted_empty_for_copy(self):
        item = {
            "template": "Итого: {total}.",
            "variables": [],
            "special": {
                "total": {
                    "type": "sum_formatted",
                    "keys": ["a"],
                }
            },
        }
        result = build_comment_text(item, {}, for_copy=True)
        assert "—" in result

    def test_sum_formatted_empty_for_preview(self):
        item = {
            "template": "Итого: {total}.",
            "variables": [],
            "special": {
                "total": {
                    "type": "sum_formatted",
                    "keys": ["a"],
                }
            },
        }
        result = build_comment_text(item, {}, for_copy=False)
        assert "…" in result


# =========================================================
# build_comment_text — percent_formatted
# =========================================================
class TestPercentFormatted:

    def test_percent_formatted(self):
        item = {
            "template": "Процент: {pct}.",
            "variables": [],
            "special": {
                "pct": {
                    "type": "percent_formatted",
                    "numerator": "num",
                    "denominator": "den",
                    "decimals": 2,
                }
            },
        }
        result = build_comment_text(item, {"num": "25", "den": "100"})
        assert "25,00" in result

    def test_percent_zero_denominator(self):
        item = {
            "template": "Процент: {pct}.",
            "variables": [],
            "special": {
                "pct": {
                    "type": "percent_formatted",
                    "numerator": "num",
                    "denominator": "den",
                }
            },
        }
        result = build_comment_text(item, {"num": "25", "den": "0"}, for_copy=True)
        assert "—" in result

    def test_percent_missing_values(self):
        item = {
            "template": "Процент: {pct}.",
            "variables": [],
            "special": {
                "pct": {
                    "type": "percent_formatted",
                    "numerator": "num",
                    "denominator": "den",
                }
            },
        }
        result = build_comment_text(item, {}, for_copy=False)
        assert "…" in result


# =========================================================
# Чистка пробелов
# =========================================================
class TestWhitespaceCleanup:

    def test_removes_extra_spaces(self):
        item = {
            "template": "А   Б  В",
            "variables": [],
            "special": {},
        }
        result = build_comment_text(item, {})
        assert result == "А Б В"

    def test_removes_space_before_punctuation(self):
        item = {
            "template": "Привет , мир .",
            "variables": [],
            "special": {},
        }
        result = build_comment_text(item, {})
        assert result == "Привет, мир."

    def test_strips(self):
        item = {
            "template": "  Привет  ",
            "variables": [],
            "special": {},
        }
        result = build_comment_text(item, {})
        assert result == "Привет"