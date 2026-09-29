# core/kv_analyzer.py
"""
Анализатор квантов.

Все правила — в data/kv_rules.json. Коды для хищений — в data/steal_codes.json.
Если какого-то файла нет — создаётся дефолтный, работа продолжается.

ТРИ ЖЁСТКИХ ПРАВИЛА (применяются первыми, не перезаписываются):

A1. «Свежие овощи / Свежие фрукты» (высший приоритет)
   - ГР 20 в ["Свежие овощи", "Свежие фрукты"]
   - → «Пересорт на кассе»
   - → Номер документа: пусто

A2. «Сырьё»
   - ГР 20 == "Сырье" ИЛИ Наименование ТП содержит "сырье"
   - И НЕ попало в A1
   - → «Потери ТО (ошибки при работе с позициями сырья и готовой продукции)»
   - → Номер документа: пусто

B. «Местный поставщик»
   - Код в операциях «Приход•Местный» / «Приход•Недовоз от поставщика»
   - И НЕ A1, И НЕ A2
   - → Излишек: «Ошибки в работе (Местный поставщик)» + «Нет номера БФ»
   - → Недостача: «Потери ТО (Местный поставщик)» + «Нет номера БФ»

Остальные правила — только для строк, не попавших ни в A1, ни в A2, ни в B.
"""
import os
import json

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from utils.logger import log
from utils.file_utils import clear_folder


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

KV_RULES_PATH = os.path.join(DATA_DIR, "kv_rules.json")
STEAL_CODES_PATH = os.path.join(DATA_DIR, "steal_codes.json")


# =========================================================
# ДЕФОЛТНЫЕ ПРАВИЛА
# =========================================================
DEFAULT_RULES = {
    "loss_min_rub": 1000.0,
    "box_deviation_pct": 50,
    "mirror_deviation_pct": 25,
    "gr20_fruits_veg": ["Свежие овощи", "Свежие фрукты"],
    "gr20_syre": "Сырье",
    "syre_name_marker": "сырье",
    "operation_types": {
        "local_supplier": [
            "Приход•Местный",
            "Приход•Недовоз от поставщика"
        ],
        "nevoz": [
            "Приход•Недовоз внутри компании"
        ],
        "perevoz": [
            "Приход•Перевоз внутри компании",
            "Приход•Неподтверждённый перевоз"
        ],
        "inventory_prefix": "Инвентаризация"
    },
    "columns": {
        "code": "Код ТП",
        "name": "Наименование ТП",
        "gr20": "ГР 20",
        "loss": "Потери (руб без НДС)",
        "surplus_deficit": "Излишек\\Недостача",
        "reason": "Типовая причина",
        "doc_number": "Номер документа/заявки"
    },
    "values": {
        "surplus": "Излишек",
        "deficit": "Недостача"
    },
    "reasons": {
        "fruits_veg": "Пересорт на кассе",
        "syre": "Потери ТО (ошибки при работе с позициями сырья и готовой продукции)",
        "local_supplier_errors": "Ошибки в работе (Местный поставщик)",
        "local_supplier_losses": "Потери ТО (Местный поставщик)",
        "steal": "Возможно хищение",
        "box_surplus": "Коробочный излишек - обычная приемка",
        "box_shortage": "Коробочный недовоз - обычная приемка",
        "mirror": "Нет потерь,  выявлено зеркальное отклонение"
    },
    "doc_number": {
        "no_bf": "Нет номера БФ",
        "reasons_with_doc": [
            "Коробочный недовоз - обычная приемка",
            "Коробочный излишек - обычная приемка",
            "Ошибки в работе (Местный поставщик)",
            "Потери ТО (Местный поставщик)"
        ],
        "reasons_without_doc": [
            "Пересорт на кассе",
            "Нет потерь,  выявлено зеркальное отклонение",
            "Возможно хищение",
            "Потери ТО (ошибки при работе с позициями сырья и готовой продукции)"
        ]
    },
    "reviewers": ["Ревизор 1", "Ревизор 2"],
    "output": {
        "file_reviewer_1": "Ревизор 1.xlsx",
        "file_reviewer_2": "Ревизор 2.xlsx"
    }
}


def _load_rules():
    """Загружает kv_rules.json. Если файла нет — создаёт дефолтный."""
    if not os.path.exists(KV_RULES_PATH):
        log.warning(f"kv_rules.json не найден — создаю дефолтный: {KV_RULES_PATH}")
        os.makedirs(DATA_DIR, exist_ok=True)
        try:
            with open(KV_RULES_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_RULES, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"Не удалось создать kv_rules.json: {e}")
        return DEFAULT_RULES

    try:
        with open(KV_RULES_PATH, "r", encoding="utf-8") as f:
            rules = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.error(f"Ошибка чтения kv_rules.json: {e}. Использую дефолт.")
        return DEFAULT_RULES

    for key, value in DEFAULT_RULES.items():
        if key not in rules:
            rules[key] = value
    return rules


def _load_steal_codes():
    """Загружает set кодов хищений. Если файла нет — пустой set."""
    if not os.path.exists(STEAL_CODES_PATH):
        log.warning(f"steal_codes.json не найден: {STEAL_CODES_PATH}")
        return set()
    try:
        with open(STEAL_CODES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(str(x) for x in data)
        log.warning("steal_codes.json должен содержать список — игнорирую")
        return set()
    except (json.JSONDecodeError, IOError) as e:
        log.error(f"Ошибка чтения steal_codes.json: {e}")
        return set()


class KvAnalyzer:
    def __init__(self):
        self.rules = _load_rules()
        self.steal_codes = _load_steal_codes()

        log.info(
            f"Инициализация Анализатора КВАНТОВ v2.4 "
            f"(правил: {len(self.rules)}, кодов хищений: {len(self.steal_codes)})"
        )

    # =========================================================
    # ЗАПУСК
    # =========================================================
    def run(self, rtp_path, kv_path, progress_callback=None):
        from config import FOLDERS

        def report(value, message=None):
            if progress_callback:
                try:
                    progress_callback(value, message)
                except Exception:
                    pass

        # --- Сокращения ---
        r = self.rules
        col = r["columns"]
        val = r["values"]
        reasons = r["reasons"]

        col_code = col["code"]
        col_name = col["name"]
        col_gr20 = col["gr20"]
        col_loss = col["loss"]
        col_sd = col["surplus_deficit"]
        col_reason = col["reason"]
        col_doc = col["doc_number"]

        fruits_veg_values = r["gr20_fruits_veg"]
        syre_value = r["gr20_syre"]
        syre_marker = r["syre_name_marker"]

        # --- 1. Очистка папки (5%) ---
        report(0.05, "Очистка папки результатов...")
        clear_folder(FOLDERS["kv"])

        # --- 2. Чтение файлов (20%) ---
        report(0.15, "Чтение РТП.xlsx...")
        df_rtp = pd.read_excel(rtp_path)

        report(0.25, "Чтение Кванты.xlsx...")
        kv = pd.read_excel(kv_path)

        # --- 3. Предобработка (35%) ---
        report(0.35, "Предобработка данных...")
        kv[col_loss] = pd.to_numeric(kv[col_loss], errors="coerce")

        kv = kv[kv[col_loss].abs() >= r["loss_min_rub"]].reset_index(drop=True)

        df_rtp["Количество"] = pd.to_numeric(df_rtp["Количество"], errors="coerce")

        kv[col_reason] = None
        kv[col_doc] = None
        kv["Ревизор"] = None

        # =====================================================
        # ЖЁСТКОЕ ПРАВИЛО A1 — ФРУКТЫ/ОВОЩИ (высший приоритет)
        # =====================================================
        report(0.40, "Жёсткое правило: Свежие овощи / фрукты...")

        fruits_veg_mask = kv[col_gr20].isin(fruits_veg_values)

        kv.loc[fruits_veg_mask, col_reason] = reasons["fruits_veg"]
        kv.loc[fruits_veg_mask, col_doc] = None

        log.info(
            f"Жёсткое правило «Фрукты/овощи»: {int(fruits_veg_mask.sum())} строк"
        )

        # =====================================================
        # ЖЁСТКОЕ ПРАВИЛО A2 — СЫРЬЁ (без пересечения с A1)
        # =====================================================
        report(0.43, "Жёсткое правило: Сырьё...")

        syre_by_gr20 = kv[col_gr20] == syre_value
        syre_by_name = kv[col_name].str.contains(
            syre_marker, case=False, na=False, regex=False
        )
        syre_mask = (syre_by_gr20 | syre_by_name) & ~fruits_veg_mask

        kv.loc[syre_mask, col_reason] = reasons["syre"]
        kv.loc[syre_mask, col_doc] = None

        log.info(
            f"Жёсткое правило «Сырьё»: "
            f"по ГР 20 — {int(syre_by_gr20.sum())}, "
            f"по наименованию — {int(syre_by_name.sum())}, "
            f"всего (без фруктов/овощей) — {int(syre_mask.sum())}"
        )

        # =====================================================
        # ЖЁСТКОЕ ПРАВИЛО B — МЕСТНЫЙ ПОСТАВЩИК
        # =====================================================
        report(0.46, "Жёсткое правило: Местный поставщик...")

        local_ops = r["operation_types"]["local_supplier"]
        local_codes = df_rtp[
            df_rtp["Название типа операции"].isin(local_ops)
        ]["Код товара"].unique()

        log.info(
            f"Местный поставщик: операций {len(local_ops)}, "
            f"уникальных кодов ТП — {len(local_codes)}"
        )

        hard_prior = fruits_veg_mask | syre_mask
        local_mask = kv[col_code].isin(local_codes) & ~hard_prior

        local_surplus_mask = local_mask & (kv[col_sd] == val["surplus"])
        kv.loc[local_surplus_mask, col_reason] = reasons["local_supplier_errors"]
        kv.loc[local_surplus_mask, col_doc] = r["doc_number"]["no_bf"]

        local_deficit_mask = local_mask & (kv[col_sd] == val["deficit"])
        kv.loc[local_deficit_mask, col_reason] = reasons["local_supplier_losses"]
        kv.loc[local_deficit_mask, col_doc] = r["doc_number"]["no_bf"]

        log.info(
            f"Жёсткое правило «Местный поставщик»: "
            f"излишек {int(local_surplus_mask.sum())}, "
            f"недостача {int(local_deficit_mask.sum())}"
        )

        # Общая маска «не трогать дальше»
        hard_mask = fruits_veg_mask | syre_mask | local_mask

        # =====================================================
        # ОСТАЛЬНЫЕ ПРАВИЛА (только для ~hard_mask)
        # =====================================================

        # --- 4. Возможно хищение (55%) ---
        report(0.55, "Анализ хищений...")
        steal_mask = (
            (kv[col_code].isin(self.steal_codes))
            & (kv[col_sd] == val["deficit"])
            & (~hard_mask)
            & kv[col_reason].isna()
        )
        kv.loc[steal_mask, col_reason] = reasons["steal"]

        # --- 5. Недовоз (65%) ---
        report(0.65, "Анализ недовозов...")

        nev = df_rtp[df_rtp["Название типа операции"].isin(
            r["operation_types"]["nevoz"]
        )]
        nev_sum = nev.groupby("Код товара")["Количество"].sum().abs()

        inv_prefix = r["operation_types"]["inventory_prefix"]
        inv_sum = df_rtp[
            df_rtp["Название типа операции"].str.startswith(inv_prefix, na=False)
        ].groupby("Код товара")["Количество"].sum().abs()

        box_pct = r["box_deviation_pct"]

        for code in kv[col_code]:
            if code in nev_sum and code in inv_sum:
                n, i = nev_sum[code], inv_sum[code]
                if n > 0 and i > 0 and abs(n - i) * 100 / max(n, i) <= box_pct:
                    idx_list = kv.index[kv[col_code] == code]
                    if len(idx_list) == 0:
                        continue
                    idx = idx_list[0]
                    if hard_mask.iloc[idx]:
                        continue
                    if kv.at[idx, col_sd] != val["surplus"]:
                        continue
                    if kv.at[idx, col_gr20] in (fruits_veg_values + [syre_value]):
                        continue
                    kv.at[idx, col_reason] = reasons["box_surplus"]

        # --- 6. Перевоз (75%) ---
        report(0.75, "Анализ перевозов...")

        per = df_rtp[df_rtp["Название типа операции"].isin(
            r["operation_types"]["perevoz"]
        )]
        per_sum = per.groupby("Код товара")["Количество"].sum().abs()

        for code in kv[col_code]:
            if code in per_sum and code in inv_sum:
                p, i = per_sum[code], inv_sum[code]
                if p > 0 and i > 0 and abs(p - i) * 100 / max(p, i) <= box_pct:
                    idx_list = kv.index[kv[col_code] == code]
                    if len(idx_list) == 0:
                        continue
                    idx = idx_list[0]
                    if hard_mask.iloc[idx]:
                        continue
                    if kv.at[idx, col_sd] != val["deficit"]:
                        continue
                    if kv.at[idx, col_gr20] in (fruits_veg_values + [syre_value]):
                        continue
                    kv.at[idx, col_reason] = reasons["box_shortage"]

        # --- 7. Зеркальные отклонения (80%) ---
        report(0.80, "Анализ зеркальных отклонений...")

        plus = df_rtp[df_rtp["Количество"] > 0].groupby("Код товара")["Количество"].sum()
        minus = df_rtp[df_rtp["Количество"] < 0].groupby("Код товара")["Количество"].sum().abs()

        mirror_pct = r["mirror_deviation_pct"]

        for code in kv[col_code]:
            if code in plus.index and code in minus.index:
                p, m = plus[code], minus[code]
                if abs(p - m) * 100 / max(p, m) <= mirror_pct:
                    idx_list = kv.index[kv[col_code] == code]
                    if len(idx_list) == 0:
                        continue
                    idx = idx_list[0]
                    if hard_mask.iloc[idx]:
                        continue
                    if not pd.isna(kv.at[idx, col_reason]):
                        continue
                    if kv.at[idx, col_gr20] in (fruits_veg_values + [syre_value]):
                        continue
                    kv.at[idx, col_reason] = reasons["mirror"]

        # --- 8. Финальные правила (85%) ---
        report(0.85, "Применение финальных правил...")

        kv.loc[
            (kv[col_sd] == val["deficit"])
            & (kv[col_reason].isna())
            & (~hard_mask),
            col_reason
        ] = reasons["box_shortage"]

        kv.loc[
            (kv[col_sd] == val["surplus"])
            & (kv[col_reason].isna())
            & (~hard_mask),
            col_reason
        ] = reasons["box_surplus"]

        # Номер документа для причин «с документом»
        doc_with = r["doc_number"]["reasons_with_doc"]
        doc_without = r["doc_number"]["reasons_without_doc"]
        no_bf = r["doc_number"]["no_bf"]

        doc_mask = kv[col_reason].isin(doc_with)
        kv.loc[doc_mask, col_doc] = no_bf

        clean_mask = kv[col_reason].isin(doc_without)
        kv.loc[clean_mask, col_doc] = None

        # --- 9. Распределение по ревизорам (90%) ---
        report(0.90, "Распределение по ревизорам...")

        kv["Сумма_модуль"] = kv[col_loss].abs()
        kv = kv.sort_values("Сумма_модуль", ascending=False).reset_index(drop=True)

        reviewers = r["reviewers"]
        kv["Ревизор"] = [reviewers[i % len(reviewers)] for i in range(len(kv))]
        kv.drop(columns=["Сумма_модуль"], inplace=True)

        rev1 = kv[kv["Ревизор"] == reviewers[0]].drop(columns=["Ревизор"]).copy()
        rev2 = kv[kv["Ревизор"] == reviewers[1]].drop(columns=["Ревизор"]).copy()

        # --- 10. Сохранение (95%) ---
        report(0.95, "Сохранение файлов...")

        out1 = os.path.join(FOLDERS["kv"], r["output"]["file_reviewer_1"])
        out2 = os.path.join(FOLDERS["kv"], r["output"]["file_reviewer_2"])

        rev1.to_excel(out1, index=False)
        rev2.to_excel(out2, index=False)

        self._autofit_columns(out1)
        self._autofit_columns(out2)

        # --- 11. Готово (100%) ---
        report(1.0, "Анализ завершён")
        log.info(f"Анализ квантов завершён. Файлы: {out1}, {out2}")

        return {"success": True, "files": [out1, out2]}

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