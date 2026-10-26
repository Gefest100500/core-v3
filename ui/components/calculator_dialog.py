# ui/components/calculator_dialog.py
"""
Мини-калькулятор в стиле Core.
"""
import ctypes
from PyQt6.QtCore import Qt, QSize, QEvent, QObject
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLineEdit, QPushButton, QWidget
)

from ui.icons import get_icon_simple


# =========================================================
# ТЁМНАЯ ШАПКА (скопировано из main.py)
# =========================================================
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19


def _apply_dark_title_bar(widget):
    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(1)
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value),
        )
        if result != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
                ctypes.byref(value), ctypes.sizeof(value),
            )
    except Exception:
        pass


class _DarkTitleBarFilter(QObject):
    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self._widget = widget

    def eventFilter(self, obj, event):
        et = event.type()
        if et in (
            QEvent.Type.Show, QEvent.Type.ShowToParent,
            QEvent.Type.WindowStateChange, QEvent.Type.WindowActivate,
        ):
            _apply_dark_title_bar(self._widget)
        return super().eventFilter(obj, event)


def _install_dark_title_bar(widget):
    _apply_dark_title_bar(widget)
    flt = _DarkTitleBarFilter(widget)
    widget.installEventFilter(flt)
    widget._dark_title_filter = flt


class CalculatorDialog(QDialog):
    def __init__(self, parent=None, colors=None):
        super().__init__(parent)
        self._colors = colors or {}
        self.setWindowTitle("Калькулятор")
        self.setFixedSize(300, 400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        _install_dark_title_bar(self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.display = QLineEdit(self)
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self._colors.get('bg', '#1B1B1B')};
                color: {self._colors.get('text', '#E0E0E0')};
                border: 1px solid {self._colors.get('border', '#333333')};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 20px;
                font-family: 'Consolas', monospace;
            }}
        """)
        self.display.setText("0")
        layout.addWidget(self.display)

        grid = QGridLayout()
        grid.setSpacing(6)

        buttons = [
            ("C", 0, 0), ("±", 0, 1), ("%", 0, 2), ("/", 0, 3),
            ("7", 1, 0), ("8", 1, 1), ("9", 1, 2), ("*", 1, 3),
            ("4", 2, 0), ("5", 2, 1), ("6", 2, 2), ("-", 2, 3),
            ("1", 3, 0), ("2", 3, 1), ("3", 3, 2), ("+", 3, 3),
            ("0", 4, 0), (".", 4, 1), ("=", 4, 2),
        ]

        for text, row, col in buttons:
            btn = QPushButton(text, self)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(50)

            if text in ("C", "±", "%", "/", "*", "-", "+", "="):
                bg = self._colors.get('button', '#D42626')
                hover = self._colors.get('hover', '#B71C1C')
                color = "#FFFFFF"
            else:
                bg = self._colors.get('card', '#222222')
                hover = self._colors.get('sidebar', '#2A2A2A')
                color = self._colors.get('text', '#E0E0E0')

            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {color};
                    border: 1px solid {self._colors.get('border', '#333333')};
                    border-radius: 6px;
                    font-size: 16px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {hover};
                }}
            """)
            btn.clicked.connect(lambda checked=False, t=text: self._on_click(t))
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

    def _on_click(self, text):
        current = self.display.text()
        try:
            if text == "C":
                self.display.setText("0")
            elif text == "±":
                if current and current != "0":
                    if current.startswith("-"):
                        self.display.setText(current[1:])
                    else:
                        self.display.setText("-" + current)
            elif text == "%":
                if current:
                    val = float(current) / 100
                    self.display.setText(str(val))
            elif text == "=":
                expr = current.replace("×", "*").replace("÷", "/")
                result = eval(expr, {"__builtins__": None}, {})
                if isinstance(result, float) and result.is_integer():
                    result = int(result)
                self.display.setText(str(result))
            elif text in ("+", "-", "*", "/"):
                if current and current[-1] in "+-*/":
                    self.display.setText(current[:-1] + text)
                else:
                    self.display.setText(current + text)
            else:
                if current == "0" and text != ".":
                    self.display.setText(text)
                elif text == "." and "." in current:
                    pass
                else:
                    self.display.setText(current + text)
        except Exception:
            self.display.setText("Ошибка")

    def keyPressEvent(self, event):
        key = event.key()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            self._on_click(str(key - Qt.Key.Key_0))
        elif key == Qt.Key.Key_Plus:
            self._on_click("+")
        elif key == Qt.Key.Key_Minus:
            self._on_click("-")
        elif key == Qt.Key.Key_Asterisk:
            self._on_click("*")
        elif key == Qt.Key.Key_Slash:
            self._on_click("/")
        elif key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
            self._on_click("=")
        elif key == Qt.Key.Key_Backspace:
            current = self.display.text()
            if len(current) > 1:
                self.display.setText(current[:-1])
            else:
                self.display.setText("0")
        elif key == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)