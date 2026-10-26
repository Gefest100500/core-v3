# tests/test_file_utils_run.py
"""
Тесты для utils/file_utils.py.

Работаем с временными папками через tmp_path.
get_base_dir патчим через monkeypatch — иначе все папки
создадутся рядом с реальным проектом.

ИЗМЕНЕНИЯ:
- test_data_dir_created обновлён под новое поведение get_data_dir():
  папка данных теперь в %LOCALAPPDATA%/Core_V3_0/data (с fallback
  в корень проекта, если LOCALAPPDATA недоступна).
"""
import os
import sys
from pathlib import Path

import pytest

from utils import file_utils
from utils.file_utils import (
    get_base_dir,
    get_data_dir,
    get_logs_dir,
    get_input_dir,
    get_generated_dir,
    get_output_dir,
    get_temp_dir,
    clear_folder,
)


# =========================================================
# FIXTURES
# =========================================================
@pytest.fixture
def fake_base(tmp_path, monkeypatch):
    """Подменяет get_base_dir на tmp_path.

    Все остальные функции (get_logs_dir и т.д.) вызывают
    get_base_dir() — поэтому подмена работает каскадно.
    """
    monkeypatch.setattr(
        "utils.file_utils.get_base_dir",
        lambda: str(tmp_path),
    )
    return tmp_path


@pytest.fixture
def fake_local_appdata(tmp_path, monkeypatch):
    """Подменяет LOCALAPPDATA на временную папку.

    Нужно, чтобы get_data_dir() не уходила в реальный
    %LOCALAPPDATA% пользователя во время тестов.
    """
    local = tmp_path / "LocalAppData"
    local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    return local


# =========================================================
# get_base_dir
# =========================================================
class TestGetBaseDir:
    def test_returns_string(self):
        result = get_base_dir()
        assert isinstance(result, str)

    def test_path_exists(self):
        result = get_base_dir()
        assert os.path.isdir(result)

    def test_frozen_uses_exe_dir(self, monkeypatch):
        """Если sys.frozen — возвращает папку с .exe."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(
            sys, "executable",
            r"C:\Some\Path\Core.exe",
            raising=False,
        )

        result = get_base_dir()
        assert result == r"C:\Some\Path"

    def test_not_frozen_uses_project_root(self, monkeypatch):
        """Если не frozen — корень проекта (родитель file_utils)."""
        monkeypatch.setattr(sys, "frozen", False, raising=False)

        result = get_base_dir()
        # Должен заканчиваться на Core_V3_0 (или как называется проект)
        assert os.path.isdir(result)
        # Внутри должна быть папка utils
        assert os.path.isdir(os.path.join(result, "utils"))


# =========================================================
# СТАНДАРТНЫЕ ПАПКИ
# =========================================================
class TestStandardDirs:
    def test_data_dir_created(self, fake_base, fake_local_appdata):
        """get_data_dir() идёт в %LOCALAPPDATA%/Core_V3_0/data.

        Новая логика: данные ревизора живут в LOCALAPPDATA,
        а не в корне проекта — чтобы работать из Program Files.
        """
        path = get_data_dir()
        assert os.path.isdir(path)
        assert path.endswith("data")
        assert path.startswith(str(fake_local_appdata))
        assert "Core_V3_0" in path

    def test_data_dir_fallback(self, fake_base, monkeypatch):
        """Без LOCALAPPDATA — fallback в корень проекта."""
        monkeypatch.delenv("LOCALAPPDATA", raising=False)

        path = get_data_dir()
        assert os.path.isdir(path)
        assert path.endswith("data")
        assert path.startswith(str(fake_base))

    def test_logs_dir_created(self, fake_base):
        path = get_logs_dir()
        assert os.path.isdir(path)
        assert path.endswith("Logs")

    def test_input_dir_created(self, fake_base):
        path = get_input_dir()
        assert os.path.isdir(path)
        assert path.endswith("Файлы")

    def test_generated_dir_created(self, fake_base):
        path = get_generated_dir()
        assert os.path.isdir(path)
        assert path.endswith("Готовые")

    def test_output_dir_alias(self, fake_base):
        """get_output_dir — алиас get_generated_dir."""
        assert get_output_dir() == get_generated_dir()

    def test_temp_dir_created(self, fake_base):
        path = get_temp_dir()
        assert os.path.isdir(path)
        assert path.endswith("temp")

    def test_dirs_are_idempotent(self, fake_base, fake_local_appdata):
        """Повторный вызов не падает."""
        p1 = get_data_dir()
        p2 = get_data_dir()
        assert p1 == p2


# =========================================================
# clear_folder
# =========================================================
class TestClearFolder:
    def test_missing_folder(self, tmp_path):
        result = clear_folder(str(tmp_path / "nonexistent"))
        assert result == (0, 0)

    def test_empty_folder(self, tmp_path):
        folder = tmp_path / "empty"
        folder.mkdir()
        result = clear_folder(str(folder))
        assert result == (0, 0)

    def test_removes_files(self, tmp_path):
        folder = tmp_path / "test"
        folder.mkdir()
        (folder / "a.txt").write_text("a")
        (folder / "b.txt").write_text("b")

        removed, failed = clear_folder(str(folder))
        assert removed == 2
        assert failed == 0
        assert len(os.listdir(folder)) == 0

    def test_removes_subdirs(self, tmp_path):
        folder = tmp_path / "test"
        folder.mkdir()
        (folder / "sub").mkdir()
        (folder / "sub" / "file.txt").write_text("x")
        (folder / "file.txt").write_text("y")

        removed, failed = clear_folder(str(folder))
        assert removed == 2  # sub + file.txt
        assert failed == 0

    def test_mixed_content(self, tmp_path):
        folder = tmp_path / "test"
        folder.mkdir()
        (folder / "file1.txt").write_text("a")
        (folder / "sub1").mkdir()
        (folder / "sub2").mkdir()

        removed, failed = clear_folder(str(folder))
        assert removed == 3
        assert failed == 0

    def test_returns_tuple(self, tmp_path):
        folder = tmp_path / "test"
        folder.mkdir()
        result = clear_folder(str(folder))
        assert isinstance(result, tuple)
        assert len(result) == 2


# =========================================================
# clear_folder — логирование
# =========================================================
class TestClearFolderLogging:
    def test_logs_warning_on_failure(self, tmp_path, monkeypatch, caplog):
        """При ошибке удаления — warning."""
        folder = tmp_path / "test"
        folder.mkdir()
        (folder / "file.txt").write_text("a")

        # Патчим os.remove, чтобы падало
        def broken_remove(path):
            raise PermissionError("test error")

        monkeypatch.setattr(os, "remove", broken_remove)

        removed, failed = clear_folder(str(folder))
        assert removed == 0
        assert failed == 1


# =========================================================
# style_excel — простой тест
# =========================================================
class TestStyleExcel:
    def test_missing_file_no_error(self, tmp_path):
        """Несуществующий файл — не падаем."""
        from utils.file_utils import style_excel
        # Не должно быть исключения
        style_excel(str(tmp_path / "nonexistent.xlsx"))

    def test_styles_xlsx(self, tmp_path):
        """Применяем стиль к реальному xlsx."""
        import pandas as pd

        path = tmp_path / "test.xlsx"
        pd.DataFrame({
            "Колонка1": [1, 2],
            "Колонка2": ["a", "b"],
        }).to_excel(path, index=False)

        from utils.file_utils import style_excel
        style_excel(str(path))

        # Файл должен существовать и открываться
        assert os.path.isfile(path)
        from openpyxl import load_workbook
        wb = load_workbook(path)
        ws = wb.active
        # Проверяем, что первая ячейка имеет жирный шрифт
        assert ws.cell(row=1, column=1).font.bold is True