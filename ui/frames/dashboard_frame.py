# ui/frames/dashboard_frame.py
"""
Дашборд отчётов из Outlook.

ИЗМЕНЕНИЯ:
- Убраны зелёные акценты из сводки, динамики и прочих мероприятий.
- Цвета в PieChart, LineChart, HBar оставлены как есть.
- В центре круга "Аналитические зоны" теперь отображается сумма
  БЕЗ учёта РМ и МЦ (если она есть в данных, иначе — с РМ и МЦ).
"""
import os
import re
from datetime import date, datetime

from PyQt6.QtCore import (
    Qt, QSize, QRectF, QStringListModel, QPointF, QSettings
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QPixmap,
    QLinearGradient, QPainterPath
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QCompleter, QPushButton, QSizePolicy, QFileDialog,
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, StyledEntry, PrimaryButton, SecondaryButton,
    style_popup, AnimatedPlaceholderEntry,
)
from ui.icons import get_icon_simple
from utils.file_utils import get_base_dir
from utils.logger import log

from core.email_analytics import (
    summary as email_summary,
    summary_history as email_history,
    gm_list as email_gm_list,
    get_zone_color,
    short_label,
    ZONES_CANONICAL,
)
from core.email_service import collect_emails


SETTINGS_ORG = "SilchenkoAleksey"
SETTINGS_APP = "CoreV3"
LAST_SYNC_KEY = "emails_last_sync"


def _fmt_money(v: float) -> str:
    if v is None:
        return "—"
    if v < 0:
        return f"-{abs(v):,.0f} ₽".replace(",", " ")
    return f"{v:,.0f} ₽".replace(",", " ")


# =========================================================
# КРУГ
# =========================================================
class PieChart(QWidget):
    def __init__(self, data=None, parent=None, center_text=None):
        super().__init__(parent)
        self._data = data or []
        self._center_text = center_text
        self.setMinimumSize(280, 280)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def set_data(self, data):
        self._data = data or []
        self.update()

    def set_center_text(self, text):
        self._center_text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1B1B1B"))

        if not self._data:
            painter.setPen(QColor("#A0A0A0"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет данных"
            )
            painter.end()
            return

        total_abs = sum(abs(v) for _, v, _, _ in self._data)
        if total_abs <= 0:
            painter.setPen(QColor("#A0A0A0"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет данных"
            )
            painter.end()
            return

        side = min(self.width(), self.height()) - 20
        if side < 100:
            side = 100
        x = (self.width() - side) // 2
        y = (self.height() - side) // 2
        rect = QRectF(x, y, side, side)

        start_angle = 90 * 16
        for label, value, total, is_deficit in self._data:
            abs_v = abs(value)
            if abs_v <= 0:
                continue
            span = int(360 * 16 * abs_v / total_abs)
            color = QColor(get_zone_color(label))
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor("#1B1B1B"), 2))
            painter.drawPie(rect, start_angle, -span)
            start_angle -= span

        inner_side = int(side * 0.55)
        inner_x = x + (side - inner_side) // 2
        inner_y = y + (side - inner_side) // 2
        painter.setBrush(QBrush(QColor("#1B1B1B")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(inner_x, inner_y, inner_side, inner_side))

        if self._center_text is not None:
            center_value = self._center_text
        else:
            grand_total = sum(v for _, v, _, _ in self._data)
            center_value = _fmt_money(grand_total)

        painter.setPen(QColor("#E0E0E0"))
        font = QFont("Segoe UI", 14)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRectF(inner_x, inner_y, inner_side, inner_side),
            Qt.AlignmentFlag.AlignCenter,
            center_value,
        )
        painter.end()


# =========================================================
# ЛИНЕЙНЫЙ ГРАФИК
# =========================================================
class LineChart(QWidget):
    POINT_RADIUS = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []
        self.setMinimumHeight(280)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def set_points(self, points):
        self._points = points or []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1B1B1B"))

        w = self.width()
        h = self.height()

        if len(self._points) < 1:
            painter.setPen(QColor("#A0A0A0"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет данных"
            )
            painter.end()
            return

        if len(self._points) == 1:
            self._draw_single_point(painter, w, h)
            painter.end()
            return

        values = [p["total"] for p in self._points]
        v_min = min(values)
        v_max = max(values)
        v_range = v_max - v_min
        if v_range <= 0:
            v_range = abs(v_max) or 1

        top_pad = 50
        bottom_pad = 60
        left_pad = 60
        right_pad = 40

        chart_h = h - top_pad - bottom_pad
        chart_w = w - left_pad - right_pad

        if chart_h <= 0 or chart_w <= 0:
            painter.end()
            return

        n = len(self._points)
        step_x = chart_w / (n - 1) if n > 1 else 0

        painter.setPen(QPen(QColor("#2A2A2A"), 1, Qt.PenStyle.DashLine))
        for i in range(5):
            y_line = top_pad + int(chart_h * i / 4)
            painter.drawLine(left_pad, y_line, left_pad + chart_w, y_line)

        positions = []
        for i, p in enumerate(self._points):
            v = p["total"]
            if v_range > 0:
                norm = (v - v_min) / v_range
            else:
                norm = 0.5
            x = left_pad + int(step_x * i)
            y = top_pad + int(chart_h * (1.0 - norm))
            positions.append((x, y, p))

        line_gradient = QLinearGradient(
            QPointF(left_pad, 0),
            QPointF(left_pad + chart_w, 0)
        )
        line_gradient.setColorAt(0.0, QColor("#4CAF50"))
        line_gradient.setColorAt(0.5, QColor("#FFD700"))
        line_gradient.setColorAt(1.0, QColor("#D42626"))

        fill_path = QPainterPath()
        first_x, first_y, _ = positions[0]
        fill_path.moveTo(first_x, top_pad + chart_h)
        for x, y, _ in positions:
            fill_path.lineTo(x, y)
        last_x, last_y, _ = positions[-1]
        fill_path.lineTo(last_x, top_pad + chart_h)
        fill_path.closeSubpath()

        fill_gradient = QLinearGradient(
            QPointF(0, top_pad),
            QPointF(0, top_pad + chart_h)
        )
        fill_gradient.setColorAt(0.0, QColor(212, 38, 38, 60))
        fill_gradient.setColorAt(1.0, QColor(212, 38, 38, 0))
        painter.setBrush(QBrush(fill_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(fill_path)

        line_path = QPainterPath()
        first_x, first_y, _ = positions[0]
        line_path.moveTo(first_x, first_y)
        for x, y, _ in positions[1:]:
            line_path.lineTo(x, y)

        pen = QPen(QBrush(line_gradient), 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(line_path)

        for i, (x, y, p) in enumerate(positions):
            radius = self.POINT_RADIUS

            painter.setPen(QPen(QColor("#1B1B1B"), 2))
            painter.setBrush(QBrush(QColor("#1B1B1B")))
            painter.drawEllipse(QPointF(x, y), radius + 2, radius + 2)

            if p["total"] > 0:
                dot_color = QColor("#D42626")
            elif p["total"] < 0:
                dot_color = QColor("#4CAF50")
            else:
                dot_color = QColor("#9E9E9E")

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(dot_color))
            painter.drawEllipse(QPointF(x, y), radius, radius)

        painter.setPen(QColor("#E0E0E0"))
        f_val = QFont("Segoe UI", 9)
        f_val.setBold(True)
        painter.setFont(f_val)

        for i, (x, y, p) in enumerate(positions):
            text = _fmt_money(p["total"])
            rect = QRectF(x - 60, y - 30, 120, 22)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.setPen(QColor("#A0A0A0"))
        f_lbl = QFont("Segoe UI", 8)
        painter.setFont(f_lbl)

        for i, (x, y, p) in enumerate(positions):
            label = p.get("label", "")
            rect = QRectF(x - 50, top_pad + chart_h + 8, 100, 36)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label,
            )

        painter.setPen(QColor("#666666"))
        f_date = QFont("Segoe UI", 7)
        painter.setFont(f_date)

        for i, (x, y, p) in enumerate(positions):
            d = p.get("date", "")
            rect = QRectF(x - 50, top_pad + chart_h + 26, 100, 18)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, d)

        painter.end()

    def _draw_single_point(self, painter, w, h):
        p = self._points[0]
        cx = w // 2
        cy = h // 2

        if p["total"] > 0:
            dot_color = QColor("#D42626")
        elif p["total"] < 0:
            dot_color = QColor("#4CAF50")
        else:
            dot_color = QColor("#9E9E9E")

        painter.setPen(QPen(QColor("#1B1B1B"), 3))
        painter.setBrush(QBrush(dot_color))
        painter.drawEllipse(QPointF(cx, cy), 10, 10)

        painter.setPen(QColor("#E0E0E0"))
        f = QFont("Segoe UI", 14)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(
            QRectF(cx - 150, cy - 50, 300, 30),
            Qt.AlignmentFlag.AlignCenter,
            _fmt_money(p["total"]),
        )

        painter.setPen(QColor("#A0A0A0"))
        f2 = QFont("Segoe UI", 10)
        painter.setFont(f2)
        painter.drawText(
            QRectF(cx - 150, cy + 20, 300, 24),
            Qt.AlignmentFlag.AlignCenter,
            f"{p.get('label', '')}  •  {p.get('date', '')}",
        )


# =========================================================
# БАР
# =========================================================
class HBar(QFrame):
    LABEL_WIDTH = 320
    VALUE_WIDTH = 120

    def __init__(self, label, value, max_value, color=None,
                 value_text=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.setStyleSheet("QFrame { background: transparent; }")

        if color is None:
            color = get_zone_color(str(label))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._full_label = short_label(str(label), max_len=120)
        self._label = QLabel(self)
        self._label.setFixedWidth(self.LABEL_WIDTH)
        self._label.setStyleSheet("color: #E0E0E0; background: transparent;")
        self._label.setToolTip(self._full_label)
        layout.addWidget(self._label)

        bar_area = QFrame()
        bar_area.setFixedHeight(10)
        bar_area.setStyleSheet("QFrame { background: transparent; }")
        bar_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.bar = QFrame(bar_area)
        self.bar.setStyleSheet(
            f"QFrame {{ background-color: {color}; border-radius: 5px; }}"
        )

        self._bar_area = bar_area
        self._max_value = max_value
        self._value = value
        layout.addWidget(bar_area, 1)

        text_val = value_text if value_text is not None else str(value)
        val_label = QLabel(text_val)
        val_label.setFixedWidth(self.VALUE_WIDTH)
        val_label.setStyleSheet(
            "color: #E0E0E0; font-family: Consolas; background: transparent;"
        )
        val_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(val_label)

        self._update_label_elide()

    def _update_label_elide(self):
        try:
            fm = QFontMetrics(self._label.font())
            elided = fm.elidedText(
                self._full_label,
                Qt.TextElideMode.ElideRight,
                self.LABEL_WIDTH - 4,
            )
            self._label.setText(elided)
        except Exception:
            self._label.setText(self._full_label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_bar()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_bar()
        self._update_label_elide()

    def _update_bar(self):
        try:
            cw = self._bar_area.width()
            h = self._bar_area.height()
            if self._max_value > 0:
                w = int(cw * self._value / self._max_value)
            else:
                w = 0
            self.bar.setGeometry(0, 0, max(0, w), h)
        except Exception:
            pass


# =========================================================
# ФИЛЬТР ГМ
# =========================================================
class GmFilter(QFrame):
    def __init__(self, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self._gm_list = email_gm_list()
        self._completer = None
        self._completer_activated = None

        self.setStyleSheet("QFrame { background: transparent; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl = QLabel("ГМ:")
        lbl.setStyleSheet("color: #A0A0A0;")
        layout.addWidget(lbl)

        self.entry = AnimatedPlaceholderEntry(
            placeholder="Код или название ГМ", parent=self
        )
        self.entry.setMinimumWidth(320)
        self.entry.setFixedHeight(32)
        self.entry.textChanged.connect(self._emit_change)
        layout.addWidget(self.entry)

        btn_clear = QPushButton("✕")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setFixedSize(32, 32)
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #A0A0A0;
                border: 1px solid #333333;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2A2A2A;
                color: #E0E0E0;
            }
        """)
        btn_clear.clicked.connect(self._clear)
        layout.addWidget(btn_clear)

        layout.addStretch()
        self._attach_completer()

    def _attach_completer(self):
        if not self._gm_list:
            return

        try:
            if self._completer is not None:
                try:
                    self._completer.activated.disconnect(self._completer_activated)
                except (TypeError, RuntimeError):
                    pass
                self.entry.setCompleter(None)
        except RuntimeError:
            pass

        self._completer = None
        self._completer_activated = None

        items = [gm.get("display", "") for gm in self._gm_list]
        items = [x for x in items if x]

        model = QStringListModel(items, self.entry)
        completer = QCompleter(model, self.entry)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(15)

        style_popup(completer)

        self.entry.setCompleter(completer)
        self._completer = completer

        def _on_activated(text):
            self.entry.setText(text)

        self._completer_activated = _on_activated
        completer.activated.connect(_on_activated)

        def _on_text_edited_for_completer(text):
            try:
                if self._completer is None:
                    return
                if not text:
                    self._completer.popup().hide()
                    return
                self._completer.setCompletionPrefix(text)
                if self._completer.completionCount() > 0:
                    self._completer.complete()
                else:
                    self._completer.popup().hide()
            except RuntimeError:
                pass

        self.entry.textEdited.connect(_on_text_edited_for_completer)

    def _clear(self):
        self.entry.clear()

    def _emit_change(self):
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def set_text(self, text):
        self.entry.setText(text)

    def get_text(self) -> str:
        return self.entry.text().strip()

    def get_code(self) -> str:
        text = self.get_text()
        if not text:
            return ""
        m = re.search(r"\b(\d{6})\b", text)
        return m.group(1) if m else ""


# =========================================================
# ДАШБОРД
# =========================================================
class DashboardFrame(BaseFrame):

    TITLE = "Дашборд"

    def __init__(self, parent, name=None,
                 initial_gm_code: str = "",
                 is_embedded: bool = False):
        self._initial_gm_code = initial_gm_code or ""
        self._is_embedded = bool(is_embedded)

        super().__init__(parent, name)
        self.scroll_content = None
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._setup_ui()

        if self._initial_gm_code:
            self.gm_filter.set_text(self._initial_gm_code)

        self.refresh()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        if self._is_embedded:
            root.setContentsMargins(16, 8, 16, 8)
        else:
            root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        if not self._is_embedded:
            title = QLabel("ДАШБОРД")
            title.setFont(self.FONTS['title'])
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(title)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self.gm_filter = GmFilter(on_change=self._on_gm_change)
        if self._is_embedded:
            self.gm_filter.setVisible(False)
        else:
            top_row.addWidget(self.gm_filter, 1)

        self.btn_export = SecondaryButton(
            "Сохранить как PNG",
            on_click=self._export_png,
            parent=self
        )
        self.btn_export.setMinimumWidth(200)
        self.btn_export.setMinimumHeight(40)
        export_icon = get_icon_simple(
            "download",
            color=self.COLORS.get('text', '#E0E0E0'),
            size=16
        )
        if not export_icon.isNull():
            self.btn_export.setIcon(export_icon)
            self.btn_export.setIconSize(QSize(16, 16))
        top_row.addWidget(self.btn_export)

        self.btn_fetch = None
        if not self._is_embedded:
            self.btn_fetch = PrimaryButton(
                "Забрать информацию",
                on_click=self._on_fetch_click,
                parent=self
            )
            self.btn_fetch.setMinimumWidth(240)
            self.btn_fetch.setMinimumHeight(40)
            fetch_icon = get_icon_simple(
                "refresh", color="#FFFFFF", size=16
            )
            if not fetch_icon.isNull():
                self.btn_fetch.setIcon(fetch_icon)
                self.btn_fetch.setIconSize(QSize(16, 16))
            top_row.addWidget(self.btn_fetch)

        if self._is_embedded:
            top_row.addStretch()

        root.addLayout(top_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        content = QWidget()
        content.setStyleSheet("QWidget { background: transparent; }")
        self.main_layout = QVBoxLayout(content)
        self.main_layout.setContentsMargins(0, 0, 24, 0)
        self.main_layout.setSpacing(20)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.scroll_content = content

    def _on_gm_change(self):
        self._refresh_all()

    # =========================================================
    # ПЕРЕРИСОВКА
    # =========================================================
    def _refresh_all(self):
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            child = item.layout()
            if child is not None:
                while child.count():
                    sub = child.takeAt(0)
                    sw = sub.widget()
                    if sw is not None:
                        sw.deleteLater()

        gm_code = self.gm_filter.get_code()

        if not gm_code:
            hint = QLabel("Выберите ГМ в поле выше")
            hint.setFont(self.FONTS['title'])
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"padding: 60px 20px;"
            )
            self.main_layout.addWidget(hint)
            self.main_layout.addStretch()
            return

        try:
            s = email_summary(gm_code)
        except Exception as e:
            log.exception(f"Ошибка аналитики: {e}")
            err = QLabel(f"Ошибка загрузки данных: {e}")
            err.setFont(self.FONTS['label'])
            err.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')}; padding: 20px;"
            )
            self.main_layout.addWidget(err)
            return

        if s["emails_count"] == 0:
            t = QLabel("Нет данных по этому ГМ")
            t.setFont(self.FONTS['title'])
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setStyleSheet("padding: 40px;")
            self.main_layout.addWidget(t)

            hint = QLabel(
                "Нажмите «Забрать информацию», чтобы загрузить отчёты."
            )
            hint.setFont(self.FONTS['label'])
            hint.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
            )
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.main_layout.addWidget(hint)
            self.main_layout.addStretch()
            return

        info = QLabel(
            f"Отчёт: ГМ {s['gm_code']} — {s['gm_name']} "
            f"от {s['report_date']}"
        )
        info.setFont(self.FONTS['label'])
        info.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(info)

        self.main_layout.addWidget(self._make_summary_section(s))

        try:
            history = email_history(gm_code)
        except Exception:
            history = []

        two_cols_layout = QHBoxLayout()
        two_cols_layout.setSpacing(20)
        two_cols_layout.setContentsMargins(0, 0, 0, 0)

        two_cols_layout.addWidget(self._make_dynamics_card(s, history), 1)
        two_cols_layout.addWidget(self._make_top3_card(s), 1)

        two_cols_widget = QWidget(self.scroll_content)
        two_cols_widget.setStyleSheet("background: transparent;")
        two_cols_widget.setLayout(two_cols_layout)
        self.main_layout.addWidget(two_cols_widget)

        self.main_layout.addWidget(self._make_zones_card(s))
        self.main_layout.addWidget(self._make_other_events_card(s))
        self.main_layout.addWidget(self._make_time_card(s))
        self.main_layout.addStretch()

    def _make_section(self, title_text, subtitle_text=""):
        frame = QFrame(self.scroll_content)
        frame.setStyleSheet("QFrame { background: transparent; }")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        t = QLabel(title_text)
        t.setFont(self.FONTS['subtitle'])
        t.setStyleSheet("color: #E0E0E0;")
        layout.addWidget(t)

        if subtitle_text:
            sub = QLabel(subtitle_text)
            sub.setFont(self.FONTS['small'])
            sub.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
            )
            sub.setWordWrap(True)
            layout.addWidget(sub)

        return frame, layout

    def _make_card_block(self, title_text, subtitle_text=""):
        card = QFrame(self.scroll_content)
        card.setObjectName("Card")
        card.setStyleSheet(f"""
            QFrame#Card {{
                background-color: {self.COLORS.get('card', '#222222')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        t = QLabel(title_text)
        t.setFont(self.FONTS['subtitle'])
        t.setStyleSheet("color: #E0E0E0; background: transparent;")
        layout.addWidget(t)

        if subtitle_text:
            sub = QLabel(subtitle_text)
            sub.setFont(self.FONTS['small'])
            sub.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"background: transparent;"
            )
            sub.setWordWrap(True)
            layout.addWidget(sub)

        return card, layout

    def _make_summary_section(self, s):
        frame, layout = self._make_section("СВОДКА")

        totals = s["totals"]
        grand = totals["grand_total"]

        color = "#D42626" if grand >= 0 else self.COLORS.get('text_dim', '#A0A0A0')

        row = QHBoxLayout()
        row.setSpacing(40)
        row.addWidget(self._make_stat("Итог", _fmt_money(grand), color))
        row.addStretch()
        layout.addLayout(row)
        return frame

    def _make_stat(self, label, value, color=None):
        if color is None:
            color = self.COLORS.get('text', '#E0E0E0')
        w = QFrame(self.scroll_content)
        w.setStyleSheet("QFrame { background: transparent; }")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(str(label))
        lbl.setFont(self.FONTS['small'])
        lbl.setStyleSheet("color: #A0A0A0;")
        layout.addWidget(lbl)

        val = QLabel(str(value))
        val.setFont(self.FONTS['subtitle'])
        val.setStyleSheet(f"color: {color};")
        layout.addWidget(val)
        return w

    def _make_dynamics_card(self, s, history):
        card, layout = self._make_card_block("ДИНАМИКА")

        if not history:
            empty = QLabel("Нет данных для графика.")
            empty.setFont(self.FONTS['label'])
            empty.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"padding: 20px 0; background: transparent;"
            )
            layout.addWidget(empty)
            layout.addStretch()
            return card

        chart = LineChart(card)
        chart.set_points(history)
        chart.setMinimumHeight(300)
        layout.addWidget(chart, 1)

        if len(history) >= 2:
            first = history[0]
            last = history[-1]
            diff = last["total"] - first["total"]

            if diff > 0:
                diff_text = f"↑ +{_fmt_money(abs(diff))}"
                diff_color = "#D42626"
            elif diff < 0:
                diff_text = f"↓ −{_fmt_money(abs(diff))}"
                diff_color = self.COLORS.get('text_dim', '#A0A0A0')
            else:
                diff_text = "= без изменений"
                diff_color = "#9E9E9E"

            footer = QHBoxLayout()
            footer.setSpacing(10)

            period_lbl = QLabel(
                f"За период: {first['date']} → {last['date']}"
            )
            period_lbl.setFont(self.FONTS['small'])
            period_lbl.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"background: transparent;"
            )
            footer.addWidget(period_lbl, 1)

            diff_lbl = QLabel(diff_text)
            diff_lbl.setFont(self.FONTS['label'])
            diff_lbl.setStyleSheet(
                f"color: {diff_color}; font-weight: bold; "
                f"background: transparent;"
            )
            footer.addWidget(diff_lbl)

            layout.addLayout(footer)

        return card

    def _make_top3_card(self, s):
        card, layout = self._make_card_block("ТОП-3 ЗОНЫ")

        zones = s["zones"]
        grand = s["totals"]["grand_total"]

        items = []
        for zone in ZONES_CANONICAL:
            d = zones.get(zone, {"total": 0.0})
            v = d.get("total", 0.0)
            if abs(v) > 0:
                items.append((zone, v))

        items.sort(key=lambda x: -abs(x[1]))
        top3 = items[:3]

        if not top3:
            empty = QLabel("Нет данных.")
            empty.setFont(self.FONTS['label'])
            empty.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"padding: 20px 0; background: transparent;"
            )
            layout.addWidget(empty)
            layout.addStretch()
            return card

        max_v = max(abs(v) for _, v in top3) or 1

        for zone, value in top3:
            color = get_zone_color(zone)
            pct_of_total = (abs(value) / abs(grand) * 100) if grand else 0.0

            header = QHBoxLayout()
            header.setSpacing(8)

            marker = QFrame()
            marker.setFixedSize(12, 12)
            marker.setStyleSheet(
                f"QFrame {{ background-color: {color}; "
                f"border-radius: 6px; }}"
            )
            header.addWidget(marker)

            name_lbl = QLabel(zone)
            name_lbl.setFont(self.FONTS['label'])
            name_lbl.setStyleSheet("color: #E0E0E0; background: transparent;")
            header.addWidget(name_lbl, 1)

            pct_lbl = QLabel(f"{pct_of_total:.0f}%")
            pct_lbl.setFont(self.FONTS['label'])
            pct_lbl.setStyleSheet(
                f"color: {color}; font-weight: bold; background: transparent;"
            )
            header.addWidget(pct_lbl)

            layout.addLayout(header)

            layout.addWidget(HBar(
                zone,
                abs(value),
                max_v,
                color=color,
                value_text=_fmt_money(value),
                parent=card,
            ))

        layout.addStretch()
        return card

    def _make_zones_card(self, s):
        card, layout = self._make_card_block("АНАЛИТИЧЕСКИЕ ЗОНЫ")

        row = QHBoxLayout()
        row.setSpacing(20)

        zones = s["zones"]
        pie_data = []
        for zone in ZONES_CANONICAL:
            d = zones.get(zone, {"total": 0.0})
            if abs(d.get("total", 0.0)) > 0:
                pie_data.append((zone, d["total"], d["total"], d["total"] > 0))
        pie_data.sort(key=lambda x: -abs(x[1]))

        # ИЗМЕНЕНИЕ: берем сумму БЕЗ РМ и МЦ, если она есть
        center_sum = s["totals"].get("grand_total_no_rm", s["totals"]["grand_total"])
        
        pie = PieChart(
            data=pie_data,
            parent=card,
            center_text=_fmt_money(center_sum),
        )
        pie.setMinimumHeight(320)
        row.addWidget(pie, 1)

        right = QVBoxLayout()
        right.setSpacing(8)

        legend_title = QLabel("ЗОНЫ")
        legend_title.setFont(self.FONTS['subtitle'])
        legend_title.setStyleSheet("color: #E0E0E0; background: transparent;")
        right.addWidget(legend_title)

        total_abs = sum(abs(v) for _, v, _, _ in pie_data) or 1

        for zone, value, total, is_deficit in pie_data:
            color = get_zone_color(zone)
            pct = abs(value) / total_abs * 100

            item = QHBoxLayout()
            item.setSpacing(10)

            marker = QFrame()
            marker.setFixedSize(12, 12)
            marker.setStyleSheet(
                f"QFrame {{ background-color: {color}; "
                f"border-radius: 6px; }}"
            )
            item.addWidget(marker)

            name_lbl = QLabel(zone)
            name_lbl.setFont(self.FONTS['label'])
            name_lbl.setStyleSheet("color: #E0E0E0; background: transparent;")
            name_lbl.setFixedWidth(220)
            item.addWidget(name_lbl)

            sum_lbl = QLabel(_fmt_money(value))
            sum_lbl.setFont(self.FONTS['label'])
            sum_lbl.setStyleSheet("color: #E0E0E0; background: transparent;")
            sum_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            item.addWidget(sum_lbl, 1)

            pct_lbl = QLabel(f"{pct:.1f}%")
            pct_lbl.setFont(self.FONTS['small'])
            pct_lbl.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"background: transparent;"
            )
            pct_lbl.setFixedWidth(60)
            pct_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            item.addWidget(pct_lbl)

            right.addLayout(item)

        right.addStretch()
        row.addLayout(right, 1)

        layout.addLayout(row)
        return card

    def _make_other_events_card(self, s):
        card, layout = self._make_card_block(
            f"ПРОЧИЕ МЕРОПРИЯТИЯ ({len(s['top_other_events'])})",
            "Все события, не относящиеся к зонам: "
            "инвентаризация МХ, перепроверки, контроль и т.д."
        )

        others = s["top_other_events"]
        if not others:
            empty = QLabel("Нет данных.")
            empty.setFont(self.FONTS['label'])
            empty.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"background: transparent;"
            )
            layout.addWidget(empty)
            return card

        max_v = max(abs(v) for _, v in others) or 1

        for label, total in others:
            color = "#D42626" if total >= 0 else self.COLORS.get('text_dim', '#A0A0A0')
            layout.addWidget(HBar(
                label,
                abs(total),
                max_v,
                color=color,
                value_text=_fmt_money(total),
                parent=card,
            ))

        return card

    def _make_time_card(self, s):
        card, layout = self._make_card_block("ЧАСЫ РЕВИЗОРОВ")

        tt = s["time_total"]
        if not tt:
            empty = QLabel("Нет данных.")
            empty.setFont(self.FONTS['label'])
            empty.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"background: transparent;"
            )
            layout.addWidget(empty)
            return card

        max_v = max(v for _, v in tt) if tt else 1
        for person, hours in tt:
            layout.addWidget(HBar(
                str(person),
                hours,
                max_v,
                color=get_zone_color(str(person)),
                value_text=f"{hours:.1f} ч",
                parent=card,
            ))
        return card

    def _export_png(self):
        if self.scroll_content is None:
            return

        base = os.path.join(get_base_dir(), "Готовые", "Дашборды")
        os.makedirs(base, exist_ok=True)

        gm_code = self.gm_filter.get_code() or "all"
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        default_name = f"dashboard_{gm_code}_{date_str}.png"
        default_path = os.path.join(base, default_name)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить дашборд как PNG",
            default_path,
            "PNG images (*.png)"
        )
        if not path:
            return

        try:
            self.scroll_content.repaint()

            pixmap = QPixmap(self.scroll_content.size())
            pixmap.fill(QColor("#1B1B1B"))
            self.scroll_content.render(pixmap)

            ok = pixmap.save(path, "PNG")
            if not ok:
                raise RuntimeError("QPixmap.save вернул False")

            log.info(f"Дашборд сохранён: {path}")

            self.show_success(
                "Сохранено",
                f"Дашборд сохранён:\n{path}"
            )

            try:
                self.app.data_manager.add_action(
                    "Дашборд → PNG",
                    os.path.basename(path),
                    "📥"
                )
            except Exception:
                pass

        except Exception as e:
            log.exception("Ошибка сохранения PNG")
            self.show_error("Ошибка", f"Не удалось сохранить PNG:\n{e}")

    def _on_fetch_click(self):
        if self.btn_fetch is None:
            return
        self.btn_fetch.setEnabled(False)
        self.run_in_thread(self._collect_in_bg)

    def _collect_in_bg(self):
        try:
            result = collect_emails(days_back=None)
            self.run_on_ui(self._on_collect_done, result)
        except Exception as e:
            log.exception("Ошибка collect_emails")
            self.run_on_ui(self._on_collect_error, str(e))

    def _on_collect_done(self, result):
        if self.btn_fetch is not None:
            self.btn_fetch.setEnabled(True)

        if not result.get("success"):
            err = result.get("error", "Неизвестная ошибка")
            self.show_error("Ошибка сбора", err)
            return

        try:
            now = datetime.now().isoformat()
            self._settings.setValue(LAST_SYNC_KEY, now)
            log.info(f"Ручная синхронизация: {now}")
        except Exception as e:
            log.warning(f"Не удалось сохранить дату синхронизации: {e}")

        try:
            self.gm_filter._gm_list = email_gm_list()
            self.gm_filter._attach_completer()
        except Exception:
            pass

        self._refresh_all()

    def _on_collect_error(self, err):
        if self.btn_fetch is not None:
            self.btn_fetch.setEnabled(True)
        self.show_error("Ошибка сбора", err)

    def refresh(self):
        self._refresh_all()