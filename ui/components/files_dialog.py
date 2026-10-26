# ui/components/files_dialog.py
"""
Внутренний файловый менеджер Core V3.0.

Открывается вместо проводника Windows при нажатии
«Открыть результат» в утилитах.

Возможности:
- Дерево папок слева: Готовые → подпапки (Кванты, Паллеты, ОС_МБП,
  Брак_утиль, Нарушения, Сводные).
- Список файлов справа: иконка, имя, размер, дата.
- Двойной клик по файлу — открыть (os.startfile).
- Drag-out в проводник Windows (перетащить файл наружу).
- Drag внутри Core между подпапками (перемещение; Ctrl — копирование).
- Ctrl+C — файл в буфер обмена как файл (вставляется в проводник).
- Контекстное меню: Открыть, Открыть папку, Скопировать путь,
  Копировать файл, Удалить.
- Кнопки «Обновить» и «Закрыть».

ИЗМЕНЕНИЯ:
- ФИКС: в FileListWidget подключён itemDoubleClicked → _on_double_click,
  который вызывает FilesDialog._open_file (os.startfile). Раньше двойной
  клик по файлу не открывал его — только через контекстное меню.
"""
import ctypes
import os
import shutil
import sys
from datetime import datetime

from PyQt6.QtCore import (
    Qt, QMimeData, QUrl, QSize, QTimer, QFileInfo, pyqtSignal
)
from PyQt6.QtGui import QFont, QDrag, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication, QTreeWidget, QTreeWidgetItem,
    QListWidget, QListWidgetItem, QAbstractItemView, QMenu,
    QSplitter, QWidget
)

from config import FOLDERS
from ui.icons import get_icon_simple
from utils.logger import log


# =========================================================
# ТЁМНАЯ СИСТЕМНАЯ ШАПКА
# =========================================================
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19


def _apply_dark_title_bar(widget):
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
        log.debug(f"files_dialog: не удалось применить тёмную шапку: {e}")


# =========================================================
# ФОРМАТИРОВАНИЕ
# =========================================================
def _format_size(size_bytes: int) -> str:
    try:
        size = float(size_bytes)
    except (TypeError, ValueError):
        return "—"

    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if size < 1024.0:
            if unit == "Б":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} ТБ"


def _format_mtime(mtime: float) -> str:
    try:
        return datetime.fromtimestamp(mtime).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return "—"


def _file_icon_name(name: str) -> str:
    lower = name.lower()
    if lower.endswith((".xlsx", ".xls")):
        return "table"
    if lower.endswith((".txt", ".log")):
        return "file-text"
    if lower.endswith((".png", ".jpg", ".jpeg", ".bmp")):
        return "image"
    if lower.endswith((".zip", ".7z", ".rar")):
        return "archive"
    return "file"


# =========================================================
# ДИАЛОГ
# =========================================================
class FilesDialog(QDialog):
    """Внутренний файловый менеджер «Готовые»."""

    def __init__(self, parent, folder_key="info",
                 bg="#1B1B1B", card="#222222", text="#E0E0E0",
                 button="#D42626", hover="#B71C1C",
                 text_dim="#A0A0A0", border="#333333"):
        super().__init__(parent)

        self._colors = {
            "bg": bg, "card": card, "text": text,
            "button": button, "hover": hover,
            "text_dim": text_dim, "border": border,
        }
        self._folder_key = folder_key
        self._current_path = ""

        self.setWindowTitle("Готовые файлы — Core V3.0")
        self.setModal(True)
        self.resize(1000, 650)
        self.setMinimumSize(760, 480)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
            }}
            QFrame#Container {{
                background-color: {card};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QTreeWidget, QListWidget {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }}
            QTreeWidget::item, QListWidget::item {{
                padding: 6px;
                border-radius: 4px;
            }}
            QTreeWidget::item:selected, QListWidget::item:selected {{
                background-color: {button};
                color: white;
            }}
            QTreeWidget::item:hover, QListWidget::item:hover {{
                background-color: {border};
            }}
            QHeaderView::section {{
                background-color: {card};
                color: {text_dim};
                border: none;
                padding: 4px;
            }}
        """)

        self._setup_ui()
        self._populate_tree()
        self._select_initial_folder()

        _apply_dark_title_bar(self)
        QTimer.singleShot(0, lambda: _apply_dark_title_bar(self))

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        container = QFrame(self)
        container.setObjectName("Container")
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("ГОТОВЫЕ ФАЙЛЫ", container)
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {self._colors['text']};")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal, container)

        # --- Дерево папок ---
        self.tree = QTreeWidget(splitter)
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(220)
        self.tree.setMaximumWidth(320)
        self.tree.itemClicked.connect(self._on_tree_click)
        splitter.addWidget(self.tree)

        # --- Список файлов ---
        self.list_widget = FileListWidget(splitter, self)
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list_widget.setDragEnabled(True)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setDropIndicatorShown(True)
        self.list_widget.setDragDropMode(
            QAbstractItemView.DragDropMode.DragDrop
        )
        self.list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.list_widget.customContextMenuRequested.connect(
            self._on_context_menu
        )
        splitter.addWidget(self.list_widget)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 740])

        layout.addWidget(splitter, 1)

        self.status_label = QLabel("", container)
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet(
            f"color: {self._colors['text_dim']};"
        )
        layout.addWidget(self.status_label)

        # --- Кнопки ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_refresh = self._make_button(
            "Обновить", primary=False, parent=container
        )
        btn_refresh.clicked.connect(self._refresh_current)
        btn_row.addWidget(btn_refresh)

        btn_row.addStretch()

        btn_close = self._make_button(
            "Закрыть", primary=True, parent=container
        )
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _make_button(self, text, primary=True, parent=None):
        btn = QPushButton(text, parent)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(38)
        btn.setMinimumWidth(130)

        c = self._colors
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c['button']};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {c['hover']};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c['text']};
                    border: 1px solid {c['border']};
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {c['border']};
                }}
            """)
        return btn

    # =========================================================
    # ДЕРЕВО ПАПОК
    # =========================================================
    def _populate_tree(self):
        self.tree.clear()

        # Корневой узел — «Готовые»
        root_path = FOLDERS.get("info")
        if not root_path:
            return

        root_item = QTreeWidgetItem(self.tree, ["Готовые"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, root_path)
        root_item.setExpanded(True)

        icon_folder = get_icon_simple(
            "folder", color=self._colors['button'], size=16
        )
        if not icon_folder.isNull():
            root_item.setIcon(0, icon_folder)

        # Подпапки
        sub_order = [
            ("kv", "Кванты"),
            ("pal", "Паллеты"),
            ("os_mbp", "ОС_МБП"),
            ("brak_util", "Брак_утиль"),
            ("violations", "Нарушения"),
            ("pivot", "Сводные"),
        ]
        for key, label in sub_order:
            path = FOLDERS.get(key)
            if not path or not os.path.isdir(path):
                continue
            item = QTreeWidgetItem(root_item, [label])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            if not icon_folder.isNull():
                item.setIcon(0, icon_folder)

    def _select_initial_folder(self):
        key = self._folder_key or "info"
        target_path = FOLDERS.get(key)

        if not target_path:
            target_path = FOLDERS.get("info")

        # Ищем узел с этим путём
        root = self.tree.topLevelItem(0)
        if root is None:
            return

        if root.data(0, Qt.ItemDataRole.UserRole) == target_path:
            self.tree.setCurrentItem(root)
            self._on_tree_click(root, 0)
            return

        for i in range(root.childCount()):
            child = root.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == target_path:
                self.tree.setCurrentItem(child)
                self._on_tree_click(child, 0)
                return

        # Fallback — корень
        self.tree.setCurrentItem(root)
        self._on_tree_click(root, 0)

    def _on_tree_click(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not os.path.isdir(path):
            return
        self._current_path = path
        self._load_files(path)

    # =========================================================
    # СПИСОК ФАЙЛОВ
    # =========================================================
    def _load_files(self, path):
        self.list_widget.clear()

        try:
            entries = list(os.scandir(path))
        except (OSError, PermissionError) as e:
            self.status_label.setText(f"Ошибка чтения папки: {e}")
            return

        files = []
        for entry in entries:
            try:
                if not entry.is_file():
                    continue
                stat = entry.stat()
                files.append((entry.name, stat.st_size, stat.st_mtime))
            except (OSError, PermissionError):
                continue

        files.sort(key=lambda x: x[0].lower())

        for name, size, mtime in files:
            item = QListWidgetItem()
            item.setText(
                f"{name}    —    {_format_size(size)}    —    {_format_mtime(mtime)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, os.path.join(path, name))
            item.setData(
                Qt.ItemDataRole.UserRole + 1,
                f"{name}\t{size}\t{mtime}"
            )
            item.setToolTip(os.path.join(path, name))

            icon_name = _file_icon_name(name)
            icon = get_icon_simple(
                icon_name, color=self._colors['text'], size=16
            )
            if not icon.isNull():
                item.setIcon(icon)

            self.list_widget.addItem(item)

        if files:
            self.status_label.setText(
                f"Файлов: {len(files)}    Папка: {os.path.basename(path)}"
            )
        else:
            self.status_label.setText(
                f"Папка пуста: {os.path.basename(path)}"
            )

    def _refresh_current(self):
        if self._current_path and os.path.isdir(self._current_path):
            self._load_files(self._current_path)

    # =========================================================
    # КОНТЕКСТНОЕ МЕНЮ
    # =========================================================
    def _on_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if item is None:
            return

        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return

        c = self._colors
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {c['card']};
                color: {c['text']};
                border: 1px solid {c['border']};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {c['button']};
                color: white;
            }}
        """)

        act_open = menu.addAction("Открыть")
        act_open_folder = menu.addAction("Открыть папку")
        menu.addSeparator()
        act_copy_path = menu.addAction("Скопировать путь")
        act_copy_file = menu.addAction("Копировать файл")
        menu.addSeparator()
        act_delete = menu.addAction("Удалить")

        chosen = menu.exec(self.list_widget.mapToGlobal(pos))
        if chosen is None:
            return

        if chosen == act_open:
            self._open_file(path)
        elif chosen == act_open_folder:
            self._open_folder_internal(os.path.dirname(path))
        elif chosen == act_copy_path:
            QApplication.clipboard().setText(path)
            self.status_label.setText("Путь скопирован")
        elif chosen == act_copy_file:
            self._copy_files_to_clipboard([path])
            self.status_label.setText("Файл скопирован в буфер обмена")
        elif chosen == act_delete:
            self._delete_files([path])

    # =========================================================
    # ДЕЙСТВИЯ С ФАЙЛАМИ
    # =========================================================
    def _open_file(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            self.status_label.setText(f"Не удалось открыть: {e}")
            log.warning(f"files_dialog: не удалось открыть {path}: {e}")

    def _open_folder_internal(self, path):
        root = self.tree.topLevelItem(0)
        if root is None:
            return

        if root.data(0, Qt.ItemDataRole.UserRole) == path:
            self.tree.setCurrentItem(root)
            self._on_tree_click(root, 0)
            return

        for i in range(root.childCount()):
            child = root.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == path:
                self.tree.setCurrentItem(child)
                self._on_tree_click(child, 0)
                return

    def _copy_files_to_clipboard(self, paths):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
        QApplication.clipboard().setMimeData(mime)

    def _delete_files(self, paths):
        from ui.components.dialogs import ask_confirm

        names = "\n".join(os.path.basename(p) for p in paths)
        ok = ask_confirm(
            self,
            "Удалить файлы?",
            f"Будет удалено:\n{names}\n\nПродолжить?"
        )
        if not ok:
            return

        deleted = 0
        failed = 0
        for p in paths:
            try:
                os.remove(p)
                deleted += 1
            except (OSError, PermissionError) as e:
                failed += 1
                log.warning(f"files_dialog: не удалось удалить {p}: {e}")

        self._refresh_current()
        if failed:
            self.status_label.setText(
                f"Удалено: {deleted}, ошибок: {failed}"
            )
        else:
            self.status_label.setText(f"Удалено файлов: {deleted}")

    # =========================================================
    # DRAG & DROP ВНУТРИ CORE
    # =========================================================
    def handle_internal_drop(self, paths, target_folder, copy_mode=False):
        """Перемещает (или копирует) файлы в целевую папку."""
        if not target_folder or not os.path.isdir(target_folder):
            return

        moved = 0
        copied = 0
        failed = 0

        for src in paths:
            if not os.path.isfile(src):
                continue

            dst = os.path.join(target_folder, os.path.basename(src))

            if os.path.abspath(src) == os.path.abspath(dst):
                continue

            if os.path.exists(dst):
                from ui.components.dialogs import ask_confirm
                ok = ask_confirm(
                    self,
                    "Файл уже существует",
                    f"{os.path.basename(dst)}\n\nПерезаписать?"
                )
                if not ok:
                    failed += 1
                    continue

            try:
                if copy_mode:
                    shutil.copy2(src, dst)
                    copied += 1
                else:
                    shutil.move(src, dst)
                    moved += 1
            except (OSError, PermissionError) as e:
                failed += 1
                log.warning(
                    f"files_dialog: не удалось переместить {src} → {dst}: {e}"
                )

        self._refresh_current()
        parts = []
        if moved:
            parts.append(f"перемещено {moved}")
        if copied:
            parts.append(f"скопировано {copied}")
        if failed:
            parts.append(f"ошибок {failed}")
        if parts:
            self.status_label.setText(", ".join(parts).capitalize())


# =========================================================
# СПИСОК ФАЙЛОВ С DRAG-OUT В ПРОВОДНИК
# =========================================================
class FileListWidget(QListWidget):
    """Список файлов: drag-out в проводник, drop внутри Core,
    двойной клик — открыть файл (os.startfile)."""

    def __init__(self, parent, dialog: FilesDialog):
        super().__init__(parent)
        self._dialog = dialog

        # ФИКС: двойной клик по файлу открывает его
        self.itemDoubleClicked.connect(self._on_double_click)

    def _on_double_click(self, item):
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self._dialog._open_file(path)

    def startDrag(self, supported_actions):
        items = self.selectedItems()
        if not items:
            return

        paths = []
        for item in items:
            p = item.data(Qt.ItemDataRole.UserRole)
            if p and os.path.isfile(p):
                paths.append(p)

        if not paths:
            return

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])

        drag = QDrag(self)
        drag.setMimeData(mime)

        icon = self.currentItem().icon()
        if not icon.isNull():
            drag.setPixmap(icon.pixmap(32, 32))

        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return

        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                p = url.toLocalFile()
                if os.path.isfile(p):
                    paths.append(p)

        if not paths:
            event.ignore()
            return

        target = self._dialog._current_path
        if not target:
            event.ignore()
            return

        copy_mode = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self._dialog.handle_internal_drop(paths, target, copy_mode=copy_mode)
        event.acceptProposedAction()