# core/violations_analyzer.py
"""
Анализатор Нарушений — каркас.

Пока:
1. Читает шаблон
2. Копирует его в Готовые/Нарушения/ как .xlsx
3. Заменяет ФИО ревизоров (заготовка)
4. Правила будут добавлены позже

ИЗМЕНЕНИЯ:
- Эмодзи из report() убраны
- Убран неиспользуемый импорт shutil
"""
import os
from datetime import datetime

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from config import FOLDERS
from utils.logger import log


# --- Названия столбцов в шаблоне нарушений ---
COL_DISTRICT = "Округ"                    # A
COL_GM_CODE = "Код ГМ"                    # B
COL_GM_NAME = "Название ГМ"               # C
COL_CHECK_DATE = "Дата проверки"          # D
COL_REVIEWER = "ФИО ревизора"             # E
COL_SECTION = "Раздел"                    # F
COL_CRITERION = "Критерий проверки"       # G
COL_SUM = "Сумма выявленного нарушения (при возможности оценить ущерб)"  # H
COL_DETAILS = "Подробно (о выявленном нарушении)"                        # I


class ViolationsAnalyzer:
    def __init__(self):
        log.info("Инициализация Анализатора Нарушений")

    def run(self, rtp_path, template_path, reviewer1, reviewer2,
            progress_callback=None):
        """
        rtp_path      — путь к РТП.xlsx
        template_path — путь к шаблону «Нарушения БП.xls»
        reviewer1     — ФИО первого ревизора
        reviewer2     — ФИО второго ревизора

        Пока — только каркас.
        """

        def report(value, message=None):
            if progress_callback:
                try:
                    progress_callback(value, message)
                except Exception:
                    pass

        # --- 1. Проверка входных файлов (5%) ---
        report(0.05, "Проверка файлов...")

        if not os.path.isfile(rtp_path):
            raise RuntimeError(f"Файл РТП не найден:\n{rtp_path}")
        if not os.path.isfile(template_path):
            raise RuntimeError(f"Файл шаблона не найден:\n{template_path}")

        # --- 2. Чтение РТП (15%) ---
        report(0.15, "Чтение РТП.xlsx...")
        try:
            df_rtp = pd.read_excel(rtp_path)
            log.info(f"РТП: {len(df_rtp)} строк, столбцы: {list(df_rtp.columns)}")
        except Exception as e:
            raise RuntimeError(f"Не удалось прочитать РТП:\n{e}")

        # --- 3. Чтение шаблона (30%) ---
        report(0.30, "Чтение шаблона нарушений...")
        try:
            df_tmpl = pd.read_excel(template_path)
            log.info(f"Шаблон: {len(df_tmpl)} строк, столбцы: {list(df_tmpl.columns)}")
        except Exception as e:
            raise RuntimeError(
                f"Не удалось прочитать шаблон:\n{e}\n\n"
                f"Если файл .xls — установите xlrd: pip install xlrd"
            )

        # --- 4. TODO: правила (здесь будут правила перевозов / недовозов) ---
        report(0.50, "Правила будут добавлены позже...")

        # --- 5. Замена ФИО ревизоров (70%) ---
        report(0.70, "Замена ФИО ревизоров...")
        if COL_REVIEWER in df_tmpl.columns:
            df_tmpl[COL_REVIEWER] = df_tmpl[COL_REVIEWER].astype(object)
            log.info(f"Ревизор 1: {reviewer1}")
            log.info(f"Ревизор 2: {reviewer2}")

        # --- 6. Сохранение (85%) ---
        report(0.85, "Сохранение результата...")
        out_dir = FOLDERS["violations"]
        os.makedirs(out_dir, exist_ok=True)

        date_str = datetime.now().strftime("%d.%m.%Y")
        out_name = f"Нарушения БП {date_str}.xlsx"
        out_path = os.path.join(out_dir, out_name)

        try:
            df_tmpl.to_excel(out_path, index=False)
        except Exception as e:
            raise RuntimeError(f"Не удалось сохранить результат:\n{e}")

        # --- 7. Автоподбор ширины колонок (95%) ---
        report(0.95, "Подгонка ширины колонок...")
        self._autofit_columns(out_path)

        # --- 8. Готово (100%) ---
        report(1.0, "Анализ завершён")
        log.info(f"Анализ нарушений завершён. Файл: {out_path}")

        return {
            "success": True,
            "file": out_path,
            "rtp_rows": len(df_rtp),
            "template_rows": len(df_tmpl),
        }

    # =========================================================
    # ВСПОМОГАТЕЛЬНЫЕ
    # =========================================================
    @staticmethod
    def _autofit_columns(file_path, min_width=8, max_width=60):
        """Подгоняет ширину каждой колонки под самый длинный текст в ней."""
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