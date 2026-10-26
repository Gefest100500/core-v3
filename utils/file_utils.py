# utils/file_utils.py
"""
Утилиты для работы с файлами и папками.

Единая точка правды для базовых директорий проекта:
- get_base_dir()      — корень проекта (или папка рядом с .exe)
- get_data_dir()      — %LOCALAPPDATA%/Core_V3_0/data (fallback: data/)
- get_logs_dir()      — Logs/ (fallback, если LOCALAPPDATA недоступна)
- get_input_dir()     — Файлы/
- get_generated_dir() — Готовые/
- get_temp_dir()      — temp/

Работает и как скрипт, и как .exe (PyInstaller).

ИЗМЕНЕНИЯ:
- get_output_dir() переименован в get_generated_dir() — но старый
  алиас оставлен для совместимости.
- clear_folder теперь логирует: сколько удалено, сколько не удалось.
  Раньше ошибки доступа тихо игнорировались.
- get_data_dir() теперь возвращает %LOCALAPPDATA%/Core_V3_0/data
  (fallback: <корень проекта>/data). Данные ревизора не теряются
  при установке в Program Files.
"""
import sys
import os
import shutil
from pathlib import Path

from utils.logger import log


# =========================================================
# БАЗОВАЯ ДИРЕКТОРИЯ
# =========================================================
def get_base_dir() -> str:
    """Возвращает базовую директорию проекта.

    - Если запущено как .exe (PyInstaller) — папка рядом с .exe
    - Если обычный скрипт — корень проекта (где main.py)

    ВАЖНО: это ЕДИНСТВЕННАЯ точка правды. Все остальные модули
    должны использовать эту функцию, а не считать BASE_DIR сами.
    """
    if getattr(sys, "frozen", False):
        # .exe — папка рядом с Core.exe
        return str(Path(sys.executable).resolve().parent)
    else:
        # Скрипт — корень проекта (где main.py)
        return str(Path(__file__).resolve().parent.parent)


# =========================================================
# ПАПКА ДАННЫХ (%LOCALAPPDATA%)
# =========================================================
def get_app_data_root() -> str:
    """Возвращает корень данных приложения.

    Приоритет:
    1. %LOCALAPPDATA%/Core_V3_0 — стандартное место (есть права на запись)
    2. <корень проекта> — fallback, если LOCALAPPDATA недоступна

    Папка НЕ создаётся здесь — это делает get_data_dir().
    """
    try:
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata and os.path.isdir(local_appdata):
            return os.path.join(local_appdata, "Core_V3_0")
    except (OSError, PermissionError):
        pass

    return get_base_dir()


def get_data_dir() -> str:
    """Папка для JSON-данных. Создаётся при первом вызове.

    Основное место: %LOCALAPPDATA%/Core_V3_0/data
    Fallback: <корень проекта>/data
    """
    path = os.path.join(get_app_data_root(), "data")
    os.makedirs(path, exist_ok=True)
    return path


# =========================================================
# СТАНДАРТНЫЕ ПАПКИ
# =========================================================
def get_logs_dir() -> str:
    """Папка для логов (Logs/). Создаётся при первом вызове.

    ВАЖНО: основная логика логов — в utils/logger.py, которая
    пишет в %LOCALAPPDATA%/Core/Logs. Эта функция — fallback,
    если LOCALAPPDATA недоступна.
    """
    path = os.path.join(get_base_dir(), "Logs")
    os.makedirs(path, exist_ok=True)
    return path


def get_input_dir() -> str:
    """Папка входных файлов (Файлы/). Создаётся при первом вызове."""
    path = os.path.join(get_base_dir(), "Файлы")
    os.makedirs(path, exist_ok=True)
    return path


def get_generated_dir() -> str:
    """Папка результатов (Готовые/). Создаётся при первом вызове.

    Основная папка для всех результатов анализа.
    """
    path = os.path.join(get_base_dir(), "Готовые")
    os.makedirs(path, exist_ok=True)
    return path


def get_output_dir() -> str:
    """Алиас для get_generated_dir() — для совместимости."""
    return get_generated_dir()


def get_temp_dir() -> str:
    """Папка временных файлов (temp/). Создаётся при первом вызове."""
    path = os.path.join(get_base_dir(), "temp")
    os.makedirs(path, exist_ok=True)
    return path


# =========================================================
# ОЧИСТКА ПАПКИ
# =========================================================
def clear_folder(folder_path):
    """Очищает папку.

    Возвращает:
        (removed, failed) — сколько удалено, сколько не удалось.

    Логирует результат:
    - если всё удалено — debug
    - если что-то не удалось — warning с количеством
    - если папки нет — debug
    """
    if not os.path.isdir(folder_path):
        log.debug(f"clear_folder: папки нет — {folder_path}")
        return (0, 0)

    removed = 0
    failed = 0

    try:
        entries = os.listdir(folder_path)
    except (OSError, PermissionError) as e:
        log.warning(f"clear_folder: не удалось прочитать {folder_path}: {e}")
        return (0, 0)

    for entry in entries:
        full_path = os.path.join(folder_path, entry)
        try:
            if os.path.isfile(full_path) or os.path.islink(full_path):
                os.remove(full_path)
                removed += 1
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
                removed += 1
        except (OSError, PermissionError) as e:
            failed += 1
            log.debug(f"clear_folder: не удалось удалить {full_path}: {e}")

    if failed:
        log.warning(
            f"clear_folder: {folder_path} — удалено {removed}, "
            f"не удалось {failed}"
        )
    else:
        log.debug(f"clear_folder: {folder_path} — удалено {removed}")

    return (removed, failed)


# =========================================================
# СТИЛИЗАЦИЯ EXCEL
# =========================================================
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