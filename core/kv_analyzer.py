# core/kv_analyzer.py
"""
Анализатор квантов.

Все правила — в data/kv_rules.json. Коды для хищений — в data/steal_codes.json.
Строгая маска причин — в data/kv_reason_schema.json.
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
   - → Номер документа: «Нет номера БФ»

B. «Местный поставщик»
   - Код в операциях «Приход•Местный» / «Приход•Недовоз от поставщика»
   - И НЕ A1, И НЕ A2
   - → Излишек: «Ошибки в работе (Местный поставщик)» + «Нет номера БФ»
   - → Недостача: «Потери ТО (Местный поставщик)» + пусто

Остальные правила — только для строк, не попавших ни в A1, ни в A2, ни в B.

ВАЛИДАЦИЯ:
- После всех правил вызывается validate_reasons(kv, schema).
- Проверяет: причина из списка, знак соответствует, документ соответствует.
- Расхождения — в Logs/core.log + возврат наружу для диалога.
- Excel не трогается: файл сохраняется как обычно.

ИЗМЕНЕНИЯ:
- Три почти одинаковых цикла в run() (коробочный недовоз по недовозам,
  коробочный недовоз по перевозам, зеркальное отклонение) вынесены
  в общий метод _apply_rule_by_code.
  Логика НЕ изменилась: порядок проверок, знак, причина, hard_mask —
  всё один-в-один.
- Общая проверка пропуска строки вынесена в _should_skip_row.
- run() возвращает shadow_rows — список dict-ов для Shadow Engine v0.3.
  Каждая строка содержит метку правила (rule_fired) и признаки:
    tp_code, gr20, sign, reason, doc, loss_amount, name, operation.
  operation — название операции из РТП (подтягивается из df_rtp).
  Shadow сам вычислит уверенность и объяснение.
  Маппинг причина → правило:
    A1 → «Пересорт на кассе»
    A2 → «Потери ТО (...сырья...)»
    B  → «Ошибки в работе (Местный поставщик)» / «Потери ТО (Местный поставщик)»
    steal → «Возможно хищение»
    box → «Коробочный недовоз - обычная приемка» / «Коробочный излишек - обычная приемка»
    mirror → «Нет потерь,  выявлено зеркальное отклонение»
    остальное → None (Shadow пометит как fallback/unknown)
"""
import os
import json

import pandas as pd

from utils.logger import log
from utils.file_utils import clear_folder
from utils.excel_utils import autofit_columns


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

KV_RULES_PATH = os.path.join(DATA_DIR, "kv_rules.json")
STEAL_CODES_PATH = os.path.join(DATA_DIR, "steal_codes.json")
KV_SCHEMA_PATH = os.path.join(DATA_DIR, "kv_reason_schema.json")


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
            "Потери ТО (ошибки при работе с позициями сырья и готовой продукции)"
        ],
        "reasons_without_doc": [
            "Пересорт на кассе",
            "Нет потерь,  выявлено зеркальное отклонение",
            "Возможно хищение",
            "Потери ТО (Местный поставщик)"
        ]
    },
    "reviewers": ["Ревизор 1", "Ревизор 2"],
    "output": {
        "file_reviewer_1": "Ревизор 1.xlsx",
        "file_reviewer_2": "Ревизор 2.xlsx"
    }
}


# =========================================================
# ЗАГРУЗКА JSON
# =========================================================
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


def _load_schema():
    """Загружает kv_reason_schema.json. Если файла нет — возвращает None."""
    if not os.path.exists(KV_SCHEMA_PATH):
        log.warning(f"kv_reason_schema.json не найден: {KV_SCHEMA_PATH}")
        return None
    try:
        with open(KV_SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        log.error(f"Ошибка чтения kv_reason_schema.json: {e}")
        return None

    if not isinstance(schema, dict) or "reasons" not in schema:
        log.warning("kv_reason_schema.json повреждён — пропускаю валидацию")
        return None

    return schema


# =========================================================
# ВАЛИДАЦИЯ
# =========================================================
def validate_reasons(kv, schema, col_reason, col_sd, col_doc):
    """Проверяет каждую строку на соответствие схеме.

    Args:
        kv: DataFrame с результатами.
        schema: словарь из kv_reason_schema.json.
        col_reason, col_sd, col_doc: имена столбцов.

    Returns:
        Список расхождений. Каждое — dict:
        {
            "excel_row": int,      # номер строки в Excel (1-based, +2 из-за заголовка)
            "reason": str,
            "issue": str,          # "unknown_reason" | "wrong_sign" | "wrong_doc"
            "detail": str,         # человеческое описание
        }
    """
    if schema is None:
        return []

    reasons_map = schema.get("reasons", {})
    errors = []

    for idx, row in kv.iterrows():
        reason = row.get(col_reason)
        sign = row.get(col_sd)
        doc = row.get(col_doc)

        # Excel-строка: idx (0-based) + 2 (заголовок + сдвиг)
        excel_row = int(idx) + 2

        if pd.isna(reason) or reason is None:
            errors.append({
                "excel_row": excel_row,
                "reason": "",
                "issue": "unknown_reason",
                "detail": "Типовая причина пустая",
            })
            continue

        reason = str(reason)

        if reason not in reasons_map:
            errors.append({
                "excel_row": excel_row,
                "reason": reason,
                "issue": "unknown_reason",
                "detail": f"Причина «{reason}» отсутствует в маске",
            })
            continue

        expected = reasons_map[reason]
        expected_signs = expected.get("sign", [])
        expected_doc = expected.get("doc")  # может быть None

        # --- Проверка знака ---
        actual_sign = "" if pd.isna(sign) else str(sign)
        if expected_signs and actual_sign not in expected_signs:
            errors.append({
                "excel_row": excel_row,
                "reason": reason,
                "issue": "wrong_sign",
                "detail": (
                    f"Знак «{actual_sign}», ожидался "
                    + " или ".join(f"«{s}»" for s in expected_signs)
                ),
            })

        # --- Проверка документа ---
        actual_doc = None if pd.isna(doc) else (str(doc).strip() or None)
        exp_doc_norm = None if expected_doc is None else str(expected_doc).strip() or None

        if actual_doc != exp_doc_norm:
            if exp_doc_norm is None:
                exp_text = "пусто"
            else:
                exp_text = f"«{exp_doc_norm}»"
            act_text = "пусто" if actual_doc is None else f"«{actual_doc}»"

            errors.append({
                "excel_row": excel_row,
                "reason": reason,
                "issue": "wrong_doc",
                "detail": (
                    f"Документ {act_text}, ожидался {exp_text}"
                ),
            })

    return errors


# =========================================================
# АНАЛИЗАТОР
# =========================================================
class KvAnalyzer:
    def __init__(self):
        self.rules = _load_rules()
        self.steal_codes = _load_steal_codes()
        self.schema = _load_schema()

        log.info(
            f"Инициализация Анализатора КВАНТОВ v2.6 "
            f"(правил: {len(self.rules)}, кодов хищений: {len(self.steal_codes)}, "
            f"маска: {'есть' if self.schema else 'нет'})"
        )

    # =========================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =========================================================
    def _should_skip_row(self, kv, idx, hard_mask, col_reason,
                         fruits_veg_values, syre_value, col_gr20):
        """Проверяет, нужно ли пропустить строку.

        Строка пропускается, если:
        - idx вне диапазона (не должно случаться, но защищаемся);
        - строка попадает в hard_mask (A1, A2, B);
        - ГР 20 входит в fruits_veg_values или syre_value.
        """
        if idx not in kv.index:
            return True

        try:
            if hard_mask.iloc[idx]:
                return True
        except (IndexError, KeyError):
            return True

        gr20 = kv.at[idx, col_gr20]
        if gr20 in (fruits_veg_values + [syre_value]):
            return True

        return False

    def _apply_rule_by_code(
        self,
        kv,
        sum_by_code,
        inv_sum,
        threshold_pct,
        hard_mask,
        col_code,
        col_sd,
        col_reason,
        col_gr20,
        fruits_veg_values,
        syre_value,
        value_sign,
        reason_text,
    ):
        """Применяет правило по коду ТП: сравнивает сумму из операций
        с суммой из инвентаризации.
        """
        applied = 0
        val_sd_col = kv[col_sd]

        for code in kv[col_code]:
            if code not in sum_by_code.index:
                continue
            if code not in inv_sum.index:
                continue

            s = sum_by_code[code]
            i = inv_sum[code]

            if not (s > 0 and i > 0):
                continue

            if abs(s - i) * 100 / max(s, i) > threshold_pct:
                continue

            idx_list = kv.index[kv[col_code] == code]
            if len(idx_list) == 0:
                continue

            idx = idx_list[0]

            if self._should_skip_row(
                kv, idx, hard_mask, col_reason,
                fruits_veg_values, syre_value, col_gr20
            ):
                continue

            if val_sd_col.at[idx] != value_sign:
                continue

            if not pd.isna(kv.at[idx, col_reason]):
                continue

            kv.at[idx, col_reason] = reason_text
            applied += 1

        return applied

    def _build_shadow_rows(
        self,
        kv,
        df_rtp,
        col_code,
        col_name,
        col_gr20,
        col_sd,
        col_reason,
        col_doc,
        col_loss,
        reasons,
    ):
        """Готовит строки для Shadow Engine v0.3.

        Каждая строка — dict:
            {
                "rtp":              "",
                "tp_code":          str,
                "date":             "",
                "rule_fired":       "A1" | "A2" | "B" | "steal" | "box" | "mirror" | None,
                "rule_confidence":  None,
                "name":             str,
                "gr20":             str,
                "sign":             str,
                "reason":           str,
                "doc":              str,
                "loss_amount":      float,
                "operation":        str,  # название операции из РТП
            }
        """
        # Карта причина → метка правила
        reason_to_rule = {
            reasons.get("fruits_veg"): "A1",
            reasons.get("syre"): "A2",
            reasons.get("local_supplier_errors"): "B",
            reasons.get("local_supplier_losses"): "B",
            reasons.get("steal"): "steal",
            reasons.get("box_surplus"): "box",
            reasons.get("box_shortage"): "box",
            reasons.get("mirror"): "mirror",
        }

        # Словарь: код ТП → название операции из РТП
        # Берём первую операцию для каждого кода
        operation_map = {}
        try:
            if df_rtp is not None and not df_rtp.empty:
                for _, r in df_rtp.iterrows():
                    code = str(r.get("Код товара", "")).strip()
                    if not code or code in operation_map:
                        continue
                    op = r.get("Название типа операции", "")
                    if pd.notna(op):
                        operation_map[code] = str(op).strip()
        except Exception:
            pass

        rows = []
        for idx, r in kv.iterrows():
            reason = r.get(col_reason)
            reason_str = "" if pd.isna(reason) else str(reason)

            rule_fired = reason_to_rule.get(reason_str)

            loss_amount = r.get(col_loss)
            if pd.isna(loss_amount):
                loss_amount = 0.0
            else:
                try:
                    loss_amount = float(loss_amount)
                except (ValueError, TypeError):
                    loss_amount = 0.0

            tp_code = str(r.get(col_code, "")).strip()
            operation = operation_map.get(tp_code, "")

            rows.append({
                "rtp": "",
                "tp_code": tp_code,
                "date": "",
                "rule_fired": rule_fired,
                "rule_confidence": None,
                "name": "" if pd.isna(r.get(col_name)) else str(r.get(col_name)),
                "gr20": "" if pd.isna(r.get(col_gr20)) else str(r.get(col_gr20)),
                "sign": "" if pd.isna(r.get(col_sd)) else str(r.get(col_sd)),
                "reason": reason_str,
                "doc": "" if pd.isna(r.get(col_doc)) else str(r.get(col_doc)),
                "loss_amount": loss_amount,
                "operation": operation,
            })
        return rows

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
        # ЖЁСТКОЕ ПРАВИЛО A1 — ФРУКТЫ/ОВОЩИ
        # =====================================================
        report(0.40, "Жёсткое правило: Свежие овощи / фрукты...")

        fruits_veg_mask = kv[col_gr20].isin(fruits_veg_values)

        kv.loc[fruits_veg_mask, col_reason] = reasons["fruits_veg"]
        kv.loc[fruits_veg_mask, col_doc] = None

        log.info(
            f"Жёсткое правило «Фрукты/овощи»: {int(fruits_veg_mask.sum())} строк"
        )

        # =====================================================
        # ЖЁСТКОЕ ПРАВИЛО A2 — СЫРЬЁ
        # =====================================================
        report(0.43, "Жёсткое правило: Сырьё...")

        syre_by_gr20 = kv[col_gr20] == syre_value
        syre_by_name = kv[col_name].str.contains(
            syre_marker, case=False, na=False, regex=False
        )
        syre_mask = (syre_by_gr20 | syre_by_name) & ~fruits_veg_mask

        kv.loc[syre_mask, col_reason] = reasons["syre"]
        kv.loc[syre_mask, col_doc] = r["doc_number"]["no_bf"]

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
        kv.loc[local_deficit_mask, col_doc] = None

        log.info(
            f"Жёсткое правило «Местный поставщик»: "
            f"излишек {int(local_surplus_mask.sum())}, "
            f"недостача {int(local_deficit_mask.sum())}"
        )

        hard_mask = fruits_veg_mask | syre_mask | local_mask

        # =====================================================
        # ОСТАЛЬНЫЕ ПРАВИЛА
        # =====================================================

        # --- 4. Возможно хищение ---
        report(0.55, "Анализ хищений...")
        steal_mask = (
            (kv[col_code].isin(self.steal_codes))
            & (kv[col_sd] == val["deficit"])
            & (~hard_mask)
            & kv[col_reason].isna()
        )
        kv.loc[steal_mask, col_reason] = reasons["steal"]

        # --- 5. Недовоз ---
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

        applied_surplus = self._apply_rule_by_code(
            kv=kv,
            sum_by_code=nev_sum,
            inv_sum=inv_sum,
            threshold_pct=box_pct,
            hard_mask=hard_mask,
            col_code=col_code,
            col_sd=col_sd,
            col_reason=col_reason,
            col_gr20=col_gr20,
            fruits_veg_values=fruits_veg_values,
            syre_value=syre_value,
            value_sign=val["surplus"],
            reason_text=reasons["box_surplus"],
        )
        log.info(f"Коробочный излишек (недовоз): {applied_surplus} строк")

        # --- 6. Перевоз ---
        report(0.75, "Анализ перевозов...")

        per = df_rtp[df_rtp["Название типа операции"].isin(
            r["operation_types"]["perevoz"]
        )]
        per_sum = per.groupby("Код товара")["Количество"].sum().abs()

        applied_deficit = self._apply_rule_by_code(
            kv=kv,
            sum_by_code=per_sum,
            inv_sum=inv_sum,
            threshold_pct=box_pct,
            hard_mask=hard_mask,
            col_code=col_code,
            col_sd=col_sd,
            col_reason=col_reason,
            col_gr20=col_gr20,
            fruits_veg_values=fruits_veg_values,
            syre_value=syre_value,
            value_sign=val["deficit"],
            reason_text=reasons["box_shortage"],
        )
        log.info(f"Коробочный недовоз (перевоз): {applied_deficit} строк")

        # --- 7. Зеркальные отклонения ---
        report(0.80, "Анализ зеркальных отклонений...")

        plus = df_rtp[df_rtp["Количество"] > 0].groupby("Код товара")["Количество"].sum()
        minus = df_rtp[df_rtp["Количество"] < 0].groupby("Код товара")["Количество"].sum().abs()

        mirror_pct = r["mirror_deviation_pct"]

        applied_mirror = self._apply_rule_by_code(
            kv=kv,
            sum_by_code=plus,
            inv_sum=minus,
            threshold_pct=mirror_pct,
            hard_mask=hard_mask,
            col_code=col_code,
            col_sd=col_sd,
            col_reason=col_reason,
            col_gr20=col_gr20,
            fruits_veg_values=fruits_veg_values,
            syre_value=syre_value,
            value_sign=None,
            reason_text=reasons["mirror"],
        )
        log.info(f"Зеркальное отклонение: {applied_mirror} строк")

        # --- 8. Финальные правила ---
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

        # Номер документа
        doc_with = r["doc_number"]["reasons_with_doc"]
        doc_without = r["doc_number"]["reasons_without_doc"]
        no_bf = r["doc_number"]["no_bf"]

        doc_mask = kv[col_reason].isin(doc_with)
        kv.loc[doc_mask, col_doc] = no_bf

        clean_mask = kv[col_reason].isin(doc_without)
        kv.loc[clean_mask, col_doc] = None

        # --- 9. Распределение по ревизорам ---
        report(0.90, "Распределение по ревизорам...")

        kv["Сумма_модуль"] = kv[col_loss].abs()
        kv = kv.sort_values("Сумма_модуль", ascending=False).reset_index(drop=True)

        reviewers = r["reviewers"]
        kv["Ревизор"] = [reviewers[i % len(reviewers)] for i in range(len(kv))]
        kv.drop(columns=["Сумма_модуль"], inplace=True)

        rev1 = kv[kv["Ревизор"] == reviewers[0]].drop(columns=["Ревизор"]).copy()
        rev2 = kv[kv["Ревизор"] == reviewers[1]].drop(columns=["Ревизор"]).copy()

        # =====================================================
        # ВАЛИДАЦИЯ ПО МАСКЕ
        # =====================================================
        report(0.92, "Проверка по маске...")
        validation_errors = validate_reasons(
            kv, self.schema, col_reason, col_sd, col_doc
        )

        if validation_errors:
            log.warning(
                f"Валидация по маске: найдено {len(validation_errors)} расхождений"
            )
            for err in validation_errors[:20]:
                log.warning(
                    f"  строка {err['excel_row']}: {err['detail']} "
                    f"(причина: «{err['reason']}»)"
                )
            if len(validation_errors) > 20:
                log.warning(f"  ... и ещё {len(validation_errors) - 20}")
        else:
            log.info("Валидация по маске: расхождений нет")

        # =====================================================
        # SHADOW ROWS — готовим для ml.shadow.run_shadow()
        # =====================================================
        report(0.94, "Подготовка данных для Shadow Engine...")

        shadow_rows = self._build_shadow_rows(
            kv=kv,
            df_rtp=df_rtp,
            col_code=col_code,
            col_name=col_name,
            col_gr20=col_gr20,
            col_sd=col_sd,
            col_reason=col_reason,
            col_doc=col_doc,
            col_loss=col_loss,
            reasons=reasons,
        )

        # --- 10. Сохранение (95%) ---
        report(0.95, "Сохранение файлов...")

        out1 = os.path.join(FOLDERS["kv"], r["output"]["file_reviewer_1"])
        out2 = os.path.join(FOLDERS["kv"], r["output"]["file_reviewer_2"])

        rev1.to_excel(out1, index=False)
        rev2.to_excel(out2, index=False)

        autofit_columns(out1)
        autofit_columns(out2)

        # --- 11. Готово (100%) ---
        report(1.0, "Анализ завершён")
        log.info(f"Анализ квантов завершён. Файлы: {out1}, {out2}")

        return {
            "success": True,
            "files": [out1, out2],
            "validation_errors": validation_errors,
            "shadow_rows": shadow_rows,
        }