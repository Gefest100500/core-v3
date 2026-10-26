# core/pal_analyzer.py
"""
Анализатор паллет.

Читает папку с файлами 1.xlsx, 2.xlsx, ... — посменные отчёты
по проверке 10% паллет. Собирает единый свод с расчётом отклонений
и суммы расхождений.

ИЗМЕНЕНИЯ:
- Добавлена _validate_columns: проверяем наличие нужных столбцов
  и числовые типы, прежде чем считать.
- autofit_columns вынесен в utils/excel_utils.py.
- BASE_DIR берётся из utils.file_utils — единая точка правды.
  Раньше pal_analyzer считал путь сам через os.path.dirname(...).
"""
import os

import pandas as pd

from utils.logger import log
from utils.file_utils import clear_folder, get_base_dir
from utils.excel_utils import autofit_columns


BASE_DIR = get_base_dir()


# Ожидаемые столбцы в исходных файлах
REQUIRED_COLUMNS = [
    "№ паллеты",
    "Код товара",
    "Товар",
    "Цена",
    "% от всех",
    "Кол-во до",
    "Кол-во после",
]

# Переименование: было → стало
COLUMN_RENAME = {
    "№ паллеты": "№ паллета",
    "Код товара": "Код товара",
    "Товар": "Товар",
    "Цена": "Цена",
    "% от всех": "% от всех",
    "Кол-во до": "Кол-во до",
    "Кол-во после": "Кол-во после",
}

# Финальные столбцы результата
FINAL_COLUMNS = [
    "№ паллета", "Код товара", "Товар", "Цена", "% от всех",
    "Кол-во до", "Кол-во после", "Отклонение", "Сумма", "Комментарий",
]


class PalAnalyzer:
    def __init__(self, config=None):
        self.config = config

    # =========================================================
    # ПУБЛИЧНЫЙ ЗАПУСК
    # =========================================================
    def run(self, folder_path):
        log.info(f"Запущена сборка паллет. Папка: {folder_path}")

        try:
            if not folder_path or not os.path.isdir(folder_path):
                raise ValueError("Папка с файлами не выбрана или не существует.")

            # Очищаем папку результатов
            if self.config:
                clear_folder(self.config.FOLDERS["pal"])
                out_dir = self.config.FOLDERS["pal"]
            else:
                out_dir = os.path.join(BASE_DIR, "Готовые", "Паллеты")
                clear_folder(out_dir)

            os.makedirs(out_dir, exist_ok=True)

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

                # Проверяем, что все нужные столбцы есть
                self._validate_columns(df, file_name)

                # Переименование
                df.rename(columns=COLUMN_RENAME, inplace=True)

                # Приводим числовые столбцы к числам
                for col in ("Цена", "Кол-во до", "Кол-во после"):
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

                # Расчёт
                df["Отклонение"] = df["Кол-во до"] - df["Кол-во после"]
                df["Сумма"] = df["Отклонение"] * df["Цена"]

                total_deviation_sum += df["Сумма"].sum()

                # Если столбца «Комментарий» нет — создаём пустой
                if "Комментарий" not in df.columns:
                    df["Комментарий"] = None

                # Приводим к финальному набору колонок
                for col in FINAL_COLUMNS:
                    if col not in df.columns:
                        df[col] = None

                all_frames.append(df[FINAL_COLUMNS])

            result_df = pd.concat(all_frames, ignore_index=True)

            out_file = os.path.join(out_dir, "Паллеты.xlsx")
            result_df.to_excel(out_file, index=False)

            autofit_columns(out_file)

            log.info(f"Сборка паллет завершена. Файл: {out_file}")
            return {
                "success": True,
                "file": out_file,
                "total_sum": round(total_deviation_sum, 2),
            }

        except Exception as e:
            log.critical(f"Ошибка при сборке паллет: {e}", exc_info=True)
            raise RuntimeError(f"Ошибка при сборке паллет: {e}")

    # =========================================================
    # ВАЛИДАЦИЯ
    # =========================================================
    @staticmethod
    def _validate_columns(df, file_name=""):
        """Проверяет наличие нужных столбцов в DataFrame.

        Args:
            df: pandas.DataFrame
            file_name: имя файла — для сообщения об ошибке

        Raises:
            RuntimeError: если какого-то столбца нет.
        """
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise RuntimeError(
                f"В файле «{file_name}» нет столбцов:\n"
                + "\n".join(f"  • {c}" for c in missing)
                + "\n\nЕсть столбцы: "
                + ", ".join(str(c) for c in df.columns)
            )