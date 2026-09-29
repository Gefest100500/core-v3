# core/brak_util_analyzer.py
"""
Анализатор Брак/Утиль.

Сверяет суммы из двух файлов по номеру:
- Файл 1: «Выборочная проверка актов списания утиля» (Номер + Сумма операции)
- Файл 2: «Операции списания» (Номер документа + Сумма документа)

Допуск по сумме — из config.py: BRAK_UTIL_TOLERANCE.

Чистые функции парсинга — в utils/parsing.py.
"""
import os
import zipfile

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.utils import get_column_letter

from config import FOLDERS, BRAK_UTIL_TOLERANCE
from utils.logger import log
from utils.parsing import norm_number, to_float


COL_NUMBER_F1 = "Номер"
COL_SUM_F1 = "Сумма операции"

COL_NUMBER_F2 = "Номер документа"
COL_SUM_F2 = "Сумма документа"

COL_NO_CHANGES = "Необоснованных изменений в Акте списания нет"
COL_NOTE = "Примечание"


class BrakUtilAnalyzer:
    def __init__(self):
        log.info("Инициализация Анализатора Брак/Утиль")

    # =========================================================
    # ПУБЛИЧНЫЙ ЗАПУСК
    # =========================================================
    def run(self, file1_path, file2_path, gm_name, progress_callback=None):
        def report(value, message=None):
            if progress_callback:
                try:
                    progress_callback(value, message)
                except Exception:
                    pass

        report(0.10, "Чтение файла «Выборочная проверка...»")
        try:
            df1 = pd.read_excel(file1_path, dtype={COL_NUMBER_F1: str})
        except Exception as e:
            raise RuntimeError(f"Не удалось прочитать файл 1:\n{e}")

        report(0.20, "Чтение файла «Операции списания»")
        try:
            df2 = pd.read_excel(file2_path, dtype={COL_NUMBER_F2: str})
        except Exception as e:
            raise RuntimeError(f"Не удалось прочитать файл 2:\n{e}")

        report(0.25, "Проверка структуры файлов...")
        self._validate_columns(df1, df2)

        df1[COL_NO_CHANGES] = df1[COL_NO_CHANGES].astype(object)
        df1[COL_NOTE] = df1[COL_NOTE].astype(object)

        report(0.35, "Сбор данных из «Операций списания»...")
        operations = {}
        for _, row in df2.iterrows():
            num = norm_number(row.get(COL_NUMBER_F2))
            if not num:
                continue
            s = to_float(row.get(COL_SUM_F2))
            if s is None:
                s = 0.0
            operations.setdefault(num, []).append(s)

        operations_sum = {num: sum(vals) for num, vals in operations.items()}

        report(0.50, "Сверка по столбцу «Номер»...")

        results = []
        discrepancies = []

        for idx, row in df1.iterrows():
            num = norm_number(row.get(COL_NUMBER_F1))
            sum1 = to_float(row.get(COL_SUM_F1))
            if sum1 is None:
                sum1 = 0.0

            if not num:
                results.append(("skip", None, None))
                continue

            if num in operations_sum:
                sum2 = operations_sum[num]
                diff = abs(sum1 - sum2)

                if diff > BRAK_UTIL_TOLERANCE:
                    results.append(("mismatch", idx, diff))
                    discrepancies.append({
                        "row": idx,
                        "number": num,
                        "sum1": sum1,
                        "sum2": sum2,
                        "reason": f"Расхождение: {diff:.2f} руб",
                    })
                else:
                    results.append(("ok", idx, None))
                continue

            results.append(("no_in_ops", idx, None))
            discrepancies.append({
                "row": idx,
                "number": num,
                "sum1": sum1,
                "sum2": None,
                "reason": "Нет в операциях",
            })

        report(0.75, "Заполнение столбцов «Да/Нет» и «Примечание»...")
        self._fill_columns(df1, results)

        report(0.85, "Сохранение результата...")
        out_dir = FOLDERS["brak_util"]
        os.makedirs(out_dir, exist_ok=True)

        safe_gm = self._safe_filename(gm_name)
        out_name = f"Выборочная проверка актов списания утиля ГМ {safe_gm}.xlsx"
        out_path = os.path.join(out_dir, out_name)

        df1.to_excel(out_path, index=False)

        report(0.88, "Подгонка ширины колонок...")
        self._autofit_columns(out_path)

        if discrepancies:
            report(0.90, "Подсветка найденных расхождений...")
            self._highlight_discrepancies(out_path, discrepancies)

        report(0.95, "Архивирование результата...")
        zip_path = out_path.replace(".xlsx", ".zip")
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(out_path, arcname=out_name)
        except Exception as e:
            log.warning(f"Не удалось создать архив: {e}")
            zip_path = None

        report(1.0, "Анализ завершён")

        log.info(
            f"Брак/Утиль: проверено {len(df1)} строк, "
            f"расхождений: {len(discrepancies)}"
        )

        return {
            "success": True,
            "file": out_path,
            "zip": zip_path,
            "total": len(df1),
            "discrepancies": discrepancies,
        }

    # =========================================================
    # ВСПОМОГАТЕЛЬНЫЕ
    # =========================================================
    @staticmethod
    def _validate_columns(df1, df2):
        need1 = [COL_NUMBER_F1, COL_SUM_F1, COL_NO_CHANGES, COL_NOTE]
        need2 = [COL_NUMBER_F2, COL_SUM_F2]

        missing1 = [c for c in need1 if c not in df1.columns]
        if missing1:
            raise RuntimeError(
                "В файле «Выборочная проверка...» нет столбцов:\n"
                + "\n".join(f"  • {c}" for c in missing1)
            )

        missing2 = [c for c in need2 if c not in df2.columns]
        if missing2:
            raise RuntimeError(
                "В файле «Операции списания» нет столбцов:\n"
                + "\n".join(f"  • {c}" for c in missing2)
            )

    @staticmethod
    def _safe_filename(name):
        bad = ['/', '\\', ':', '"', '<', '>', '|', '?', '*']
        s = name
        for ch in bad:
            s = s.replace(ch, "_")
        return s.strip() or "без_названия"

    @staticmethod
    def _fill_columns(df1, results):
        for status, idx, _diff in results:
            if idx is None:
                continue
            if status == "ok":
                df1.at[idx, COL_NO_CHANGES] = "Да"
                df1.at[idx, COL_NOTE] = "Нет"
            elif status == "no_in_ops":
                df1.at[idx, COL_NO_CHANGES] = "Нет"
                df1.at[idx, COL_NOTE] = "Нет в операциях"
            elif status == "mismatch":
                df1.at[idx, COL_NO_CHANGES] = "Нет"
                df1.at[idx, COL_NOTE] = "Есть расхождения"

    @staticmethod
    def _autofit_columns(file_path, min_width=8, max_width=60):
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

    @staticmethod
    def _highlight_discrepancies(file_path, discrepancies):
        try:
            wb = load_workbook(file_path)
        except Exception as e:
            log.warning(f"Не удалось открыть файл для подсветки: {e}")
            return

        ws = wb.active

        red_fill = PatternFill(
            start_color="FF5252", end_color="FF5252", fill_type="solid"
        )
        white_bold = Font(color="FFFFFF", bold=True)

        for d in discrepancies:
            excel_row = d["row"] + 2
            for col in range(1, ws.max_column + 1):
                cell = ws.cell(row=excel_row, column=col)
                cell.fill = red_fill
                cell.font = white_bold

        try:
            wb.save(file_path)
        except PermissionError:
            log.warning(
                f"Файл {file_path} занят — не удалось сохранить подсветку. "
                f"Закройте его и запустите снова."
            )