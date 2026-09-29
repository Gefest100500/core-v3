# ui/components/dialogs.py
"""
Всплывающие окна для Core V3.0.

Два уровня:
1. Simple-функции: show_info, show_error, show_success, ask_confirm
   (на базе QMessageBox, быстро и просто)

2. CustomMessageBox — красивое модальное окно в стиле программы:
   - иконка в цветном круге
   - цвет по типу (info/success/warning/error)
   - кнопка «Скопировать» для ошибок
   - центрируется относительно родителя

В PyQt6 Ctrl+V и копирование работают через QApplication.clipboard() —
без pyperclip и без костылей.
"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication, QWidget, QMessageBox
)

from utils.logger import log


# =========================================================
# ЦВЕТА И ИКОНКИ ПО ТИПУ
# =========================================================
DIALOG_TYPES = {
    "info":    {"icon": "ℹ️", "color": "#6366f1"},
    "success": {"icon": "✅", "color": "#4CAF50"},
    "warning": {"icon": "⚠️", "color": "#FFD700"},
    "error":   {"icon": "❌", "color": "#D42626"},
}


# =========================================================
# ПРОСТЫЕ ОБЁРТКИ НА БАЗЕ QMessageBox
# =========================================================
def _make_simple_box(parent, title, message, icon_type, buttons):
    """Создаёт и стилизует QMessageBox."""
    box = QMessageBox(parent)
    box.setIcon(icon_type)
    box.setWindowTitle(title)
    box.setText(message)
    box.setStandardButtons(buttons)
    box.setStyleSheet("""
        QMessageBox {
            background-color: #1B1B1B;
            color: #E0E0E0;
        }
        QMessageBox QLabel {
            color: #E0E0E0;
            font-size: 14px;
            min-width: 300px;
        }
        QMessageBox QPushButton {
            background-color: #D42626;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            min-width: 80px;
            font-size: 13px;
        }
        QMessageBox QPushButton:hover {
            background-color: #B71C1C;
        }
    """)
    return box


def show_info(parent, title, message):
    """Информационное окно."""
    box = _make_simple_box(
        parent, title, message,
        QMessageBox.Icon.Information,
        QMessageBox.StandardButton.Ok
    )
    box.exec()


def show_success(parent, title, message):
    """Успех."""
    box = _make_simple_box(
        parent, title, message,
        QMessageBox.Icon.Information,
        QMessageBox.StandardButton.Ok
    )
    box.exec()


def show_warning(parent, title, message):
    """Предупреждение."""
    box = _make_simple_box(
        parent, title, message,
        QMessageBox.Icon.Warning,
        QMessageBox.StandardButton.Ok
    )
    box.exec()


def show_error(parent, title, message):
    """Ошибка."""
    box = _make_simple_box(
        parent, title, message,
        QMessageBox.Icon.Critical,
        QMessageBox.StandardButton.Ok
    )
    box.exec()


def ask_confirm(parent, title, message) -> bool:
    """Да/Нет. True — если «Да»."""
    box = _make_simple_box(
        parent, title, message,
        QMessageBox.Icon.Question,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    box.setDefaultButton(QMessageBox.StandardButton.No)
    result = box.exec()
    return result == QMessageBox.StandardButton.Yes


# =========================================================
# КРАСИВОЕ КАСТОМНОЕ ОКНО
# =========================================================
class CustomMessageBox(QDialog):
    """Красивое модальное окно в стиле программы.

    Совместимо с оригинальным CTk-классом по API.

    Особенности:
    - иконка в цветном круге
    - цвет по типу (info/success/warning/error)
    - кнопка «Скопировать» для ошибок
    - центрируется относительно родителя
    - Enter и Escape закрывают
    """

    def __init__(self, parent, title, message, msg_type="info",
                 bg="#1B1B1B", card="#222222", text="#E0E0E0",
                 button="#D42626", hover="#B71C1C",
                 text_dim="#A0A0A0", border="#333333"):
        super().__init__(parent)

        self.parent_window = parent
        self.error_text = message
        self.msg_type = msg_type

        # Настройки окна
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 260)
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

        # --- Контейнер ---
        container = QFrame(self)
        container.setObjectName("Container")
        container.setGeometry(2, 2, 396, 256)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(12)

        # --- Иконка в круге ---
        cfg = DIALOG_TYPES.get(msg_type, DIALOG_TYPES["info"])
        icon = cfg["icon"]
        accent = cfg["color"]

        icon_circle = QLabel(icon, container)
        icon_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_circle.setFixedSize(60, 60)
        icon_circle.setStyleSheet(f"""
            background-color: {accent};
            color: white;
            border-radius: 30px;
            font-size: 30px;
        """)

        # Обёртка для центрирования
        icon_wrapper = QHBoxLayout()
        icon_wrapper.addStretch()
        icon_wrapper.addWidget(icon_circle)
        icon_wrapper.addStretch()
        container_layout.addLayout(icon_wrapper)

        # --- Текст ---
        msg_label = QLabel(message, container)
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_label.setFont(QFont("Segoe UI", 11))
        msg_label.setStyleSheet(f"color: {text};")
        container_layout.addWidget(msg_label)

        container_layout.addStretch()

        # --- Панель кнопок ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        # Кнопка «Скопировать» — только для ошибок
        if msg_type == "error":
            self.copy_btn = QPushButton("📋 Скопировать", container)
            self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.copy_btn.setMinimumHeight(38)
            self.copy_btn.setMinimumWidth(140)
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

        # Кнопка «ОК»
        ok_btn = QPushButton("ОК", container)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setMinimumHeight(38)
        ok_btn.setMinimumWidth(140)
        ok_btn.setStyleSheet(f"""
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
        ok_btn.clicked.connect(self._close)
        btn_layout.addWidget(ok_btn)

        btn_layout.addStretch()
        container_layout.addLayout(btn_layout)

        # --- Центрирование относительно родителя ---
        self._center_on_parent()

        # Enter и Escape
        self.setFocus()

    # =========================================================
    def keyPressEvent(self, event):
        """Enter и Escape закрывают окно."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter,
                           Qt.Key.Key_Escape):
            self._close()
        else:
            super().keyPressEvent(event)

    def _center_on_parent(self):
        """Центрирует окно относительно родителя."""
        if self.parent_window is None:
            return

        try:
            parent_geo = self.parent_window.geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)
        except Exception:
            # Fallback — центр экрана
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            self.move(x, y)

    def _copy_error(self):
        """Копирует текст ошибки в буфер обмена.

        В PyQt6 используется QApplication.clipboard() — работает всегда.
        """
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.error_text)

            self.copy_btn.setText("✅ Скопировано")
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
        """Сбрасывает кнопку «Скопировать» обратно."""
        try:
            self.copy_btn.setText("📋 Скопировать")
            self.copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #A0A0A0;
                    border: 1px solid #333333;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #333333;
                }
            """)
        except Exception:
            pass

    def _close(self):
        """Закрывает окно."""
        try:
            self.accept()
        except Exception:
            pass