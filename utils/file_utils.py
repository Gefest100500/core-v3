# utils/file_utils.py
"""
Утилиты для работы с файлами и папками.

Определяет базовые директории проекта (base, data, logs, input, output, temp).
Работает и как скрипт, и как .exe (PyInstaller).
"""
import sys
import os
from pathlib import Path
import shutil


def get_base_dir():
    """Возвращает базовую директорию.

    - Если запущено как .exe (PyInstaller) — папка рядом с .exe
    - Если обычный скрипт — корень проекта (где main.py)
    """
    if getattr(sys, "frozen", False):
        # .exe — папка рядом с Core.exe
        return str(Path(sys.executable).resolve().parent)
    else:
        # Скрипт — корень проекта (где main.py)
        return str(Path(__file__).resolve().parent.parent)


def get_data_dir():
    """Папка для JSON-данных (data/). Создаётся при первом вызове."""
    path = os.path.join(get_base_dir(), "data")
    os.makedirs(path, exist_ok=True)
    return path


def get_logs_dir():
    """Папка для логов (Logs/). Создаётся при первом вызове."""
    path = os.path.join(get_base_dir(), "Logs")
    os.makedirs(path, exist_ok=True)
    return path


def get_input_dir():
    """Папка входных файлов (Файлы/). Создаётся при первом вызове."""
    path = os.path.join(get_base_dir(), "Файлы")
    os.makedirs(path, exist_ok=True)
    return path


def get_output_dir():
    """Папка результатов (Готовые/). Создаётся при первом вызове."""
    path = os.path.join(get_base_dir(), "Готовые")
    os.makedirs(path, exist_ok=True)
    return path


def get_temp_dir():
    """Папка временных файлов (temp/). Создаётся при первом вызове."""
    path = os.path.join(get_base_dir(), "temp")
    os.makedirs(path, exist_ok=True)
    return path


def clear_folder(folder_path):
    """Очищает папку. Молча игнорирует ошибки доступа."""
    if not os.path.isdir(folder_path):
        return
    for entry in os.listdir(folder_path):
        full_path = os.path.join(folder_path, entry)
        try:
            if os.path.isfile(full_path) or os.path.islink(full_path):
                os.remove(full_path)
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
        except (OSError, PermissionError):
            pass


def style_excel(file_path, header_row=1, start_col=1, end_col=None):
    """Применяет стиль к заголовкам Excel-файла.

    file_path может быть:
    - str — путь к .xlsx файлу (обрабатываются ВСЕ листы файла)
    - openpyxl.Worksheet — конкретный лист (обрабатывается только он)

    ВАЖНО: если передан str — это ДОЛЖЕН быть путь к файлу,
    а не имя листа. Иначе будет AttributeError.
    """
    from openpyxl import load_workbook

    if isinstance(file_path, str):
        if not os.path.exists(file_path):
            return
        wb = load_workbook(file_path)
        for sheet_name in wb.sheetnames:
            _style_worksheet(wb[sheet_name], header_row, start_col, end_col)
        wb.save(file_path)
    else:
        # Это уже worksheet
        _style_worksheet(file_path, header_row, start_col, end_col)


def _style_worksheet(worksheet, header_row=1, start_col=1, end_col=None):
    """Применяет стиль к заголовкам одного worksheet."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    if end_col is None:
        end_col = worksheet.max_column

    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="D42626", end_color="D42626", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="FFFFFF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col in range(start_col, end_col + 1):
        cell = worksheet.cell(row=header_row, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = border

    for col in range(start_col, end_col + 1):
        column_letter = get_column_letter(col)
        max_length = 10
        for row in range(1, worksheet.max_row + 1):
            cell_value = worksheet.cell(row=row, column=col).value
            if cell_value:
                max_length = max(max_length, len(str(cell_value)))
        worksheet.column_dimensions[column_letter].width = min(max_length + 2, 60)

    worksheet.freeze_panes = worksheet.cell(row=header_row + 1, column=1)