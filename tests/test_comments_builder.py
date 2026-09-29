# tests/test_comments_builder.py
"""
Тесты для core/comments_builder.py.
"""
import pytest

from core.comments_builder import (
    resolve_conditional_block, build_comment_text
)


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


class TestBuildCommentText:
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
        # для копирования пустое — оставляем placeholder пустым
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