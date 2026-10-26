# ui/components/notepad_dialog.py
"""
Блокнот в стиле Core с возможностью просмотра старых записей.
- Слева список заметок (файлы .txt в %LOCALAPPDATA%/Core_V3_0/notes/).
- Справа текст выбранной заметки (редактируется).
- Кнопки: Новая, Удалить.
- Автосохранение при вводе.
- Тёмная шапка окна.
- Кастомный диалог подтверждения (на русском).
"""
import os
import ctypes
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, QSize, QEvent, QObject
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QSplitter,
    QMessageBox, QWidget
)

from utils.file_utils import get_data_dir
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


# =========================================================
# КАСТОМНЫЙ ДИАЛОГ ПОДТВЕРЖДЕНИЯ
# =========================================================
class CoreConfirmDialog(QDialog):
    def __init__(self, parent=None, colors=None, title="", text=""):
        super().__init__(parent)
        self._colors = colors or {}
        self.setWindowTitle(title)
        self.setFixedSize(400, 180)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        _install_dark_title_bar(self)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {self._colors.get('text', '#E0E0E0')}; font-size: 14px;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_no = QPushButton("Нет")
        btn_no.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_no.setFixedSize(80, 32)
        btn_no.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {self._colors.get('text', '#E0E0E0')};
                border: 1px solid {self._colors.get('border', '#333333')};
                border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {self._colors.get('sidebar', '#2A2A2A')}; }}
        """)
        btn_no.clicked.connect(self.reject)
        btn_layout.addWidget(btn_no)

        btn_yes = QPushButton("Да")
        btn_yes.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_yes.setFixedSize(80, 32)
        btn_yes.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._colors.get('error', '#FF5252')};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: #D32F2F; }}
        """)
        btn_yes.clicked.connect(self.accept)
        btn_layout.addWidget(btn_yes)

        layout.addLayout(btn_layout)


class NotepadDialog(QDialog):
    def __init__(self, parent=None, colors=None):
        super().__init__(parent)
        self._colors = colors or {}
        self.setWindowTitle("Блокнот ревизора")
        self.resize(800, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        _install_dark_title_bar(self)

        self._notes_dir = os.path.join(get_data_dir(), "notes")
        os.makedirs(self._notes_dir, exist_ok=True)

        self._current_file = None

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(1000)
        self._save_timer.timeout.connect(self._save_current)

        self._setup_ui()
        self._load_notes_list()

        if self.list_widget.count() == 0:
            self._create_new_note()
        else:
            self.list_widget.setCurrentRow(0)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Левая панель
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        lbl_notes = QLabel("Мои записи")
        lbl_notes.setStyleSheet(f"color: {self._colors.get('text_dim', '#A0A0A0')}; font-size: 12px; font-weight: bold;")
        left_layout.addWidget(lbl_notes)

        self.list_widget = QListWidget(left_panel)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {self._colors.get('bg', '#1B1B1B')};
                color: {self._colors.get('text', '#E0E0E0')};
                border: 1px solid {self._colors.get('border', '#333333')};
                border-radius: 6px;
                font-size: 13px;
                outline: none;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
                margin-bottom: 2px;
            }}
            QListWidget::item:selected {{
                background-color: {self._colors.get('button', '#D42626')};
                color: #FFFFFF;
            }}
            QListWidget::item:hover {{
                background-color: {self._colors.get('sidebar', '#2A2A2A')};
            }}
        """)
        self.list_widget.currentItemChanged.connect(self._on_note_selected)
        left_layout.addWidget(self.list_widget, 1)

        btn_new = QPushButton("  Новая")
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.setMinimumHeight(32)
        btn_new.setStyleSheet(self._btn_style())
        icon_new = get_icon_simple("file", color=self._colors.get('text', '#E0E0E0'), size=14)
        if not icon_new.isNull():
            btn_new.setIcon(icon_new)
            btn_new.setIconSize(QSize(14, 14))
        btn_new.clicked.connect(self._create_new_note)
        left_layout.addWidget(btn_new)

        btn_delete = QPushButton("  Удалить")
        btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_delete.setMinimumHeight(32)
        btn_delete.setStyleSheet(self._btn_danger_style())
        icon_del = get_icon_simple("trash", color=self._colors.get('error', '#FF5252'), size=14)
        if not icon_del.isNull():
            btn_delete.setIcon(icon_del)
            btn_delete.setIconSize(QSize(14, 14))
        btn_delete.clicked.connect(self._delete_current_note)
        left_layout.addWidget(btn_delete)

        splitter.addWidget(left_panel)

        # Правая панель
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.title_label = QLabel("Нет заметки")
        self.title_label.setStyleSheet(f"color: {self._colors.get('text', '#E0E0E0')}; font-size: 14px; font-weight: bold;")
        right_layout.addWidget(self.title_label)

        self.editor = QTextEdit(right_panel)
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self._colors.get('bg', '#1B1B1B')};
                color: {self._colors.get('text', '#E0E0E0')};
                border: 1px solid {self._colors.get('border', '#333333')};
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
                font-family: 'Segoe UI', sans-serif;
            }}
        """)
        self.editor.textChanged.connect(self._on_text_changed)
        right_layout.addWidget(self.editor, 1)

        hint = QLabel("Автосохранение включено")
        hint.setStyleSheet(f"color: {self._colors.get('text_dim', '#A0A0A0')}; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_layout.addWidget(hint)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([250, 550])

        layout.addWidget(splitter, 1)

    def _btn_style(self):
        return f"""
            QPushButton {{
                background-color: {self._colors.get('card', '#222222')};
                color: {self._colors.get('text', '#E0E0E0')};
                border: 1px solid {self._colors.get('border', '#333333')};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {self._colors.get('sidebar', '#2A2A2A')};
            }}
        """

    def _btn_danger_style(self):
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {self._colors.get('error', '#FF5252')};
                border: 1px solid {self._colors.get('error', '#FF5252')};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {self._colors.get('error', '#FF5252')};
                color: #FFFFFF;
            }}
        """

    def _load_notes_list(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        try:
            files = [f for f in os.listdir(self._notes_dir) if f.endswith(".txt")]
            files.sort(key=lambda f: os.path.getmtime(os.path.join(self._notes_dir, f)), reverse=True)
            for filename in files:
                path = os.path.join(self._notes_dir, filename)
                name = filename[:-4]
                try:
                    dt = datetime.strptime(name, "%Y-%m-%d_%H-%M-%S")
                    display = dt.strftime("%d.%m.%Y %H:%M")
                except ValueError:
                    display = name
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.list_widget.addItem(item)
        except Exception:
            pass
        self.list_widget.blockSignals(False)

    def _create_new_note(self):
        if self._current_file:
            self._save_current()

        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{now}.txt"
        path = os.path.join(self._notes_dir, filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось создать заметку:\n{e}")
            return

        self._load_notes_list()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self.list_widget.setCurrentRow(i)
                break

    def _on_note_selected(self, current, _previous):
        if current is None:
            return
        if self._current_file and self._current_file != current.data(Qt.ItemDataRole.UserRole):
            self._save_current()

        path = current.data(Qt.ItemDataRole.UserRole)
        self._current_file = path

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            content = ""

        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)

        name = os.path.basename(path)[:-4]
        try:
            dt = datetime.strptime(name, "%Y-%m-%d_%H-%M-%S")
            display = dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            display = name
        self.title_label.setText(f"Запись: {display}")

    def _on_text_changed(self):
        self._save_timer.start()

    def _save_current(self):
        if not self._current_file:
            return
        try:
            with open(self._current_file, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
        except Exception:
            pass

    def _delete_current_note(self):
        if not self._current_file:
            return
        
        # ИСПОЛЬЗУЕМ КАСТОМНЫЙ ДИАЛОГ ВМЕСТО QMessageBox
        dialog = CoreConfirmDialog(
            self, self._colors,
            title="Удалить запись?",
            text="Вы уверены, что хотите удалить эту запись?"
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            os.remove(self._current_file)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось удалить:\n{e}")
            return

        self._current_file = None
        self.editor.clear()
        self.title_label.setText("Нет заметки")
        self._load_notes_list()

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        else:
            self._create_new_note()

    def closeEvent(self, event):
        if self._save_timer.isActive():
            self._save_timer.stop()
        self._save_current()
        super().closeEvent(event)