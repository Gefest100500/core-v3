# ui/frames/inventory_frame.py
r"""
Инвентаризация.

ИЗМЕНЕНИЯ:
- Прогресс-бары (по дням и по чек-листу) теперь СЕРЫЕ (в едином стиле).
- Убран зелёный цвет из процента чек-листа.
"""
import re
from datetime import date, datetime

from PyQt6.QtCore import Qt, QStringListModel, QTimer, QDate
from PyQt6.QtGui import QTextCharFormat, QColor, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QCheckBox, QCompleter, QLineEdit,
    QProgressBar, QDateEdit, QInputDialog, QDialog
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, StyledCombo, PrimaryButton, SecondaryButton,
    style_popup, AnimatedPlaceholderEntry,
)
from ui.components.dialogs import ask_confirm, show_info, show_error
from utils.logger import log

from utils.data_manager import (
    GM_DATA_PATH,
    INVENTORY_PLANS_PATH,
    INVENTORY_PATH,
)

from core.inventory_helper import (
    find_gm_by_code,
    get_variant_values,
    get_variant_key_from_title,
    build_empty_checklist,
    calculate_end_date,
    calculate_days_passed,
    calculate_progress,
    format_date_ru,
    get_day_data,
)


class InventoryFrame(BaseFrame):

    TITLE = "Инвентаризация"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.gm_data = []
        self.plans = {}
        self.active_inventory = None

        self._last_inventory_signature = None
        self._loading = False

        # Debounce таймер для сохранения чек-листа
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._do_save_inventory)

        # Ссылки на чекбоксы: (day_key, shift_key, idx) → QCheckBox
        self._checkboxes = {}

        self._load_all_from_cache()
        self._setup_ui()
        self._refresh_async()

    @property
    def dm(self):
        return self.app.data_manager

    # =========================================================
    # ЗАГРУЗКА
    # =========================================================
    def _load_all_from_cache(self):
        self.gm_data = self.dm.get_gm_data()
        self.plans = self.dm.get_inventory_plans()
        self.active_inventory = self.dm.get_active_inventory()
        self._last_inventory_signature = self.dm.signature(self.active_inventory)

    def _refresh_async(self):
        if self._loading:
            return
        self._loading = True

        results = {"done": 0, "total": 3, "data": {}}

        def _check_done():
            if results["done"] < results["total"]:
                return
            self._loading = False
            self._apply_loaded_data(results["data"])

        def _make_cb(key):
            def _cb(data):
                results["data"][key] = data
                results["done"] += 1
                self.run_on_ui(_check_done)
            return _cb

        try:
            if hasattr(self.dm, "read_json_async"):
                self.dm.read_json_async("gm_data", GM_DATA_PATH, _make_cb("gm_data"))
                self.dm.read_json_async("inventory_plans", INVENTORY_PLANS_PATH, _make_cb("plans"))
                self.dm.read_json_async("active_inventory", INVENTORY_PATH, _make_cb("active"))
            else:
                results["data"]["gm_data"] = self.dm.get_gm_data()
                results["data"]["plans"] = self.dm.get_inventory_plans()
                results["data"]["active"] = self.dm.get_active_inventory()
                results["done"] = 3
                _check_done()
        except Exception as e:
            log.debug(f"async load inventory failed: {e}")
            self._loading = False

    def _apply_loaded_data(self, data):
        if not data:
            return

        new_gm = data.get("gm_data", self.gm_data)
        new_plans = data.get("plans", self.plans)
        new_active = data.get("active", self.active_inventory)

        new_sig = self.dm.signature(new_active)

        changed = False
        if new_gm != self.gm_data:
            self.gm_data = new_gm or []
            changed = True
        if new_plans != self.plans:
            self.plans = new_plans or {}
            changed = True
        if new_sig != self._last_inventory_signature:
            self.active_inventory = new_active
            self._last_inventory_signature = new_sig
            changed = True

        if changed:
            self._render_inventory()
            self._rebuild_checklist_view()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(15, 15, 15, 10)
        root_layout.setSpacing(10)

        title = QLabel("ИНВЕНТАРИЗАЦИЯ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        self.main_scroll = QScrollArea(self)
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.main_scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(12)

        self.main_scroll.setWidget(self.scroll_content)
        root_layout.addWidget(self.main_scroll, 1)

        self.inventory_card = create_card(self.scroll_content)
        self.scroll_layout.addWidget(self.inventory_card)

        self.inventory_container = QVBoxLayout()
        self.inventory_container.setSpacing(8)
        self.inventory_card.layout().addLayout(self.inventory_container)

        self.checklist_card = create_card(self.scroll_content)
        self.scroll_layout.addWidget(self.checklist_card)

        self.checklist_container = QVBoxLayout()
        self.checklist_container.setSpacing(6)
        self.checklist_card.layout().addLayout(self.checklist_container)

        self.scroll_layout.addStretch()

        self._render_inventory()
        self._rebuild_checklist_view()

    # =========================================================
    # УТИЛИТЫ UI
    # =========================================================
    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            child = item.layout()
            if child is not None:
                self._clear_layout(child)

    # =========================================================
    # АКТИВНАЯ — РЕНДЕР
    # =========================================================
    def _render_inventory(self):
        self._clear_layout(self.inventory_container)

        if self.active_inventory:
            self._render_inventory_active()
        else:
            self._render_inventory_form()

    # =========================================================
    # ФОРМА ЗАПУСКА
    # =========================================================
    def _render_inventory_form(self):
        card = self.inventory_card

        title = QLabel("НАЧАТЬ ИНВЕНТАРИЗАЦИЮ", card)
        title.setFont(self.FONTS['subtitle'])
        self.inventory_container.addWidget(title)

        hint = QLabel("Заполните поля и нажмите кнопку внизу.", card)
        hint.setFont(self.FONTS['small'])
        hint.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        self.inventory_container.addWidget(hint)

        # --- Код ГМ ---
        row_gm = QHBoxLayout()
        row_gm.setSpacing(10)

        lbl_gm = QLabel("Код ГМ:", card)
        lbl_gm.setFont(self.FONTS['label'])
        lbl_gm.setFixedWidth(180)
        row_gm.addWidget(lbl_gm)

        self.gm_input = AnimatedPlaceholderEntry(
            placeholder="Введите код или название ГМ",
            parent=card
        )
        self.gm_input.setFixedWidth(220)
        self.gm_input.textChanged.connect(self._on_gm_code_change)
        self._attach_gm_completer(self.gm_input)
        row_gm.addWidget(self.gm_input)

        self.lbl_gm_name = QLabel("", card)
        self.lbl_gm_name.setFont(self.FONTS['small'])
        self.lbl_gm_name.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        row_gm.addWidget(self.lbl_gm_name, 1)

        self.inventory_container.addLayout(row_gm)

        # --- Вариант ---
        row_var = QHBoxLayout()
        row_var.setSpacing(10)

        lbl_var = QLabel("Вариант:", card)
        lbl_var.setFont(self.FONTS['label'])
        lbl_var.setFixedWidth(180)
        row_var.addWidget(lbl_var)

        self.combo_variant = StyledCombo(
            items=get_variant_values(self.plans),
            parent=card
        )
        self.combo_variant.setMinimumWidth(400)
        self.combo_variant.currentTextChanged.connect(self._on_variant_change)
        row_var.addWidget(self.combo_variant, 1)

        self.inventory_container.addLayout(row_var)

        # --- Дата начала ---
        row_start = QHBoxLayout()
        row_start.setSpacing(10)

        lbl_start = QLabel("Дата начала:", card)
        lbl_start.setFont(self.FONTS['label'])
        lbl_start.setFixedWidth(180)
        row_start.addWidget(lbl_start)

        self.date_start = QDateEdit(card)
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate())
        self.date_start.setDisplayFormat("dd.MM.yyyy")
        self.date_start.setMinimumHeight(38)
        self.date_start.setFixedWidth(200)
        self.date_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.date_start.dateChanged.connect(self._update_end_date)

        style_popup(self.date_start)

        row_start.addWidget(self.date_start)
        row_start.addStretch()
        self.inventory_container.addLayout(row_start)

        self._apply_today_highlight(self.date_start)

        # --- Дата окончания ---
        row_end = QHBoxLayout()
        row_end.setSpacing(10)

        lbl_end = QLabel("Дата окончания:", card)
        lbl_end.setFont(self.FONTS['label'])
        lbl_end.setFixedWidth(180)
        row_end.addWidget(lbl_end)

        self.lbl_end_date = QLabel("—", card)
        self.lbl_end_date.setFont(self.FONTS['label'])
        self.lbl_end_date.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        row_end.addWidget(self.lbl_end_date, 1)

        self.inventory_container.addLayout(row_end)

        # --- Статус формы ---
        self.lbl_form_status = QLabel("", card)
        self.lbl_form_status.setFont(self.FONTS['small'])
        self.lbl_form_status.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        self.inventory_container.addWidget(self.lbl_form_status)

        # --- Кнопка запуска ---
        btn_start = PrimaryButton(
            "НАЧАТЬ ИНВЕНТАРИЗАЦИЮ",
            on_click=self._start_inventory,
            parent=card
        )
        btn_start.setMinimumWidth(400)
        btn_start.setMinimumHeight(50)

        btn_wrap = QHBoxLayout()
        btn_wrap.addStretch()
        btn_wrap.addWidget(btn_start)
        btn_wrap.addStretch()
        self.inventory_container.addLayout(btn_wrap)

        QTimer.singleShot(0, self._update_end_date)

    # =========================================================
    # ПОДСВЕТКА СЕГОДНЯШНЕЙ ДАТЫ
    # =========================================================
    @staticmethod
    def _apply_today_highlight(date_edit):
        cal = date_edit.calendarWidget()
        if cal is None:
            return

        today = QDate.currentDate()

        fmt = QTextCharFormat()
        fmt.setBackground(QBrush(QColor("#D42626")))
        fmt.setForeground(QBrush(QColor("#FFFFFF")))
        fmt.setFontWeight(75)

        cal.setDateTextFormat(today, fmt)

    # =========================================================
    # АВТОКОМПЛИТ ГМ
    # =========================================================
    def _attach_gm_completer(self, entry: QLineEdit):
        if not self.gm_data:
            return

        items = []
        for gm in self.gm_data:
            code = str(gm.get("Код", "")).strip()
            name = gm.get("Название", "")
            if code:
                items.append(f"{code} — {name}")

        model = QStringListModel(items, entry)
        completer = QCompleter(model, entry)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(15)

        style_popup(completer)
        entry.setCompleter(completer)

        def _on_activated(text):
            match = re.search(r'\b(\d{6})\b', text)
            if match:
                entry.setText(match.group(1))
            else:
                entry.setText(text)

        completer.activated.connect(_on_activated)

    def _on_gm_code_change(self, text=None):
        code = self.gm_input.text().strip()

        if len(code) != 6 or not code.isdigit():
            self.lbl_gm_name.setText("")
            return

        gm = find_gm_by_code(code, self.gm_data)
        if gm:
            name = gm.get("Название", "")
            self.lbl_gm_name.setText(f"✓ {name}")
            self.lbl_gm_name.setStyleSheet(
                f"color: {self.COLORS.get('text', '#E0E0E0')};"
            )
        else:
            self.lbl_gm_name.setText("✗ ГМ не найден в базе")
            self.lbl_gm_name.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )

    def _on_variant_change(self, value=None):
        self._update_end_date()

    def _update_end_date(self):
        qdate = self.date_start.date()
        sd = date(qdate.year(), qdate.month(), qdate.day())

        variant_title = self.combo_variant.currentText()
        variant_key = get_variant_key_from_title(variant_title, self.plans)

        if not variant_key:
            self.lbl_end_date.setText("—")
            self.lbl_end_date.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
            )
            return

        plan = self.plans.get(variant_key, {})
        days_total = plan.get("days_total", 0)

        if not days_total:
            self.lbl_end_date.setText("—")
            return

        ed = calculate_end_date(sd, days_total)
        self.lbl_end_date.setText(f"{ed.strftime('%d.%m.%Y')} ({days_total} суток)")
        self.lbl_end_date.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )

    # =========================================================
    # СТАРТ ИНВЕНТАРИЗАЦИИ
    # =========================================================
    def _start_inventory(self):
        if self.active_inventory:
            show_info(
                self,
                "Невозможно начать",
                "Невозможно начать новую инвентаризацию, пока активна текущая.\n\n"
                "Завершите или смените текущую инвентаризацию."
            )
            return

        code = self.gm_input.text().strip()

        if len(code) != 6 or not code.isdigit():
            match = re.search(r'\b(\d{6})\b', code)
            if match:
                code = match.group(1)
                self.gm_input.setText(code)

        if len(code) != 6 or not code.isdigit():
            self.lbl_form_status.setText("⚠️ Введите корректный код ГМ (6 цифр)")
            self.lbl_form_status.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
            return

        gm = find_gm_by_code(code, self.gm_data)
        if not gm:
            self.lbl_form_status.setText("⚠️ ГМ не найден в базе")
            self.lbl_form_status.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
            return

        variant_title = self.combo_variant.currentText()
        variant_key = get_variant_key_from_title(variant_title, self.plans)
        if not variant_key:
            self.lbl_form_status.setText("⚠️ Не выбран вариант")
            self.lbl_form_status.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
            return

        plan = self.plans.get(variant_key, {})
        days_total = plan.get("days_total", 0)

        qdate = self.date_start.date()
        sd = date(qdate.year(), qdate.month(), qdate.day())
        ed = calculate_end_date(sd, days_total)

        checklist_state = build_empty_checklist(plan)

        self.active_inventory = {
            "gm_code": code,
            "gm_name": gm.get("Название", ""),
            "gm_address": gm.get("Адрес", ""),
            "variant": variant_key,
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "days_total": days_total,
            "checklist": checklist_state,
        }

        self.dm.set_active_inventory(self.active_inventory)
        self._last_inventory_signature = self.dm.signature(self.active_inventory)

        log.info(f"Начата инвентаризация: ГМ {code} (вариант {variant_key})")

        try:
            self.dm.add_action(
                "Начата инвентаризация",
                f"ГМ {code} — {gm.get('Название', '')} (вариант {variant_key})",
                "🏪"
            )
        except Exception:
            pass

        self._render_inventory()
        self._rebuild_checklist_view()

    # =========================================================
    # АКТИВНАЯ ИНВЕНТАРИЗАЦИЯ — отображение
    # =========================================================
    def _render_inventory_active(self):
        inv = self.active_inventory
        card = self.inventory_card

        title = QLabel(
            f"АКТИВНАЯ ИНВЕНТАРИЗАЦИЯ (Вариант {inv.get('variant', '?')})",
            card
        )
        title.setFont(self.FONTS['subtitle'])
        title.setStyleSheet(f"color: {self.COLORS.get('button', '#D42626')};")
        self.inventory_container.addWidget(title)

        gm_label = QLabel(
            f"ГМ {inv.get('gm_code', '?')} — {inv.get('gm_name', '?')}",
            card
        )
        gm_label.setFont(self.FONTS['label'])
        self.inventory_container.addWidget(gm_label)

        address = inv.get("gm_address", "")
        if address:
            addr_label = QLabel(f"{address}", card)
            addr_label.setFont(self.FONTS['small'])
            addr_label.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
            )
            self.inventory_container.addWidget(addr_label)

        start_str = inv.get("start_date", "")
        end_str = inv.get("end_date", "")
        days_total = inv.get("days_total", 1)

        start_fmt = format_date_ru(start_str)
        end_fmt = format_date_ru(end_str)

        try:
            sd = datetime.fromisoformat(start_str).date()
            days_passed = calculate_days_passed(sd, days_total)
        except Exception:
            days_passed = 1

        info_row = QHBoxLayout()

        dates_label = QLabel(
            f"{start_fmt} → {end_fmt} ({days_total} суток)",
            card
        )
        dates_label.setFont(self.FONTS['small'])
        dates_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        info_row.addWidget(dates_label, 1)

        days_label = QLabel(f"День {days_passed} из {days_total}", card)
        days_label.setFont(self.FONTS['label'])
        info_row.addWidget(days_label)

        self.inventory_container.addLayout(info_row)

        # Прогресс по дням (серый)
        progress_value = days_passed / days_total if days_total > 0 else 0
        pbar = QProgressBar(card)
        pbar.setObjectName("GlobalProgress")
        pbar.setMinimum(0)
        pbar.setMaximum(100)
        pbar.setValue(int(progress_value * 100))
        pbar.setFixedHeight(12)
        pbar.setTextVisible(False)
        self.inventory_container.addWidget(pbar)

        pct_label = QLabel(f"{int(progress_value * 100)}%", card)
        pct_label.setFont(self.FONTS['small'])
        pct_label.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        pct_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.inventory_container.addWidget(pct_label)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_change = PrimaryButton(
            "Сменить ГМ",
            on_click=self._change_inventory,
            parent=card
        )
        btn_change.setMinimumWidth(180)
        btn_change.setMinimumHeight(40)
        btn_row.addWidget(btn_change)

        btn_finish = SecondaryButton(
            "Завершить",
            on_click=self._finish_inventory,
            parent=card
        )
        btn_finish.setMinimumWidth(180)
        btn_finish.setMinimumHeight(40)
        btn_row.addWidget(btn_finish)

        btn_row.addStretch()
        self.inventory_container.addLayout(btn_row)

        btn_plan = SecondaryButton(
            "План на все дни",
            on_click=self._show_full_plan,
            parent=card
        )
        btn_plan.setMinimumWidth(400)
        btn_plan.setMinimumHeight(40)

        btn_wrap = QHBoxLayout()
        btn_wrap.addStretch()
        btn_wrap.addWidget(btn_plan)
        btn_wrap.addStretch()
        self.inventory_container.addLayout(btn_wrap)

    # =========================================================
    # ЧЕК-ЛИСТ
    # =========================================================
    def _rebuild_checklist_view(self):
        self._clear_layout(self.checklist_container)
        self._checkboxes = {}

        card = self.checklist_card

        if not self.active_inventory:
            title = QLabel("ЧЕК-ЛИСТ ДНЯ", card)
            title.setFont(self.FONTS['subtitle'])
            self.checklist_container.addWidget(title)

            hint = QLabel("Начните инвентаризацию, чтобы видеть чек-лист.", card)
            hint.setFont(self.FONTS['small'])
            hint.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
            self.checklist_container.addWidget(hint)
            return

        variant_key = self.active_inventory.get("variant", "")
        plan = self.plans.get(variant_key, {})

        if not plan:
            err = QLabel("⚠️ План не найден", card)
            err.setFont(self.FONTS['label'])
            err.setStyleSheet(f"color: {self.COLORS.get('error', '#FF5252')};")
            self.checklist_container.addWidget(err)
            return

        start_str = self.active_inventory.get("start_date", "")
        days_total = self.active_inventory.get("days_total", 1)

        try:
            sd = datetime.fromisoformat(start_str).date()
            days_passed = calculate_days_passed(sd, days_total)
        except Exception:
            days_passed = 1

        day_data = get_day_data(plan, days_passed)
        if not day_data:
            err = QLabel(f"⚠️ День {days_passed} не найден в плане", card)
            err.setFont(self.FONTS['label'])
            err.setStyleSheet(f"color: {self.COLORS.get('error', '#FF5252')};")
            self.checklist_container.addWidget(err)
            return

        title = QLabel(
            f"ЧЕК-ЛИСТ — {day_data.get('day_name', f'День {days_passed}')}",
            card
        )
        title.setFont(self.FONTS['subtitle'])
        title.setStyleSheet(f"color: {self.COLORS.get('button', '#D42626')};")
        self.checklist_container.addWidget(title)

        checklist = self.active_inventory.get("checklist", {})
        progress = calculate_progress(checklist, plan)

        prog_row = QHBoxLayout()
        lbl_prog = QLabel(f"Всего: {progress['done']} из {progress['total']}", card)
        lbl_prog.setFont(self.FONTS['small'])
        lbl_prog.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        prog_row.addWidget(lbl_prog, 1)

        lbl_pct = QLabel(f"{progress['percent']}%", card)
        lbl_pct.setFont(self.FONTS['label'])
        pct_color = self.COLORS.get('text', '#E0E0E0')  # всегда серый/белый, не зелёный
        lbl_pct.setStyleSheet(f"color: {pct_color};")
        prog_row.addWidget(lbl_pct)

        self.checklist_container.addLayout(prog_row)

        pbar = QProgressBar(card)
        pbar.setObjectName("GlobalProgress")
        pbar.setMinimum(0)
        pbar.setMaximum(100)
        pbar.setValue(progress['percent'])
        pbar.setFixedHeight(8)
        pbar.setTextVisible(False)
        self.checklist_container.addWidget(pbar)

        day_key = f"day_{days_passed}"
        day_state = checklist.get(day_key, {})

        for shift_idx, shift_data in enumerate(day_data.get("shifts", [])):
            shift_key = f"shift_{shift_idx + 1}"
            shift_name = shift_data.get("shift_name", f"Смена {shift_idx + 1}")
            tasks = shift_data.get("tasks", [])
            shift_state = day_state.get(shift_key, {})

            shift_title = QLabel(shift_name.upper(), card)
            shift_title.setFont(self.FONTS['subtitle'])
            self.checklist_container.addWidget(shift_title)

            for i, task in enumerate(tasks):
                is_done = shift_state.get(str(i), False)

                cb = QCheckBox(task, card)
                cb.setChecked(is_done)
                cb.setFont(self.FONTS['small'])
                cb.setStyleSheet(self._checkbox_style(is_done))

                cb.stateChanged.connect(
                    lambda state, dk=day_key, sk=shift_key, idx=i:
                    self._toggle_item(dk, sk, idx, state == Qt.CheckState.Checked.value)
                )

                self.checklist_container.addWidget(cb)
                self._checkboxes[(day_key, shift_key, i)] = cb

    def _checkbox_style(self, is_done: bool) -> str:
        return f"""
            QCheckBox {{
                background-color: transparent;
                color: {self.COLORS.get('text_dim', '#A0A0A0') if is_done else self.COLORS.get('text', '#E0E0E0')};
                spacing: 8px;
                padding: 4px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {self.COLORS.get('border', '#333333')};
                border-radius: 4px;
                background-color: transparent;
            }}
            QCheckBox::indicator:hover {{
                border-color: {self.COLORS.get('text_dim', '#A0A0A0')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.COLORS.get('button', '#D42626')};
                border-color: {self.COLORS.get('button', '#D42626')};
            }}
        """

    def _toggle_item(self, day_key, shift_key, idx, value):
        if not self.active_inventory:
            return

        checklist = self.active_inventory.get("checklist", {})
        if day_key not in checklist:
            checklist[day_key] = {}
        if shift_key not in checklist[day_key]:
            checklist[day_key][shift_key] = {}

        checklist[day_key][shift_key][str(idx)] = bool(value)
        self._save_timer.start()

    def _do_save_inventory(self):
        if not self.active_inventory:
            return
        try:
            self.dm.set_active_inventory(self.active_inventory)
            self._last_inventory_signature = self.dm.signature(self.active_inventory)
        except Exception as e:
            log.warning(f"Не удалось сохранить инвентаризацию: {e}")

        self._refresh_checkbox_styles()

    def _refresh_checkbox_styles(self):
        for (_dk, _sk, _idx), cb in self._checkboxes.items():
            try:
                cb.setStyleSheet(self._checkbox_style(cb.isChecked()))
            except RuntimeError:
                pass

    # =========================================================
    # ХУКИ ЖИЗНЕННОГО ЦИКЛА
    # =========================================================
    def on_hide(self):
        try:
            if self._save_timer.isActive():
                self._save_timer.stop()
                self._do_save_inventory()
        except Exception:
            pass

    def on_close(self):
        try:
            if self._save_timer.isActive():
                self._save_timer.stop()
                self._do_save_inventory()
        except Exception:
            pass

    # =========================================================
    # ДЕЙСТВИЯ
    # =========================================================
    def _change_inventory(self):
        if not self.active_inventory:
            return

        ok = ask_confirm(
            self,
            "Сменить ГМ",
            "Текущая инвентаризация будет удалена.\n\nПродолжить?"
        )
        if not ok:
            return

        code, ok = QInputDialog.getText(
            self,
            "Сменить ГМ",
            "Введите новый номер ГМ (6 цифр):"
        )
        if not ok or not code:
            return

        code = code.strip()
        if len(code) != 6 or not code.isdigit():
            show_error(self, "Ошибка", "Номер ГМ должен состоять из 6 цифр.")
            return

        gm = find_gm_by_code(code, self.gm_data)
        if not gm:
            show_error(self, "Ошибка", f"ГМ {code} не найден в базе.")
            return

        self._finish_current_inventory()

        old_inv = self.active_inventory
        self.active_inventory = {
            "gm_code": code,
            "gm_name": gm.get("Название", ""),
            "gm_address": gm.get("Адрес", ""),
            "variant": old_inv.get("variant", "Ж"),
            "start_date": old_inv.get("start_date", date.today().isoformat()),
            "end_date": old_inv.get("end_date", date.today().isoformat()),
            "days_total": old_inv.get("days_total", 5),
            "checklist": {},
        }

        variant_key = self.active_inventory["variant"]
        plan = self.plans.get(variant_key, {})
        self.active_inventory["checklist"] = build_empty_checklist(plan)

        self.dm.set_active_inventory(self.active_inventory)
        self._last_inventory_signature = self.dm.signature(self.active_inventory)

        self._render_inventory()
        self._rebuild_checklist_view()

        try:
            self.dm.add_action(
                "Смена ГМ",
                f"Новый ГМ {code} — {gm.get('Название', '')}",
                "🔄"
            )
        except Exception:
            pass

    def _finish_inventory(self):
        if not self.active_inventory:
            return

        code = self.active_inventory.get("gm_code", "")
        name = self.active_inventory.get("gm_name", "")

        ok = ask_confirm(
            self,
            "Завершить инвентаризацию?",
            f"ГМ {code} — {name}\n\nЧек-лист будет удалён. Продолжить?"
        )
        if not ok:
            return

        self._finish_current_inventory()
        self._render_inventory()
        self._rebuild_checklist_view()

    def _finish_current_inventory(self):
        if not self.active_inventory:
            return

        gm_code = self.active_inventory.get("gm_code", "")

        self.active_inventory = None
        self.dm.set_active_inventory(None)
        self._last_inventory_signature = None

        log.info(f"Инвентаризация завершена (чек-лист удалён): ГМ {gm_code}")

    # =========================================================
    # ПЛАН НА ВСЕ ДНИ
    # =========================================================
    def _show_full_plan(self):
        if not self.active_inventory:
            return

        variant_key = self.active_inventory.get("variant", "")
        plan = self.plans.get(variant_key, {})

        if not plan:
            show_error(self, "Ошибка", "План не найден.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"План инвентаризации — Вариант {variant_key}")
        dlg.resize(800, 700)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel(plan.get("title", f"Вариант {variant_key}"), dlg)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        scroll = QScrollArea(dlg)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        for day_data in plan.get("days", []):
            day_frame = QFrame(content)
            day_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
                    border-radius: 10px;
                }}
            """)
            day_layout = QVBoxLayout(day_frame)
            day_layout.setContentsMargins(15, 12, 15, 12)
            day_layout.setSpacing(4)

            day_title = QLabel(
                day_data.get("day_name", f"День {day_data.get('day_num', '?')}"),
                day_frame
            )
            day_title.setFont(self.FONTS['subtitle'])
            day_title.setStyleSheet(f"color: {self.COLORS.get('button', '#D42626')};")
            day_layout.addWidget(day_title)

            for shift_idx, shift_data in enumerate(day_data.get("shifts", [])):
                shift_name = shift_data.get("shift_name", f"Смена {shift_idx + 1}")
                tasks = shift_data.get("tasks", [])

                shift_label = QLabel(shift_name, day_frame)
                shift_label.setFont(self.FONTS['label'])
                day_layout.addWidget(shift_label)

                for task in tasks:
                    task_label = QLabel(f"  • {task}", day_frame)
                    task_label.setFont(self.FONTS['small'])
                    task_label.setStyleSheet(
                        f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
                    )
                    task_label.setWordWrap(True)
                    day_layout.addWidget(task_label)

            content_layout.addWidget(day_frame)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        btn_close = PrimaryButton("Закрыть", on_click=dlg.accept, parent=dlg)
        btn_close.setMinimumWidth(200)

        btn_wrap = QHBoxLayout()
        btn_wrap.addStretch()
        btn_wrap.addWidget(btn_close)
        btn_wrap.addStretch()
        layout.addLayout(btn_wrap)

        dlg.exec()

    # =========================================================
    # REFRESH
    # =========================================================
    def refresh(self):
        self._load_all_from_cache()
        self._render_inventory()
        self._rebuild_checklist_view()
        self._refresh_async()