# ui/components/dialogs.py
"""
Всплывающие окна для Core V3.0.

ИЗМЕНЕНИЯ:
- Убран зелёный цвет для success. Теперь success — серый (#A0A0A0).
- Все остальные цвета (info, warning, error, question) оставлены.
"""
import ctypes
import sys

from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication, QWidget, QLineEdit
)

from ui.icons import get_icon_simple
from utils.logger import log


# =========================================================
# ТЁМНАЯ СИСТЕМНАЯ ШАПКА (Windows DWM API)
# =========================================================
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19


def _apply_dark_title_bar(widget):
    """Красит системный заголовок окна в тёмный цвет."""
    if sys.platform != "win32":
        return

    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(1)

        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )

        if result != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
    except Exception as e:
        log.debug(f"Не удалось применить тёмную шапку: {e}")


# =========================================================
# ИКОНКИ ПО ТИПУ (SVG, не эмодзи)
# =========================================================
DIALOG_ICONS = {
    "info":     "info",
    "success":  "check",
    "warning":  "alert-triangle",
    "error":    "x",
    "question": "help-circle",
}

DIALOG_COLOR_KEYS = {
    "info":     "button",
    "success":  "text_dim",  # СЕРЫЙ, не зелёный
    "warning":  "warning",
    "error":    "error",
    "question": "button",
}

DIALOG_COLOR_FALLBACK = {
    "info":     "#6366f1",
    "success":  "#A0A0A0",  # СЕРЫЙ, не зелёный
    "warning":  "#FFD700",
    "error":    "#FF5252",
    "question": "#D42626",
}


def _get_accent_color(msg_type, colors):
    """Возвращает цвет акцента для типа диалога."""
    key = DIALOG_COLOR_KEYS.get(msg_type, "button")

    if colors and key in colors:
        return colors[key]

    return DIALOG_COLOR_FALLBACK.get(msg_type, "#D42626")


# =========================================================
# КРАСИВОЕ КАСТОМНОЕ ОКНО
# =========================================================
class CustomMessageBox(QDialog):
    """Красивое модальное окно в стиле программы."""

    def __init__(self, parent, title, message, msg_type="info",
                 buttons=None,
                 bg="#1B1B1B", card="#222222", text="#E0E0E0",
                 button="#D42626", hover="#B71C1C",
                 text_dim="#A0A0A0", border="#333333"):
        super().__init__(parent)

        self.parent_window = parent
        self.error_text = message
        self.msg_type = msg_type
        self._buttons = buttons if buttons else ["ОК"]
        self._colors = {
            "bg": bg, "card": card, "text": text,
            "button": button, "hover": hover,
            "text_dim": text_dim, "border": border,
        }

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setMaximumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
            }}
            QFrame#Container {{
                background-color: {card};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        container = QFrame(self)
        container.setObjectName("Container")
        outer_layout.addWidget(container)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 24, 24, 24)
        container_layout.setSpacing(14)

        # Иконка (SVG)
        accent = _get_accent_color(msg_type, self._colors)
        icon_name = DIALOG_ICONS.get(msg_type, "info")

        icon_circle = QLabel(container)
        icon_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_circle.setFixedSize(56, 56)
        icon_circle.setStyleSheet(f"""
            background-color: {accent};
            border-radius: 28px;
        """)

        icon = get_icon_simple(icon_name, color="#FFFFFF", size=28)
        if not icon.isNull():
            icon_circle.setPixmap(icon.pixmap(28, 28))

        icon_wrapper = QHBoxLayout()
        icon_wrapper.addStretch()
        icon_wrapper.addWidget(icon_circle)
        icon_wrapper.addStretch()
        container_layout.addLayout(icon_wrapper)

        msg_label = QLabel(message, container)
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_label.setFont(QFont("Segoe UI", 11))
        msg_label.setStyleSheet(f"color: {text};")
        container_layout.addWidget(msg_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        if msg_type == "error":
            self.copy_btn = QPushButton(" Скопировать", container)
            self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.copy_btn.setMinimumHeight(38)
            self.copy_btn.setMinimumWidth(140)
            icon_copy = get_icon_simple("copy", color=text_dim, size=14)
            if not icon_copy.isNull():
                self.copy_btn.setIcon(icon_copy)
                self.copy_btn.setIconSize(QSize(14, 14))
            self.copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {text_dim};
                    border: 1px solid {border};
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {border};
                }}
            """)
            self.copy_btn.clicked.connect(self._copy_error)
            btn_layout.addWidget(self.copy_btn)

        self._button_widgets = []
        for btn_text in self._buttons:
            is_primary = btn_text in ("ОК", "Да")

            btn = QPushButton(btn_text, container)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(38)
            btn.setMinimumWidth(120)

            if is_primary:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {button};
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 8px 16px;
                        font-size: 14px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {hover};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {text};
                        border: 1px solid {border};
                        border-radius: 8px;
                        padding: 8px 16px;
                        font-size: 14px;
                    }}
                    QPushButton:hover {{
                        background-color: {border};
                    }}
                """)

            if btn_text == "ОК":
                btn.clicked.connect(self._on_ok)
            elif btn_text == "Да":
                btn.clicked.connect(self._on_yes)
            elif btn_text == "Нет":
                btn.clicked.connect(self._on_no)
            else:
                btn.clicked.connect(self._on_ok)

            btn_layout.addWidget(btn)
            self._button_widgets.append(btn)

        btn_layout.addStretch()
        container_layout.addLayout(btn_layout)

        self._center_on_parent()

        _apply_dark_title_bar(self)
        QTimer.singleShot(0, lambda: _apply_dark_title_bar(self))

        self.setFocus()

    def showEvent(self, event):
        super().showEvent(event)
        _apply_dark_title_bar(self)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_ok()
        elif event.key() == Qt.Key.Key_Escape:
            self._on_no()
        else:
            super().keyPressEvent(event)

    def _on_ok(self):
        try:
            self.accept()
        except Exception:
            pass

    def _on_yes(self):
        try:
            self.accept()
        except Exception:
            pass

    def _on_no(self):
        try:
            self.reject()
        except Exception:
            pass

    def _center_on_parent(self):
        if self.parent_window is None:
            return

        try:
            self.adjustSize()
            parent_geo = self.parent_window.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)
        except Exception:
            try:
                screen = QApplication.primaryScreen().geometry()
                x = (screen.width() - self.width()) // 2
                y = (screen.height() - self.height()) // 2
                self.move(x, y)
            except Exception:
                pass

    def _copy_error(self):
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.error_text)

            self.copy_btn.setText(" Скопировано")
            self.copy_btn.setIcon(
                get_icon_simple("check", color="#4CAF50", size=14)
            )
            self.copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #4CAF50;
                    border: 1px solid #4CAF50;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 13px;
                }
            """)

            QTimer.singleShot(2000, self._reset_copy_btn)
        except Exception as e:
            log.warning(f"Не удалось скопировать: {e}")

    def _reset_copy_btn(self):
        try:
            self.copy_btn.setText(" Скопировать")
            self.copy_btn.setIcon(
                get_icon_simple("copy", color=self._colors['text_dim'], size=14)
            )
            c = self._colors
            self.copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c['text_dim']};
                    border: 1px solid {c['border']};
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {c['border']};
                }}
            """)
        except Exception:
            pass


# =========================================================
# ДИАЛОГ СМЕНЫ ПАРОЛЯ
# =========================================================
class PasswordDialog(QDialog):
    """Диалог смены пароля."""

    def __init__(self, parent,
                 bg="#1B1B1B", card="#222222", text="#E0E0E0",
                 button="#D42626", hover="#B71C1C",
                 text_dim="#A0A0A0", border="#333333"):
        super().__init__(parent)

        self._new_password = ""
        self._colors = {
            "bg": bg, "card": card, "text": text,
            "button": button, "hover": hover,
            "text_dim": text_dim, "border": border,
        }

        self.setWindowTitle("Сменить пароль")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setMaximumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
            }}
            QFrame#Container {{
                background-color: {card};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        container = QFrame(self)
        container.setObjectName("Container")
        outer_layout.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Смена пароля терминалов", container)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {text};")
        layout.addWidget(title)

        layout.addWidget(self._make_label("Текущий пароль:", container))
        self.entry_current = self._make_password_entry(container)
        layout.addWidget(self.entry_current)

        layout.addWidget(self._make_label("Новый пароль:", container))
        self.entry_new = self._make_password_entry(container)
        layout.addWidget(self.entry_new)

        layout.addWidget(self._make_label("Повторите новый пароль:", container))
        self.entry_confirm = self._make_password_entry(container)
        layout.addWidget(self.entry_confirm)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Отмена", container)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setMinimumHeight(38)
        btn_cancel.setMinimumWidth(120)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {border};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Сохранить", container)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setMinimumHeight(38)
        btn_save.setMinimumWidth(120)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {button};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
        """)
        btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(btn_save)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._center_on_parent()
        _apply_dark_title_bar(self)
        QTimer.singleShot(0, lambda: _apply_dark_title_bar(self))

        self.entry_current.setFocus()

    def _make_label(self, text, parent):
        lbl = QLabel(text, parent)
        lbl.setStyleSheet(f"color: {self._colors['text_dim']}; font-size: 12px;")
        return lbl

    def _make_password_entry(self, parent):
        entry = QLineEdit(parent)
        entry.setEchoMode(QLineEdit.EchoMode.Password)
        entry.setMinimumHeight(38)
        entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self._colors['bg']};
                color: {self._colors['text']};
                border: 1px solid {self._colors['border']};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {self._colors['button']};
            }}
        """)
        return entry

    def showEvent(self, event):
        super().showEvent(event)
        _apply_dark_title_bar(self)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_save()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def _on_save(self):
        new = self.entry_new.text()
        confirm = self.entry_confirm.text()

        if not new:
            self._show_error("Пароль не может быть пустым.")
            return
        if new != confirm:
            self._show_error("Пароли не совпадают.")
            return

        self._new_password = new
        self.accept()

    def _show_error(self, text):
        _show_dialog(
            self, "Ошибка", text, "error",
            colors=self._colors
        )

    def get_password(self):
        return self._new_password

    def _center_on_parent(self):
        parent = self.parent()
        if parent is None:
            return
        try:
            self.adjustSize()
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)
        except Exception:
            pass


# =========================================================
# ПРОСТЫЕ ОБЁРТКИ
# =========================================================
def _show_dialog(parent, title, message, msg_type, buttons=None, colors=None):
    """Создаёт и показывает CustomMessageBox с текущими цветами приложения."""
    if colors is None:
        colors = _get_colors(parent)

    box = CustomMessageBox(
        parent, title, message, msg_type,
        buttons=buttons,
        bg=colors.get("bg", "#1B1B1B"),
        card=colors.get("card", "#222222"),
        text=colors.get("text", "#E0E0E0"),
        button=colors.get("button", "#D42626"),
        hover=colors.get("hover", "#B71C1C"),
        text_dim=colors.get("text_dim", "#A0A0A0"),
        border=colors.get("border", "#333333"),
    )
    return box.exec()


def _get_colors(parent):
    """Пытается получить COLORS из родителя. Иначе — дефолт."""
    try:
        if parent is not None and hasattr(parent, "COLORS"):
            return parent.COLORS
        if parent is not None and hasattr(parent, "app") and hasattr(parent.app, "COLORS"):
            return parent.app.COLORS
    except Exception:
        pass
    return {}


def show_info(parent, title, message):
    """Информационное окно."""
    return _show_dialog(parent, title, message, "info", buttons=["ОК"])


def show_success(parent, title, message):
    """Успех."""
    return _show_dialog(parent, title, message, "success", buttons=["ОК"])


def show_warning(parent, title, message):
    """Предупреждение."""
    return _show_dialog(parent, title, message, "warning", buttons=["ОК"])


def show_error(parent, title, message):
    """Ошибка."""
    return _show_dialog(parent, title, message, "error", buttons=["ОК"])


def ask_confirm(parent, title, message) -> bool:
    """Да/Нет. Возвращает True, если «Да»."""
    result = _show_dialog(
        parent, title, message, "question",
        buttons=["Да", "Нет"]
    )
    return result == QDialog.DialogCode.Accepted


def ask_password(parent) -> str:
    """Диалог смены пароля. Возвращает новый пароль или пустую строку."""
    colors = _get_colors(parent)
    dialog = PasswordDialog(
        parent,
        bg=colors.get("bg", "#1B1B1B"),
        card=colors.get("card", "#222222"),
        text=colors.get("text", "#E0E0E0"),
        button=colors.get("button", "#D42626"),
        hover=colors.get("hover", "#B71C1C"),
        text_dim=colors.get("text_dim", "#A0A0A0"),
        border=colors.get("border", "#333333"),
    )
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_password()
    return ""