# core/pal_analyzer.py
"""
Анализатор паллет.

Читает папку с файлами, имена которых — 6-значные номера паллет
(например, 528573.xls, 528596.xls). Собирает единый свод.

Из каждого файла берутся только столбцы:
  Код товара, Товар, Цена, % от всех, Кол-во до, Кол-во после.
№ паллета подставляется из имени файла.

Результат: один лист «Задания ТСД» с колонками:
  № паллета, Код товара, Товар, Цена, % от всех,
  Кол-во до, Кол-во после, Отклонение, Сумма, Комментарий.
Сумма всегда 0. Все ячейки с границами, столбцы по ширине содержимого.

Дополнительно: файл «Файл инвентаризации.txt» — сводная по коду товара
(сумма отклонений), формат строки: «Код\tОтклонение», без шапки.
"""
import os
import re

import pandas as pd
from openpyxl.styles import Border, Side, Alignment
from openpyxl.utils import get_column_letter

from utils.logger import log
from utils.file_utils import clear_folder, get_base_dir


BASE_DIR = get_base_dir()

# Столбцы, которые берём из исходных файлов
SOURCE_COLUMNS = [
    "Код товара",
    "Товар",
    "Цена",
    "% от всех",
    "Кол-во до",
    "Кол-во после",
]

# Финальные столбцы результата
FINAL_COLUMNS = [
    "№ паллета", "Код товара", "Товар", "Цена", "% от всех",
    "Кол-во до", "Кол-во после", "Отклонение", "Сумма", "Комментарий",
]

# Имя файла — 6 цифр
FILE_NAME_RE = re.compile(r"^\d{6}$")


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
                out_dir = self.config.FOLDERS["pal"]
                clear_folder(out_dir)
            else:
                out_dir = os.path.join(BASE_DIR, "Готовые", "Паллеты")
                clear_folder(out_dir)

            os.makedirs(out_dir, exist_ok=True)

            files = self._collect_files(folder_path)
            if not files:
                raise FileNotFoundError(
                    "В выбранной папке нет файлов с именем из 6 цифр "
                    "(например, 528596.xls)."
                )

            all_frames = []

            for file_name, pallet_number in files:
                full_path = os.path.join(folder_path, file_name)
                df = self._read_file(full_path, file_name, pallet_number)
                if df is not None and not df.empty:
                    all_frames.append(df)

            if not all_frames:
                raise RuntimeError(
                    "Не удалось прочитать ни одного файла с нужными столбцами."
                )

            result_df = pd.concat(all_frames, ignore_index=True)

            out_file = os.path.join(out_dir, "Паллеты.xlsx")
            self._write_result(result_df, out_file)

            inv_file = os.path.join(out_dir, "Файл инвентаризации.txt")
            self._write_inventory_file(result_df, inv_file)

            log.info(f"Сборка паллет завершена. Файл: {out_file}")
            log.info(f"Файл инвентаризации: {inv_file}")

            return {
                "success": True,
                "file": out_file,
                "inventory_file": inv_file,
            }

        except Exception as e:
            log.critical(f"Ошибка при сборке паллет: {e}", exc_info=True)
            raise RuntimeError(f"Ошибка при сборке паллет: {e}")

    # =========================================================
    # ПОИСК ФАЙЛОВ
    # =========================================================
    @staticmethod
    def _collect_files(folder_path):
        """Возвращает список (имя_файла, номер_паллеты), отсортированный по номеру."""
        result = []
        try:
            for name in os.listdir(folder_path):
                base, ext = os.path.splitext(name)
                if ext.lower() not in (".xls", ".xlsx"):
                    continue
                if not FILE_NAME_RE.match(base):
                    continue
                result.append((name, base))
        except (PermissionError, OSError) as e:
            raise RuntimeError(f"Нет доступа к папке: {e}")

        result.sort(key=lambda x: int(x[1]))
        return result

    # =========================================================
    # ЧТЕНИЕ ОДНОГО ФАЙЛА
    # =========================================================
    def _read_file(self, full_path, file_name, pallet_number):
        try:
            df = pd.read_excel(full_path)
        except Exception as e:
            log.warning(f"Не удалось прочитать «{file_name}»: {e}")
            return None

        # Проверяем наличие нужных столбцов
        missing = [c for c in SOURCE_COLUMNS if c not in df.columns]
        if missing:
            raise RuntimeError(
                f"В файле «{file_name}» нет столбцов:\n"
                + "\n".join(f"  • {c}" for c in missing)
                + "\n\nЕсть столбцы: "
                + ", ".join(str(c) for c in df.columns)
            )

        df = df[SOURCE_COLUMNS].copy()

        # Числовые столбцы — к числам
        for col in ("Цена", "% от всех", "Кол-во до", "Кол-во после"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        # Расчёт отклонения (Сумма всегда 0)
        df["Отклонение"] = df["Кол-во до"] - df["Кол-во после"]
        df["Сумма"] = 0.0

        # № паллета — из имени файла
        df.insert(0, "№ паллета", pallet_number)

        # Комментарий — пустой
        df["Комментарий"] = None

        # Финальный порядок колонок
        for col in FINAL_COLUMNS:
            if col not in df.columns:
                df[col] = None

        return df[FINAL_COLUMNS]

    # =========================================================
    # ЗАПИСЬ РЕЗУЛЬТАТА (XLSX)
    # =========================================================
    @staticmethod
    def _write_result(df, out_file):
        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Задания ТСД")

            worksheet = writer.sheets["Задания ТСД"]

            thin = Side(style="thin", color="000000")
            border = Border(left=thin, right=thin, top=thin, bottom=thin)

            for row in worksheet.iter_rows(
                min_row=1, max_row=worksheet.max_row,
                min_col=1, max_col=worksheet.max_column
            ):
                for cell in row:
                    cell.border = border
                    if cell.row == 1:
                        cell.font = cell.font.copy(bold=True)
                        cell.alignment = Alignment(
                            horizontal="center", vertical="center", wrap_text=True
                        )
                    else:
                        cell.alignment = Alignment(vertical="center")

            for col_idx, col_name in enumerate(df.columns, start=1):
                letter = get_column_letter(col_idx)
                max_len = len(str(col_name))
                for val in df[col_name]:
                    if pd.isna(val):
                        continue
                    s = str(val)
                    if len(s) > max_len:
                        max_len = len(s)
                worksheet.column_dimensions[letter].width = min(max_len + 2, 60)

    # =========================================================
    # ЗАПИСЬ ФАЙЛА ИНВЕНТАРИЗАЦИИ (TXT)
    # =========================================================
    @staticmethod
    def _write_inventory_file(df, out_file):
        """Сводная по коду товара: сумма отклонений. Формат: Код<TAB>Отклонение."""
        pivot = (
            df.groupby("Код товара", as_index=False)["Отклонение"]
              .sum()
              .sort_values("Код товара", key=lambda s: s.astype(str))
        )

        lines = []
        for _, row in pivot.iterrows():
            code = str(row["Код товара"]).strip()
            if code.endswith(".0"):
                code = code[:-2]
            deviation = int(round(float(row["Отклонение"])))
            lines.append(f"{code}\t{deviation}")

        text = "\n".join(lines)
        with open(out_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)