# ui/frames/timesheet_frame.py
"""
Табель — вкладка для ввода рабочих часов ревизора.

- Свой календарь на месяц (воскресенье подсвечено красным)
- Три поля: К (командировка), Д (дорога), Н (ночь)
- Поля пустые по умолчанию, только целые числа
- Автосохранение при вводе
- Строка для АСУЗ снизу + кнопка «Копировать»
- Сводка по 4 неделям месяца (только К)
- Итого по К + отдельно Дорога (Д) и Ночные (Н)

ИЗМЕНЕНИЯ:
- QSpinBox заменён на QLineEdit + QIntValidator (без стрелочек).
- Добавлена сводка по неделям (только К).
- Добавлены строки «Дорога (Д)» и «Ночные (Н)» под «Итого (К)».
"""
import calendar
from datetime import date

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QGridLayout, QWidget, QApplication
)

from ui.frames.base_frame import BaseFrame
from ui.icons import get_icon_simple
from utils.logger import log
from core.timesheet import (
    load_timesheet, save_timesheet, get_day, set_day,
    format_for_asu,
)


WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


class TimesheetFrame(BaseFrame):

    TITLE = "Табель"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        today = date.today()
        self._year = today.year
        self._month = today.month
        self._selected_date: date = today
        self._data: dict = load_timesheet()
        self._day_buttons: dict = {}
        self._loading = False

        self._setup_ui()
        self._render_calendar()
        self._load_selected_day()
        self._update_weeks_summary()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # --- Заголовок месяца + кнопки навигации ---
        header = QHBoxLayout()
        header.setSpacing(10)

        self.btn_prev = QPushButton("←")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setFixedSize(40, 34)
        self.btn_prev.setStyleSheet(self._nav_btn_style())
        self.btn_prev.clicked.connect(self._prev_month)
        header.addWidget(self.btn_prev)

        self.month_label = QLabel("")
        self.month_label.setFont(self.FONTS['subtitle'])
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )
        header.addWidget(self.month_label, 1)

        self.btn_next = QPushButton("→")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setFixedSize(40, 34)
        self.btn_next.setStyleSheet(self._nav_btn_style())
        self.btn_next.clicked.connect(self._next_month)
        header.addWidget(self.btn_next)

        root.addLayout(header)

        # --- Календарь ---
        cal_frame = QFrame(self)
        cal_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.COLORS.get('card', '#222222')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
            }}
        """)
        cal_layout = QVBoxLayout(cal_frame)
        cal_layout.setContentsMargins(12, 12, 12, 12)
        cal_layout.setSpacing(6)

        weekdays_layout = QGridLayout()
        weekdays_layout.setSpacing(4)
        for col, name in enumerate(WEEKDAYS_RU):
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedHeight(28)
            lbl.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"font-size: 12px; font-weight: bold;"
            )
            weekdays_layout.addWidget(lbl, 0, col)
        cal_layout.addLayout(weekdays_layout)

        self.days_grid = QGridLayout()
        self.days_grid.setSpacing(4)
        cal_layout.addLayout(self.days_grid)

        root.addWidget(cal_frame)

        # --- Панель ввода ---
        input_frame = QFrame(self)
        input_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.COLORS.get('card', '#222222')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
            }}
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(14, 12, 14, 12)
        input_layout.setSpacing(10)

        self.date_label = QLabel("")
        self.date_label.setFont(self.FONTS['label'])
        self.date_label.setStyleSheet(
            f"color: {self.COLORS.get('button', '#D42626')};"
        )
        input_layout.addWidget(self.date_label)

        # Три поля
        fields_layout = QHBoxLayout()
        fields_layout.setSpacing(12)

        self.edit_k = self._make_lineedit("К (командировка)")
        self.edit_d = self._make_lineedit("Д (дорога)")
        self.edit_n = self._make_lineedit("Н (ночь)")

        fields_layout.addWidget(self._make_field("К (командировка)", self.edit_k))
        fields_layout.addWidget(self._make_field("Д (дорога)", self.edit_d))
        fields_layout.addWidget(self._make_field("Н (ночь)", self.edit_n))

        input_layout.addLayout(fields_layout)

        # Строка для АСУЗ
        asu_layout = QHBoxLayout()
        asu_layout.setSpacing(10)

        asu_label = QLabel("Для АСУЗ:")
        asu_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; font-size: 12px;"
        )
        asu_layout.addWidget(asu_label)

        self.asu_value = QLabel("К 0 Д 0 Н 0")
        self.asu_value.setFont(self.FONTS['label'])
        self.asu_value.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; "
            f"background-color: {self.COLORS.get('bg', '#1B1B1B')}; "
            f"padding: 6px 12px; border-radius: 4px;"
        )
        asu_layout.addWidget(self.asu_value, 1)

        self.btn_copy = QPushButton("  Копировать")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setMinimumHeight(34)
        self.btn_copy.setStyleSheet(self._copy_btn_style())
        icon_copy = get_icon_simple(
            "copy", color=self.COLORS.get('text', '#E0E0E0'), size=14
        )
        if not icon_copy.isNull():
            self.btn_copy.setIcon(icon_copy)
            self.btn_copy.setIconSize(QSize(14, 14))
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        asu_layout.addWidget(self.btn_copy)

        input_layout.addLayout(asu_layout)

        root.addWidget(input_frame)

        # --- Сводка по неделям ---
        weeks_frame = QFrame(self)
        weeks_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.COLORS.get('card', '#222222')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
            }}
        """)
        weeks_layout = QVBoxLayout(weeks_frame)
        weeks_layout.setContentsMargins(14, 12, 14, 12)
        weeks_layout.setSpacing(6)

        weeks_title = QLabel("СВОДКА ПО НЕДЕЛЯМ (К)")
        weeks_title.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
            f"font-size: 11px; font-weight: bold;"
        )
        weeks_layout.addWidget(weeks_title)

        self.weeks_labels = {}
        for i in range(1, 5):
            row = QHBoxLayout()
            row.setSpacing(10)

            lbl = QLabel("")
            lbl.setStyleSheet(
                f"color: {self.COLORS.get('text', '#E0E0E0')}; font-size: 13px;"
            )
            row.addWidget(lbl, 1)

            value = QLabel("0")
            value.setStyleSheet(
                f"color: {self.COLORS.get('button', '#D42626')}; "
                f"font-size: 13px; font-weight: bold;"
            )
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(value)

            weeks_layout.addLayout(row)
            self.weeks_labels[i] = (lbl, value)

        # Разделитель
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(
            f"background-color: {self.COLORS.get('border', '#333333')};"
        )
        weeks_layout.addWidget(sep)

        # Итого (К)
        total_row = QHBoxLayout()
        total_row.setSpacing(10)

        total_lbl = QLabel("Итого (К):")
        total_lbl.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; "
            f"font-size: 13px; font-weight: bold;"
        )
        total_row.addWidget(total_lbl, 1)

        self.total_value = QLabel("0")
        self.total_value.setStyleSheet(
            f"color: {self.COLORS.get('button', '#D42626')}; "
            f"font-size: 14px; font-weight: bold;"
        )
        self.total_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        total_row.addWidget(self.total_value)

        weeks_layout.addLayout(total_row)

        # Дорога (Д)
        road_row = QHBoxLayout()
        road_row.setSpacing(10)

        road_lbl = QLabel("Дорога (Д):")
        road_lbl.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; "
            f"font-size: 13px; font-weight: bold;"
        )
        road_row.addWidget(road_lbl, 1)

        self.road_value = QLabel("0")
        self.road_value.setStyleSheet(
            f"color: {self.COLORS.get('button', '#D42626')}; "
            f"font-size: 14px; font-weight: bold;"
        )
        self.road_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        road_row.addWidget(self.road_value)

        weeks_layout.addLayout(road_row)

        # Ночные (Н)
        night_row = QHBoxLayout()
        night_row.setSpacing(10)

        night_lbl = QLabel("Ночные (Н):")
        night_lbl.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; "
            f"font-size: 13px; font-weight: bold;"
        )
        night_row.addWidget(night_lbl, 1)

        self.night_value = QLabel("0")
        self.night_value.setStyleSheet(
            f"color: {self.COLORS.get('button', '#D42626')}; "
            f"font-size: 14px; font-weight: bold;"
        )
        self.night_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        night_row.addWidget(self.night_value)

        weeks_layout.addLayout(night_row)

        root.addWidget(weeks_frame)
        root.addStretch()

        # --- Статус ---
        self.status_label = QLabel("Готово")
        self.status_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; font-size: 11px;"
        )
        root.addWidget(self.status_label)

    def _make_lineedit(self, tooltip: str) -> QLineEdit:
        edit = QLineEdit(self)
        edit.setPlaceholderText("")
        edit.setValidator(QIntValidator(0, 999999, self))
        edit.setFixedHeight(36)
        edit.setToolTip(tooltip)
        edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.COLORS.get('bg', '#1B1B1B')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {self.COLORS.get('button', '#D42626')};
            }}
        """)
        edit.textChanged.connect(self._on_value_changed)
        return edit

    def _make_field(self, label_text: str, edit: QLineEdit) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; font-size: 11px;"
        )
        layout.addWidget(lbl)
        layout.addWidget(edit)
        return w

    def _nav_btn_style(self):
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 6px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
                border-color: {self.COLORS.get('button', '#D42626')};
            }}
        """

    def _copy_btn_style(self):
        return f"""
            QPushButton {{
                background-color: {self.COLORS.get('button', '#D42626')};
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #B01E1E;
            }}
        """

    def _day_btn_style(self, is_selected: bool, is_sunday: bool, has_data: bool):
        if is_selected:
            bg = self.COLORS.get('button', '#D42626')
            color = "#FFFFFF"
        elif has_data:
            bg = self.COLORS.get('sidebar', '#2A2A2A')
            color = self.COLORS.get('text', '#E0E0E0')
        else:
            bg = self.COLORS.get('bg', '#1B1B1B')
            color = self.COLORS.get('text', '#E0E0E0')

        if is_sunday and not is_selected:
            color = self.COLORS.get('error', '#FF5252')

        return f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 6px;
                font-size: 13px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
            }}
        """

    # =========================================================
    # КАЛЕНДАРЬ
    # =========================================================
    def _render_calendar(self):
        while self.days_grid.count():
            item = self.days_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self._day_buttons = {}
        self.month_label.setText(f"{MONTHS_RU[self._month]} {self._year}")

        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdayscalendar(self._year, self._month)

        today = date.today()
        sunday_col = 6

        for row, week in enumerate(weeks):
            for col, day_num in enumerate(week):
                if day_num == 0:
                    continue

                d = date(self._year, self._month, day_num)
                is_sunday = (col == sunday_col)
                is_selected = (d == self._selected_date)
                has_data = get_day(self._data, d) is not None

                btn = QPushButton(str(day_num))
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(38)
                btn.setStyleSheet(
                    self._day_btn_style(is_selected, is_sunday, has_data)
                )
                btn.clicked.connect(
                    lambda checked=False, dd=d: self._select_day(dd)
                )

                if d == today and not is_selected:
                    btn.setStyleSheet(
                        btn.styleSheet().replace(
                            self.COLORS.get('border', '#333333'),
                            self.COLORS.get('button', '#D42626'),
                        )
                    )

                self.days_grid.addWidget(btn, row, col)
                self._day_buttons[d] = btn

    def _select_day(self, d: date):
        self._selected_date = d
        self._render_calendar()
        self._load_selected_day()

    def _prev_month(self):
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self._render_calendar()
        self._load_selected_day()
        self._update_weeks_summary()

    def _next_month(self):
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self._render_calendar()
        self._load_selected_day()
        self._update_weeks_summary()

    # =========================================================
    # ЗАГРУЗКА ДНЯ
    # =========================================================
    def _load_selected_day(self):
        self._loading = True

        d = self._selected_date
        self.date_label.setText(
            d.strftime("%d.%m.%Y") + f"  ({WEEKDAYS_RU[d.weekday()]})"
        )

        rec = get_day(self._data, d)
        if rec is None:
            self.edit_k.setText("")
            self.edit_d.setText("")
            self.edit_n.setText("")
        else:
            k = rec.get("k", 0)
            d_val = rec.get("d", 0)
            n = rec.get("n", 0)
            self.edit_k.setText(str(k) if k != 0 else "")
            self.edit_d.setText(str(d_val) if d_val != 0 else "")
            self.edit_n.setText(str(n) if n != 0 else "")

        self._update_asu_label()
        self._loading = False

    def _get_value(self, edit: QLineEdit) -> int:
        text = edit.text().strip()
        if not text:
            return 0
        try:
            return int(text)
        except ValueError:
            return 0

    # =========================================================
    # ИЗМЕНЕНИЕ ЗНАЧЕНИЙ
    # =========================================================
    def _on_value_changed(self):
        if self._loading:
            return

        d = self._selected_date
        k = self._get_value(self.edit_k)
        d_val = self._get_value(self.edit_d)
        n = self._get_value(self.edit_n)

        set_day(self._data, d, k, d_val, n)
        save_timesheet(self._data)

        self._update_asu_label()
        self._refresh_day_button(d)
        self._update_weeks_summary()

        self.status_label.setText(
            f"Сохранено: {d.strftime('%d.%m.%Y')} — К {k} Д {d_val} Н {n}"
        )

    def _update_asu_label(self):
        k = self._get_value(self.edit_k)
        d_val = self._get_value(self.edit_d)
        n = self._get_value(self.edit_n)
        self.asu_value.setText(format_for_asu(k, d_val, n))

    def _refresh_day_button(self, d: date):
        btn = self._day_buttons.get(d)
        if btn is None:
            return

        is_sunday = (d.weekday() == 6)
        is_selected = (d == self._selected_date)
        has_data = get_day(self._data, d) is not None

        btn.setStyleSheet(self._day_btn_style(is_selected, is_sunday, has_data))

    # =========================================================
    # СВОДКА ПО НЕДЕЛЯМ
    # =========================================================
    def _update_weeks_summary(self):
        """Считает сумму К по 4 неделям + Дорога (Д) и Ночные (Н) за месяц.

        Недели:
            Неделя 1: 1-7
            Неделя 2: 8-14
            Неделя 3: 15-21
            Неделя 4: 22-31 (включая остаток)
        """
        ranges = {
            1: (1, 7),
            2: (8, 14),
            3: (15, 21),
            4: (22, 31),
        }

        totals = {1: 0, 2: 0, 3: 0, 4: 0}
        total_d = 0
        total_n = 0
        month_days = calendar.monthrange(self._year, self._month)[1]

        for day_num in range(1, month_days + 1):
            d = date(self._year, self._month, day_num)
            rec = get_day(self._data, d)
            if rec is None:
                continue

            k = rec.get("k", 0)
            d_val = rec.get("d", 0)
            n = rec.get("n", 0)

            # Дорога и Ночные — суммируем всегда
            total_d += d_val
            total_n += n

            if k == 0:
                continue

            for week_num, (start, end) in ranges.items():
                if start <= day_num <= end:
                    totals[week_num] += k
                    break

        # Обновляем метки недель
        for week_num in range(1, 5):
            start, end = ranges[week_num]
            lbl, value = self.weeks_labels[week_num]
            lbl.setText(f"Неделя {week_num} ({start:02d}-{end:02d}):")
            value.setText(str(totals[week_num]))

        # Итого (К)
        total_k = sum(totals.values())
        self.total_value.setText(str(total_k))

        # Дорога (Д)
        self.road_value.setText(str(total_d))

        # Ночные (Н)
        self.night_value.setText(str(total_n))

    # =========================================================
    # КОПИРОВАНИЕ
    # =========================================================
    def _copy_to_clipboard(self):
        text = self.asu_value.text()
        QApplication.clipboard().setText(text)
        self.status_label.setText(f"Скопировано: {text}")

    # =========================================================
    # REFRESH
    # =========================================================
    def refresh(self):
        self._data = load_timesheet()
        self._render_calendar()
        self._load_selected_day()
        self._update_weeks_summary()