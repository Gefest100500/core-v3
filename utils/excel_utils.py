# utils/excel_utils.py
"""
Утилиты для работы с Excel-файлами.

Чистые функции без PyQt — можно тестировать без QApplication.

Содержит:
- autofit_columns — подгонка ширины колонок под содержимое
- safe_filename — очистка имени от запрещённых символов

Раньше эти функции дублировались в 5 анализаторах (kv, pal, os_mbp,
brak_util, violations). Теперь — одна точка правды.
"""
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from utils.logger import log


# Запрещённые символы в именах файлов Windows
_BAD_FILENAME_CHARS = ['/', '\\', ':', '"', '<', '>', '|', '?', '*']


def autofit_columns(file_path, min_width=8, max_width=60):
    """Подгоняет ширину каждой колонки под самый длинный текст в ней.

    Args:
        file_path: путь к .xlsx файлу
        min_width: минимальная ширина колонки
        max_width: максимальная ширина колонки

    Файл должен существовать и быть доступен для записи.
    При PermissionError (файл занят) — логирует предупреждение и тихо выходит.
    """
    try:
        wb = load_workbook(file_path)
    except Exception as e:
        log.warning(f"Не удалось открыть файл для автоподбора ширины: {e}")
        return

    ws = wb.active

    for col_cells in ws.iter_cols():
        col_letter = None
        max_len = 0

        for cell in col_cells:
            if col_letter is None:
                col_letter = get_column_letter(cell.column)

            val = cell.value
            if val is None:
                continue

            text = str(val)
            lines = text.split("\n")
            line_len = max(len(line) for line in lines) if lines else 0

            if line_len > max_len:
                max_len = line_len

        if col_letter is None:
            continue

        width = max(min_width, min(max_len + 2, max_width))
        ws.column_dimensions[col_letter].width = width

    try:
        wb.save(file_path)
    except PermissionError:
        log.warning(
            f"Файл {file_path} занят — не удалось сохранить ширину колонок."
        )


def safe_filename(name):
    """Очищает имя от запрещённых символов Windows.

    Args:
        name: исходное имя

    Returns:
        Безопасное имя. Если после очистки пусто — возвращает "без_названия".
    """
    s = str(name)
    for ch in _BAD_FILENAME_CHARS:
        s = s.replace(ch, "_")
    return s.strip() or "без_названия"