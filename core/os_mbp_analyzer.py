# core/os_mbp_analyzer.py
"""
Сборка свода ОС и МБП.

Парсер ИНВ-1 (инвентаризационная опись):
- Находит строку-шапку по маркеру «количество, шт.»
- Ищет ВСЕ столбцы «количество, шт.» и выбирает тот, где сумма > 0
  (в ИНВ-1 два таких столбца: «Фактическое наличие» и «По данным
   бухгалтерского учета». Заполнен обычно один из них.)
- Сдвигает данные на 3 строки ниже шапки (подшапка + нумерация + 1)
- Фильтрует мусор: шапку, нумерацию, итоговые строки
- Группирует по наименованию, суммирует количество

ИЗМЕНЕНИЯ:
- BASE_DIR берётся из utils.file_utils — единая точка правды.
- autofit_columns вынесен в utils/excel_utils.py
"""
import os
import json
import re

import pandas as pd
from openpyxl.utils import get_column_letter

from utils.logger import log
from utils.file_utils import clear_folder, get_base_dir
from utils.excel_utils import autofit_columns


BASE_DIR = get_base_dir()

UNWANTED_PATH = os.path.join(BASE_DIR, "data", "unwanted.json")


# Маркер нижнего уровня шапки
HEADER_MARKER = "количество, шт"

NAME_KEYWORDS = [
    "наименование, назначение",
    "наименование,",
    "наименование",
]

QTY_KEYWORDS = [
    "количество, шт",
    "количество,шт",
]

TOTAL_MARKERS = [
    "итого",
    "итого по странице",
    "итого по описи",
    "всего",
]


class OsMbpAnalyzer:
    def __init__(self, config=None):
        self.config = config

        self.unwanted = []
        if os.path.exists(UNWANTED_PATH):
            try:
                with open(UNWANTED_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    self.unwanted = [str(x).lower().strip() for x in raw if x]
                log.info(f"unwanted.json загружен: {len(self.unwanted)} позиций")
            except Exception as e:
                log.warning(f"Не удалось загрузить unwanted.json: {e}")
        else:
            log.warning(f"unwanted.json не найден: {UNWANTED_PATH}")

    # =========================================================
    # ПУБЛИЧНЫЙ ЗАПУСК
    # =========================================================
    def run(self, os_files, mbp_files, remove_unwanted_flag):
        log.info(
            f"Сборка ОС/МБП: os_files={len(os_files)}, "
            f"mbp_files={len(mbp_files)}, remove_unwanted={remove_unwanted_flag}"
        )

        if self.config and hasattr(self.config, "FOLDERS"):
            out_dir = self.config.FOLDERS["os_mbp"]
        else:
            out_dir = os.path.join(BASE_DIR, "Готовые", "ОС_МБП")

        clear_folder(out_dir)
        os.makedirs(out_dir, exist_ok=True)

        df_os = self._build_svod(os_files, "ОС", remove_unwanted_flag)
        os_path = os.path.join(out_dir, "ОС.xlsx")
        df_os.to_excel(os_path, index=False)
        autofit_columns(os_path)
        log.info(f"ОС сохранён: {os_path} ({len(df_os)} строк)")

        df_mbp = self._build_svod(mbp_files, "МБП", remove_unwanted_flag)
        mbp_path = os.path.join(out_dir, "МБП.xlsx")
        df_mbp.to_excel(mbp_path, index=False)
        autofit_columns(mbp_path)
        log.info(f"МБП сохранён: {mbp_path} ({len(df_mbp)} строк)")

        return {
            "success": True,
            "files": [os_path, mbp_path],
            "os_rows": len(df_os),
            "mbp_rows": len(df_mbp),
        }

    # =========================================================
    # СБОРКА СВОДА
    # =========================================================
    def _build_svod(self, files, default_category, remove_unwanted):
        all_frames = []

        for path in files:
            if not path or not os.path.isfile(path):
                log.warning(f"Файл не найден: {path}")
                continue

            category = self._detect_category(path, default_category)

            try:
                df = self._parse_inv1(path, category)
            except Exception as e:
                log.exception(f"Ошибка парсинга {path}: {e}")
                continue

            if df is None or df.empty:
                log.warning(f"Пустой результат парсинга: {path}")
                continue

            all_frames.append(df)

        if not all_frames:
            log.warning("Нет данных для свода — возвращаю пустой DataFrame")
            return pd.DataFrame(columns=["Категория", "Наименование", "Количество"])

        combined = pd.concat(all_frames, ignore_index=True)

        if remove_unwanted and self.unwanted:
            combined = self._filter_unwanted(combined)
            log.info(f"После фильтра мусора: {len(combined)} строк")

        grouped = (
            combined
            .groupby(["Категория", "Наименование"], as_index=False)["Количество"]
            .sum()
        )

        grouped = grouped.sort_values(
            ["Категория", "Наименование"],
            key=lambda col: col.str.lower()
        ).reset_index(drop=True)

        log.info(f"Свод {default_category}: {len(grouped)} уникальных позиций")

        return grouped

    # =========================================================
    # ОПРЕДЕЛЕНИЕ КАТЕГОРИИ
    # =========================================================
    @staticmethod
    def _detect_category(path, default):
        name_lower = os.path.basename(path).lower()

        if "мбп" in name_lower:
            return "МБП"
        if "забаланс" in name_lower:
            return "Забаланс"

        return default

    # =========================================================
    # ПАРСЕР ИНВ-1
    # =========================================================
    def _parse_inv1(self, file_path, category):
        log.info(f"Парсинг ИНВ-1: {os.path.basename(file_path)}")

        df_raw = pd.read_excel(file_path, header=None)
        log.info(f"Прочитано строк: {len(df_raw)}, столбцов: {len(df_raw.columns)}")

        # 1. Ищем строку-шапку (по маркеру «количество, шт.»)
        header_row_idx = self._find_header_row(df_raw)
        if header_row_idx is None:
            raise RuntimeError(
                "Не найдена строка-шапка ИНВ-1 (нет маркера «количество, шт.»)"
            )
        log.info(
            f"Строка-шапка найдена: индекс {header_row_idx} "
            f"(Excel: {header_row_idx + 1})"
        )

        # 2. Определяем столбец наименования
        name_col_idx = self._find_column(
            df_raw, header_row_idx, NAME_KEYWORDS, "Наименование"
        )
        if name_col_idx is None:
            raise RuntimeError("Не найден столбец «Наименование»")

        # 3. Определяем столбец количества — ищем ВСЕ «количество, шт.»
        #    и выбираем тот, где сумма > 0
        qty_candidates = self._find_qty_columns(df_raw, header_row_idx)
        if not qty_candidates:
            raise RuntimeError("Не найдены столбцы «количество, шт.»")

        # 4. Данные начинаются на 3 строки ниже шапки:
        #    header_row_idx      — подшапка (количество, шт.)
        #    header_row_idx + 1  — нумерация столбцов (1, 2, 3...)
        #    header_row_idx + 2  — первая строка данных (№1, №2, ...)
        data_start = header_row_idx + 2
        df_data = df_raw.iloc[data_start:].copy()

        # 5. Маска наименований
        names = df_data.iloc[:, name_col_idx].astype(str).str.strip()

        mask_name = (
            names.notna()
            & (names != "")
            & (names.str.lower() != "nan")
        )

        # Исключаем шапку (если попала)
        mask_header = ~names.str.lower().str.contains(
            "наименование, назначение", na=False
        )

        # Исключаем итоговые строки
        mask_total = ~names.str.lower().str.contains(
            "|".join(TOTAL_MARKERS), na=False, regex=True
        )

        # Исключаем строки, где наименование — просто число (нумерация)
        mask_number = ~names.str.match(r"^\d+(\.\d+)?$", na=False)

        mask = mask_name & mask_header & mask_total & mask_number

        # 6. Выбираем лучший столбец количества
        best_qty_col = None
        best_sum = -1
        best_qty_data = None

        for qty_col_idx in qty_candidates:
            qty_series = pd.to_numeric(
                df_data.loc[mask, df_data.columns[qty_col_idx]],
                errors="coerce"
            ).fillna(0)
            total = int(qty_series.sum())

            log.info(
                f"  Кандидат {get_column_letter(qty_col_idx + 1)} "
                f"(индекс {qty_col_idx}): сумма = {total}"
            )

            if total > best_sum:
                best_sum = total
                best_qty_col = qty_col_idx
                best_qty_data = qty_series

        if best_qty_col is None:
            raise RuntimeError("Не удалось выбрать столбец «Количество»")

        log.info(
            f"Столбцы: Наименование = {get_column_letter(name_col_idx + 1)} "
            f"(индекс {name_col_idx}), "
            f"Количество = {get_column_letter(best_qty_col + 1)} "
            f"(индекс {best_qty_col})"
        )

        log.info(f"Строк с данными: {int(mask.sum())}")

        # 7. Собираем результат
        result = pd.DataFrame()
        result["Наименование"] = names[mask].values
        result["Количество"] = best_qty_data.values.astype(int)
        result["Категория"] = category

        result["Наименование"] = result["Наименование"].apply(self._clean_name)
        result = result[result["Наименование"] != ""].reset_index(drop=True)

        total_qty = int(result["Количество"].sum())

        if len(result) > 0 and total_qty == 0:
            log.warning(
                f"⚠ Столбец «Количество» выбран неверно: "
                f"{len(result)} строк, но сумма = 0."
            )

        log.info(
            f"Итог по {os.path.basename(file_path)}: "
            f"{len(result)} строк, "
            f"сумма количества = {total_qty}"
        )

        return result[["Категория", "Наименование", "Количество"]]

    # =========================================================
    # ПОИСК ШАПКИ
    # =========================================================
    @staticmethod
    def _find_header_row(df_raw):
        """Ищет строку с маркером «количество, шт.» (подшапка ИНВ-1)."""
        for idx in range(min(len(df_raw), 100)):
            row = df_raw.iloc[idx]

            row_str = " ".join(
                str(x).lower().strip()
                for x in row
                if pd.notna(x)
            ).replace("\n", " ")

            if HEADER_MARKER in row_str:
                return idx

        return None

    # =========================================================
    # ПОИСК СТОЛБЦА
    # =========================================================
    @staticmethod
    def _find_column(df_raw, header_row_idx, keywords, label):
        """Ищет столбец по ключевым словам в 2 уровнях шапки."""
        header_parts = []
        for offset in (-1, 0, 1):
            row_idx = header_row_idx + offset
            if row_idx < 0 or row_idx >= len(df_raw):
                continue
            row = df_raw.iloc[row_idx]
            for col_idx, value in enumerate(row):
                if pd.notna(value):
                    text = str(value).lower().strip().replace("\n", " ")
                    header_parts.append((col_idx, text))

        for keyword in keywords:
            keyword_lower = keyword.lower()
            for col_idx, text in header_parts:
                if keyword_lower in text:
                    return col_idx

        log.warning(f"Столбец «{label}» не найден по ключам: {keywords}")
        return None

    # =========================================================
    # ПОИСК ВСЕХ СТОЛБЦОВ «КОЛИЧЕСТВО, ШТ.»
    # =========================================================
    @staticmethod
    def _find_qty_columns(df_raw, header_row_idx):
        """Ищет ВСЕ столбцы с «количество, шт.» в шапке.

        В ИНВ-1 таких столбцов два:
        - «Фактическое наличие → количество, шт.»
        - «По данным бух. учёта → количество, шт.»
        """
        candidates = []

        for offset in (-1, 0, 1):
            row_idx = header_row_idx + offset
            if row_idx < 0 or row_idx >= len(df_raw):
                continue
            row = df_raw.iloc[row_idx]
            for col_idx, value in enumerate(row):
                if pd.notna(value):
                    text = str(value).lower().strip().replace("\n", " ")
                    if any(kw in text for kw in QTY_KEYWORDS):
                        if col_idx not in candidates:
                            candidates.append(col_idx)

        return sorted(candidates)

    # =========================================================
    # ЧИСТКА НАИМЕНОВАНИЯ
    # =========================================================
    @staticmethod
    def _clean_name(name):
        if not name:
            return ""

        s = str(name).strip()
        s = s.replace("\n", " ").replace("\r", " ")
        s = re.sub(r"\s+", " ", s)

        return s

    # =========================================================
    # ФИЛЬТР МУСОРА
    # =========================================================
    def _filter_unwanted(self, df):
        if df.empty or not self.unwanted:
            return df

        def is_unwanted(name):
            name_lower = str(name).lower()
            for word in self.unwanted:
                if word and word in name_lower:
                    return True
            return False

        mask = ~df["Наименование"].apply(is_unwanted)
        return df[mask].reset_index(drop=True)