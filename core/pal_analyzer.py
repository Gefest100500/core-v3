# core/pal_analyzer.py
import os
import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from utils.logger import log
from utils.file_utils import clear_folder


class PalAnalyzer:
    def __init__(self, config=None):
        self.config = config

    def run(self, folder_path):
        log.info(f"Запущена сборка паллет. Папка: {folder_path}")

        try:
            if not folder_path or not os.path.isdir(folder_path):
                raise ValueError("Папка с файлами не выбрана или не существует.")

            if self.config:
                clear_folder(self.config.FOLDERS["pal"])
            else:
                clear_folder(os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "Готовые", "Паллеты"
                ))

            files = sorted(
                [f for f in os.listdir(folder_path)
                 if f.endswith((".xlsx", ".xls")) and f[:-5].isdigit()],
                key=lambda x: int(x[:-5])
            )

            if not files:
                raise FileNotFoundError(
                    "В выбранной папке нет файлов формата '1.xlsx', '2.xlsx'..."
                )

            all_frames = []
            total_deviation_sum = 0.0

            for file_name in files:
                full_path = os.path.join(folder_path, file_name)
                df = pd.read_excel(full_path)

                col_map = {
                    '№ паллеты': '№ паллета',
                    'Код товара': 'Код товара',
                    'Товар': 'Товар',
                    'Цена': 'Цена',
                    '% от всех': '% от всех',
                    'Кол-во до': 'Кол-во до',
                    'Кол-во после': 'Кол-во после'
                }
                df.rename(columns=col_map, inplace=True)

                df['Отклонение'] = df['Кол-во до'] - df['Кол-во после']
                df['Сумма'] = df['Отклонение'] * df['Цена']

                total_deviation_sum += df['Сумма'].sum()

                final_cols = [
                    '№ паллета', 'Код товара', 'Товар', 'Цена', '% от всех',
                    'Кол-во до', 'Кол-во после', 'Отклонение', 'Сумма', 'Комментарий'
                ]
                for col in final_cols:
                    if col not in df.columns:
                        df[col] = None

                all_frames.append(df[final_cols])

            result_df = pd.concat(all_frames, ignore_index=True)

            if self.config:
                out_file = os.path.join(self.config.FOLDERS["pal"], "Паллеты.xlsx")
            else:
                out_file = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "Готовые", "Паллеты", "Паллеты.xlsx"
                )

            result_df.to_excel(out_file, index=False)

            # ВНИМАНИЕ: style_excel НЕ вызываем — шапку не красим

            # Автоподбор ширины колонок
            self._autofit_columns(out_file)

            log.info(f"Сборка паллет завершена. Файл: {out_file}")
            return {"success": True, "file": out_file,
                    "total_sum": round(total_deviation_sum, 2)}

        except Exception as e:
            log.critical(f"Ошибка при сборке паллет: {e}", exc_info=True)
            raise RuntimeError(f"Ошибка при сборке паллет: {e}")

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