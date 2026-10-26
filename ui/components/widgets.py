# ui/components/widgets.py
"""
Общие виджеты для Core V3.0.

ИЗМЕНЕНИЯ:
- SecondaryButton теперь поддерживает иконки (icon_name).
  Если иконка есть, текст и иконка выравниваются аккуратно
  через внутренний layout, без "наездов" padding'ов QSS.
- Добавлен AnimatedPlaceholderEntry — поле ввода с побуквенным
  плейсхолдером. Реализован через paintEvent: рисуем текст сами,
  не зависим от Qt-плейсхолдера, QSS и момента показа.
  Анимация стартует в showEvent (когда виджет точно в event loop).
"""
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPainter, QColor, QIcon
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCompleter, QDateEdit, QTabWidget,
    QStyle, QWidget
)

from ui.icons import get_icon_simple

# =========================================================
# ЕДИНЫЙ СТИЛЬ ДЛЯ POPUP-ОКОН
# =========================================================
POPUP_QSS = """
QListView, QCalendarWidget {
    background-color: #222222;
    color: #E0E0E0;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 6px;
    outline: none;
    font-size: 13px;
}
QListView::item {
    background-color: transparent;
    color: #E0E0E0;
    padding: 6px 10px;
    border-radius: 6px;
    min-height: 22px;
}
QListView::item:hover {
    background-color: #2A2A2A;
    color: #FFFFFF;
}
QListView::item:selected {
    background-color: #D42626;
    color: #FFFFFF;
}
QCalendarWidget QWidget {
    background-color: #222222;
    color: #E0E0E0;
}
QCalendarWidget QAbstractItemView:enabled {
    background-color: #222222;
    color: #E0E0E0;
    selection-background-color: #D42626;
    selection-color: #FFFFFF;
    outline: none;
}
QCalendarWidget QToolButton {
    background-color: #2A2A2A;
    color: #E0E0E0;
    border: none;
    padding: 4px 8px;
    font-size: 13px;
}
QCalendarWidget QToolButton:hover {
    background-color: #333333;
    color: #FFFFFF;
}
QCalendarWidget QMenu {
    background-color: #2A2A2A;
    color: #E0E0E0;
    border: 1px solid #333333;
}
QCalendarWidget QMenu::item:selected {
    background-color: #D42626;
    color: #FFFFFF;
}
QCalendarWidget QSpinBox {
    background-color: #2A2A2A;
    color: #E0E0E0;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 2px 6px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #2A2A2A;
}
QCalendarWidget QWidget#qt_calendar_calendarview {
    background-color: #222222;
}
"""


def style_popup(widget):
    """Красит popup любого виджета в единый тёмный стиль."""
    popup = None

    if isinstance(widget, QComboBox):
        popup = widget.view()
    elif isinstance(widget, QCompleter):
        popup = widget.popup()
    elif isinstance(widget, QDateEdit):
        popup = widget.calendarWidget()

    if popup is None:
        return False

    popup.setStyleSheet(POPUP_QSS)
    return True


# =========================================================
# СОВМЕСТИМОСТЬ С ОРИГИНАЛОМ
# =========================================================
def create_card(master, bg="#222222", border="#333333",
                corner_radius=12, border_width=2):
    """Карточка с рамкой."""
    card = QFrame(master)
    card.setObjectName("Card")
    card.setStyleSheet(f"""
        QFrame#Card {{
            background-color: {bg};
            border: {border_width}px solid {border};
            border-radius: {corner_radius}px;
        }}
    """)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(10)

    return card


def create_title(master, text, font, text_color="#E0E0E0", pady=(25, 12)):
    """Заголовок с отступами сверху и снизу."""
    wrapper = QFrame(master)
    wrapper.setFrameShape(QFrame.Shape.NoFrame)

    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, pady[0], 0, pady[1])

    label = QLabel(text, wrapper)
    label.setFont(font)
    label.setStyleSheet(f"color: {text_color};")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(label)
    return wrapper


def style_tabview(tabview, card="#222222", sidebar="#2A2A2A",
                  button="#D42626", hover="#B71C1C",
                  text="#E0E0E0", text_dim="#A0A0A0"):
    """Стилизует QTabWidget."""
    if not isinstance(tabview, QTabWidget):
        return

    tabview.setStyleSheet(f"""
        QTabWidget::pane {{
            background-color: {card};
            border: 1px solid {sidebar};
            border-radius: 8px;
        }}
        QTabBar::tab {{
            background-color: {sidebar};
            color: {text};
            padding: 8px 20px;
            margin-right: 2px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-size: 13px;
        }}
        QTabBar::tab:selected {{
            background-color: {button};
            color: white;
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {hover};
            color: white;
        }}
    """)


# =========================================================
# НОВЫЕ УДОБНЫЕ ФУНКЦИИ
# =========================================================
def SectionTitle(text, parent=None):
    """Заголовок секции."""
    label = QLabel(text, parent)
    label.setObjectName("Subtitle")
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return label


def InfoLabel(text, parent=None):
    """Мелкая серая подпись."""
    label = QLabel(text, parent)
    label.setObjectName("InfoLabel")
    label.setStyleSheet("color: #A0A0A0;")
    return label


def PrimaryButton(text, on_click=None, parent=None, icon_name=None):
    """Основная кнопка (красная)."""
    btn = QPushButton(text, parent)
    btn.setObjectName("PrimaryBtn")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(40)
    
    if icon_name:
        icon = get_icon_simple(icon_name, color="#FFFFFF", size=18)
        btn.setIcon(icon)
        btn.setIconSize(QSize(18, 18))
        
    if on_click:
        btn.clicked.connect(lambda: on_click())
    return btn


def SecondaryButton(text, on_click=None, parent=None, icon_name=None, icon_color="#E0E0E0"):
    """Вторичная кнопка (серая). Поддерживает иконки без наездов."""
    btn = QPushButton(text, parent)
    btn.setObjectName("SecondaryBtn")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(40)
    
    # QSS кнопки. Если есть иконка, делаем отступ слева чуть больше для баланса.
    padding_left = "16px" if not icon_name else "12px"
    btn.setStyleSheet(f"""
        QPushButton#SecondaryBtn {{
            background-color: #333333;
            color: #E0E0E0;
            border: 1px solid #444444;
            border-radius: 8px;
            padding: 8px {padding_left};
            text-align: center;
        }}
        QPushButton#SecondaryBtn:hover {{
            background-color: #444444;
        }}
    """)

    if icon_name:
        icon = get_icon_simple(icon_name, color=icon_color, size=16)
        btn.setIcon(icon)
        btn.setIconSize(QSize(16, 16))

    if on_click:
        btn.clicked.connect(lambda: on_click())
    return btn


def StyledEntry(placeholder="", parent=None):
    """Поле ввода в тёмном стиле."""
    entry = QLineEdit(parent)
    entry.setObjectName("StyledEntry")
    entry.setPlaceholderText(placeholder)
    entry.setMinimumHeight(36)
    entry.setStyleSheet("""
        QLineEdit#StyledEntry {
            background-color: #2A2A2A;
            color: #E0E0E0;
            border: 1px solid #444444;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 14px;
        }
        QLineEdit#StyledEntry:focus {
            border: 1px solid #D42626;
        }
    """)
    return entry


# =========================================================
# АНИМИРОВАННЫЙ ПЛЕЙСХОЛДЕР
# =========================================================
class AnimatedPlaceholderEntry(QLineEdit):
    """Поле ввода с побуквенно «печатающимся» плейсхолдером."""

    TYPING_INTERVAL_MS = 45
    PAUSE_AFTER_TYPING_MS = 1500
    PAUSE_AFTER_ERASING_MS = 400

    def __init__(self, placeholder="", parent=None, interval_ms=None):
        super().__init__(parent)

        self._full_placeholder = placeholder or ""
        self._typed_len = 0
        self._animation_started = False
        self._phase = "typing"
        self._typing_interval = interval_ms or self.TYPING_INTERVAL_MS

        self._timer = QTimer(self)
        self._timer.setInterval(self._typing_interval)
        self._timer.timeout.connect(self._on_tick)

        self._pause_timer = QTimer(self)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.timeout.connect(self._on_pause_done)

        self.setObjectName("StyledEntry")
        self.setMinimumHeight(36)
        self.setStyleSheet("""
            QLineEdit#StyledEntry {
                background-color: #2A2A2A;
                color: #E0E0E0;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 14px;
            }
            QLineEdit#StyledEntry:focus {
                border: 1px solid #D42626;
            }
        """)

        QLineEdit.setPlaceholderText(self, "")
        self.textChanged.connect(self._on_text_changed)

    def setPlaceholderText(self, text):
        self._full_placeholder = text or ""
        self._reset_cycle()
        if self._should_animate():
            self._start()
        else:
            self._stop()
            self.update()

    def placeholderText(self):
        return self._full_placeholder

    def _should_animate(self):
        return bool(self._full_placeholder) and not self.text()

    def _reset_cycle(self):
        self._timer.stop()
        self._pause_timer.stop()
        self._typed_len = 0
        self._phase = "typing"

    def _start(self):
        self._reset_cycle()
        self.update()
        if not self._should_animate():
            return
        self._timer.setInterval(self._typing_interval)
        self._timer.start()

    def _stop(self):
        self._timer.stop()
        self._pause_timer.stop()

    def _on_tick(self):
        if not self._should_animate():
            self._stop()
            self.update()
            return

        if self._phase == "typing":
            if self._typed_len < len(self._full_placeholder):
                self._typed_len += 1
                self.update()
                if self._typed_len >= len(self._full_placeholder):
                    self._timer.stop()
                    self._phase = "pausing_after_typing"
                    self._pause_timer.start(self.PAUSE_AFTER_TYPING_MS)
            return

    def _on_pause_done(self):
        if not self._should_animate():
            self._stop()
            self.update()
            return

        if self._phase == "pausing_after_typing":
            self._typed_len = 0
            self.update()
            self._phase = "pausing_after_erasing"
            self._pause_timer.start(self.PAUSE_AFTER_ERASING_MS)
            return

        if self._phase == "pausing_after_erasing":
            self._phase = "typing"
            self._timer.setInterval(self._typing_interval)
            self._timer.start()
            self.update()
            return

    def _on_text_changed(self, text):
        if text:
            self._stop()
        elif self._should_animate() and not self.hasFocus():
            self._start()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.text() or self.hasFocus() or not self._full_placeholder:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#808080"))
        painter.setFont(self.font())

        rect = self.rect().adjusted(11, 0, -11, 0)
        visible = self._full_placeholder[:self._typed_len]

        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            visible,
        )
        painter.end()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._animation_started and self._should_animate():
            self._animation_started = True
            QTimer.singleShot(0, self._start)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._stop()
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if self._should_animate():
            self._start()
        self.update()

    def clear(self):
        super().clear()
        if self._should_animate():
            self._start()
        self.update()


def StyledCombo(items=None, parent=None):
    """Выпадающий список в тёмном стиле."""
    combo = QComboBox(parent)
    combo.setMinimumHeight(36)
    if items:
        combo.addItems(items)

    combo.setStyleSheet("""
        QComboBox {
            background-color: #2A2A2A;
            color: #E0E0E0;
            border: 1px solid #444444;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 14px;
        }
        QComboBox:hover { border: 1px solid #A0A0A0; }
        QComboBox:focus { border: 1px solid #D42626; }
        QComboBox::drop-down { border: none; width: 24px; }
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #A0A0A0;
            width: 0; height: 0; margin-right: 6px;
        }
    """)
    style_popup(combo)
    return combo


def Row(*widgets, spacing=10, parent=None):
    """Горизонтальный ряд виджетов."""
    row = QFrame(parent)
    row.setFrameShape(QFrame.Shape.NoFrame)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for w in widgets:
        layout.addWidget(w)
    return row


def VStack(*widgets, spacing=10, parent=None):
    """Вертикальный стек виджетов."""
    stack = QFrame(parent)
    stack.setFrameShape(QFrame.Shape.NoFrame)
    layout = QVBoxLayout(stack)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for w in widgets:
        layout.addWidget(w)
    return stack