# tests/test_data_dir.py
"""
Тесты для get_data_dir() и get_app_data_root().
"""
import os
import sys
import tempfile

import pytest

from utils import file_utils


def test_get_data_dir_uses_local_appdata(monkeypatch, tmp_path):
    """При наличии LOCALAPPDATA путь идёт туда."""
    fake_local = tmp_path / "LocalAppData"
    fake_local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    path = file_utils.get_data_dir()

    assert path == os.path.join(str(fake_local), "Core_V3_0", "data")
    assert os.path.isdir(path)


def test_get_data_dir_fallback_without_local_appdata(monkeypatch):
    """Без LOCALAPPDATA — fallback в корень проекта."""
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    path = file_utils.get_data_dir()

    assert path == os.path.join(file_utils.get_base_dir(), "data")
    assert os.path.isdir(path)


def test_get_data_dir_creates_folder(monkeypatch, tmp_path):
    """Папка создаётся при первом вызове."""
    fake_local = tmp_path / "LocalAppData"
    fake_local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    expected = os.path.join(str(fake_local), "Core_V3_0", "data")
    assert not os.path.isdir(expected)

    file_utils.get_data_dir()

    assert os.path.isdir(expected)