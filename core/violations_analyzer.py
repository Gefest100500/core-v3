# core/violations_analyzer.py
"""
Трассировщик правил (Анализатор нарушений).

Вход: файл со списком кодов + РТП.
Применяет УПРОЩЁННЫЕ правила (без Пересорта, Хищения и Местного поставщика).

ИЗМЕНЕНИЯ:
- Сбор операций «Инвентаризация» теперь возвращает список:
  [(дата, количество), ...] для каждой конкретной инвентаризации.
"""
import os
import json

import pandas as pd

from utils.logger import log
from utils.parsing import find_column_ci


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

KV_RULES_PATH = os.path.join(DATA_DIR, "kv_rules.json")


DEFAULT_RULES = {
    "box_deviation_pct": 50,
    "mirror_deviation_pct": 25,
    "operation_types": {
        "nevoz": ["Приход•Недовоз внутри компании"],
        "perevoz": [
            "Приход•Перевоз внутри компании",
            "Приход•Неподтверждённый перевоз",
        ],
        "inventory_prefix": "Инвентаризация",
    },
    "values": {"surplus": "Излишек", "deficit": "Недостача"},
    "reasons": {
        "box_surplus": "Коробочный излишек - обычная приемка",
        "box_shortage": "Коробочный недовоз - обычная приемка",
        "mirror": "Нет потерь,  выявлено зеркальное отклонение",
    },
}


def _load_rules():
    if not os.path.exists(KV_RULES_PATH):
        return DEFAULT_RULES
    try:
        with open(KV_RULES_PATH, "r", encoding="utf-8") as f:
            rules = json.load(f)
    except (json.JSONDecodeError, IOError):
        return DEFAULT_RULES
    for key, value in DEFAULT_RULES.items():
        if key not in rules:
            rules[key] = value
    return rules


class ViolationsAnalyzer:
    def __init__(self):
        self.rules = _load_rules()

    # =========================================================
    # ЗАПУСК
    # =========================================================
    def run(self, codes_path, rtp_path, progress_callback=None):
        def report(value, message=None):
            if progress_callback:
                try:
                    progress_callback(value, message)
                except Exception:
                    pass

        r = self.rules
        val = r["values"]
        reasons = r["reasons"]

        # --- 1. Проверка (5%) ---
        report(0.05, "Проверка файлов...")
        if not os.path.isfile(codes_path):
            raise RuntimeError(f"Файл с кодами не найден:\n{codes_path}")
        if not os.path.isfile(rtp_path):
            raise RuntimeError(f"Файл РТП не найден:\n{rtp_path}")

        # --- 2. Чтение кодов (10%) ---
        report(0.10, "Чтение кодов...")
        df_codes = pd.read_excel(codes_path)
        
        code_col_codes = find_column_ci(df_codes, "Код товара")
        if code_col_codes is None:
            code_col_codes = find_column_ci(df_codes, "Код ТП")
        if code_col_codes is None:
            raise RuntimeError(
                f"В файле с кодами нет столбца «Код товара» или «Код ТП».\n"
                f"Столбцы: {list(df_codes.columns)}"
            )

        codes_set = set(
            str(x).strip() for x in df_codes[code_col_codes].dropna().tolist()
            if str(x).strip()
        )
        log.info(f"Кодов загружено: {len(codes_set)}")

        # --- 3. Чтение РТП (20%) ---
        report(0.20, "Чтение РТП...")
        df = pd.read_excel(rtp_path)
        
        code_col = find_column_ci(df, "Код товара") or find_column_ci(df, "Код ТП")
        qty_col = find_column_ci(df, "Количество")
        op_col = find_column_ci(df, "Название типа операции")
        date_col = find_column_ci(df, "Дата операции")
        
        name_col = find_column_ci(df, "Название")
        if name_col is None:
            name_col = find_column_ci(df, "Наименование ТП")
            
        gr20_col = find_column_ci(df, "GR20")
        if gr20_col is None:
            gr20_col = find_column_ci(df, "ГР20")
        if gr20_col is None:
            gr20_col = find_column_ci(df, "ГР 20")

        if not all([code_col, qty_col, op_col]):
            raise RuntimeError(
                f"В РТП нет нужных столбцов (Код, Количество, Операция).\n"
                f"Столбцы: {list(df.columns)}"
            )

        df["_code_str"] = df[code_col].astype(str).str.strip()
        df[qty_col] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0)

        # Фильтруем РТП по кодам из списка
        df_f = df[df["_code_str"].isin(codes_set)].copy()
        
        if len(df_f) == 0:
            report(1.0, "Нет строк по выбранным кодам в РТП")
            return {"success": True, "rows": [], "total_rtp_rows": len(df)}

        # --- 4. Считаем данные (30%) ---
        report(0.30, "Группировка по коду ТП...")

        first_rows = df_f.groupby("_code_str", sort=False).first()
        
        nev = df_f[df_f[op_col].isin(r["operation_types"]["nevoz"])]
        nev_sum = nev.groupby("_code_str")[qty_col].sum().abs()

        per = df_f[df_f[op_col].isin(r["operation_types"]["perevoz"])]
        per_sum = per.groupby("_code_str")[qty_col].sum().abs()

        inv_prefix = r["operation_types"]["inventory_prefix"]
        inv = df_f[df_f[op_col].astype(str).str.startswith(inv_prefix, na=False)]
        inv_sum = inv.groupby("_code_str")[qty_col].sum().abs()

        # Сбор детальной информации по инвентаризации (дата + кол-во)
        inv_details = {}
        if date_col:
            # Группируем по коду и дате, суммируем количество
            inv_grouped = inv.groupby(["_code_str", date_col])[qty_col].sum().reset_index()
            for code in first_rows.index:
                code_inv = inv_grouped[inv_grouped["_code_str"] == code]
                details = []
                for _, row_inv in code_inv.iterrows():
                    d_str = str(row_inv[date_col]).strip()
                    q_val = row_inv[qty_col]
                    details.append((d_str, q_val))
                if details:
                    inv_details[code] = details
        else:
            # Если даты нет, просто суммируем (fallback)
            for code in first_rows.index:
                code_inv = inv[inv["_code_str"] == code]
                if len(code_inv) > 0:
                    inv_details[code] = [("—", code_inv[qty_col].sum())]

        plus = df_f[df_f[qty_col] > 0].groupby("_code_str")[qty_col].sum()
        minus = df_f[df_f[qty_col] < 0].groupby("_code_str")[qty_col].sum().abs()

        total_qty = df_f.groupby("_code_str")[qty_col].sum()

        # --- 5. Применяем правила (50%) ---
        report(0.50, "Применение правил...")

        results = []
        box_pct = r["box_deviation_pct"]
        mirror_pct = r["mirror_deviation_pct"]

        for code in first_rows.index:
            name = first_rows.at[code, name_col] if name_col else ""
            gr20 = first_rows.at[code, gr20_col] if gr20_col else ""
            
            qty = total_qty.get(code, 0)
            
            sign = ""
            if qty < 0:
                sign = val["surplus"]
            elif qty > 0:
                sign = val["deficit"]

            reason = ""
            features = {}

            # 1. Зеркалка
            if code in plus.index and code in minus.index:
                p = plus[code]
                m = minus[code]
                if p > 0 and m > 0:
                    dev = abs(p - m) * 100 / max(p, m)
                    if dev <= mirror_pct:
                        reason = reasons["mirror"]
                        features = {"rule": "mirror", "deviation": f"{dev:.1f}%"}

            # 2. Коробочный (недовоз/перевоз)
            if not reason:
                if code in per_sum.index and code in inv_sum.index:
                    s = per_sum[code]
                    i = inv_sum[code]
                    if s > 0 and i > 0:
                        dev = abs(s - i) * 100 / max(s, i)
                        if dev <= box_pct and sign == val["deficit"]:
                            reason = reasons["box_shortage"]
                            features = {"rule": "box_shortage", "deviation": f"{dev:.1f}%"}
                
                if not reason and code in nev_sum.index and code in inv_sum.index:
                    s = nev_sum[code]
                    i = inv_sum[code]
                    if s > 0 and i > 0:
                        dev = abs(s - i) * 100 / max(s, i)
                        if dev <= box_pct and sign == val["surplus"]:
                            reason = reasons["box_surplus"]
                            features = {"rule": "box_surplus", "deviation": f"{dev:.1f}%"}

            # 3. Обычная приемка (финальное правило)
            if not reason and sign:
                if sign == val["deficit"]:
                    reason = reasons["box_shortage"]
                    features = {"rule": "fallback", "reason": "Правила молчат (Недостача)"}
                elif sign == val["surplus"]:
                    reason = reasons["box_surplus"]
                    features = {"rule": "fallback", "reason": "Правила молчат (Излишек)"}

            if reason:
                # Добавляем детали инвентаризации
                inv_data = inv_details.get(code, [])
                
                results.append({
                    "code": code,
                    "name": str(name),
                    "gr20": str(gr20),
                    "sign": sign,
                    "reason": reason,
                    "features": features,
                    "inv_details": inv_data
                })

        report(1.0, f"Найдено: {len(results)}")
        return {
            "success": True,
            "rows": results,
            "total_rtp_rows": len(df),
        }