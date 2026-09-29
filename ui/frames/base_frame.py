# ui/frames/base_frame.py
"""
Базовый класс для всех вкладок.

Все вкладки наследуются от BaseFrame и получают готовые методы:
- set_status / show_status — статус-бар
- start_progress / update_progress / finish_progress — прогресс
- show_error / show_success / show_warning / show_info — диалоги
- run_in_thread — безопасный запуск фоновой задачи в Qt
- run_on_ui — безопасный вызов в главном потоке из фонового
- open_folder — открыть папку

Плюс PlaceholderFrame — заглушка для нереализованных вкладок.

ИЗМЕНЕНИЯ:
- run_on_ui переведён на pyqtSignal (правильная доставка из фонового потока)
- убран winfo_exists (это Tkinter-метод, в PyQt его нет)
- добавлена проверка sip.isdeleted
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6 import sip

from ui.components.dialogs import CustomMessageBox
from utils.logger import log


class BaseFrame(QWidget):
    """Базовый класс для всех вкладок интерфейса."""

    TITLE = "Вкладка"

    # Сигнал для безопасного вызова UI-функций из фонового потока.
    # Qt автоматически доставляет его в поток, где живёт виджет (главный).
    _ui_call = pyqtSignal(object, tuple, dict)

    def __init__(self, parent, name=None, **kwargs):
        """
        Args:
            parent: главное окно AuditApp
            name: имя вкладки (например 'home')
        """
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.app = parent
        self.tab_name = name or "unknown"

        self.FONTS = parent.FONTS
        self.COLORS = parent.COLORS

        # Подключаем сигнал к обработчику. Живём в главном потоке —
        # значит, _execute_ui_call всегда вызывается в главном потоке.
        self._ui_call.connect(self._execute_ui_call)

    # =========================================================
    # СТАТУС-БАР
    # =========================================================
    def set_status(self, text, color=None):
        """Устанавливает текст в статус-бар."""
        if hasattr(self.app, "set_status"):
            self.app.set_status(text, color)

    def show_status(self, text, color=None):
        """Алиас для set_status (совместимость)."""
        self.set_status(text, color)

    # =========================================================
    # ПРОГРЕСС
    # =========================================================
    def start_progress(self, status_text="Обработка..."):
        """Запускает индикатор прогресса."""
        if hasattr(self.app, "start_progress"):
            self.app.start_progress(status_text)

    def update_progress(self, value):
        """Обновляет прогресс (0.0–1.0)."""
        if hasattr(self.app, "update_progress"):
            self.app.update_progress(value)

    def finish_progress(self, success=True, message=None):
        """Завершает прогресс."""
        if hasattr(self.app, "finish_progress"):
            self.app.finish_progress(success, message)

    # =========================================================
    # ДИАЛОГИ
    # =========================================================
    def _dialog(self, title, message, kind):
        """Общий конструктор диалога."""
        CustomMessageBox(
            self, title, message, kind,
            bg=self.COLORS.get("bg", "#1B1B1B"),
            card=self.COLORS.get("card", "#222222"),
            text=self.COLORS.get("text", "#E0E0E0"),
            button=self.COLORS.get("button", "#D42626"),
            hover=self.COLORS.get("hover", "#B71C1C"),
            text_dim=self.COLORS.get("text_dim", "#A0A0A0"),
            border=self.COLORS.get("border", "#333333"),
        ).exec()

    def show_error(self, title, message):
        self._dialog(title, message, "error")

    def show_success(self, title, message):
        self._dialog(title, message, "success")

    def show_warning(self, title, message):
        self._dialog(title, message, "warning")

    def show_info(self, title, message):
        self._dialog(title, message, "info")

    # =========================================================
    # ФОНОВЫЕ ЗАДАЧИ
    # =========================================================
    def run_in_thread(self, target, *args, **kwargs):
        """Запускает target в фоновом потоке.

        ВАЖНО: в Qt обновлять UI можно ТОЛЬКО из главного потока.
        Если target хочет обновить UI — используй self.run_on_ui(fn).
        """
        import threading
        threading.Thread(
            target=target,
            args=args,
            kwargs=kwargs,
            daemon=True
        ).start()

    def run_on_ui(self, fn, *args, **kwargs):
        """Выполняет fn в главном потоке Qt.

        Реализовано через pyqtSignal — Qt сам доставит вызов
        в поток, где живёт виджет (главный). Работает безопасно
        из любого фонового потока.
        """
        self._ui_call.emit(fn, args, kwargs)

    def _execute_ui_call(self, fn, args, kwargs):
        """Принимает сигнал и вызывает fn в главном потоке."""
        if sip.isdeleted(self):
            return
        try:
            fn(*args, **kwargs)
        except Exception as e:
            log.exception(f"Ошибка в run_on_ui callback: {e}")

    # =========================================================
    # УТИЛИТЫ
    # =========================================================
    def open_folder(self, folder_key):
        """Открывает папку по ключу FOLDERS."""
        if hasattr(self.app, "open_folder"):
            self.app.open_folder(folder_key)
        else:
            from config import FOLDERS
            import os
            path = FOLDERS.get(folder_key)
            if path and os.path.isdir(path):
                try:
                    os.startfile(path)
                except Exception as e:
                    log.warning(f"Не удалось открыть папку {path}: {e}")

    def refresh(self):
        """Вызывается при переключении на вкладку. Переопределяется."""
        pass


class PlaceholderFrame(BaseFrame):
    """Заглушка для вкладок, которые ещё не реализованы."""

    def __init__(self, parent, name=None, **kwargs):
        self._name = name
        super().__init__(parent, name, **kwargs)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("🚧", self)
        icon.setStyleSheet("font-size: 48px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        title = QLabel(f"Вкладка «{self._name}»", self)
        title.setFont(self.FONTS['subtitle'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        hint = QLabel("Ещё в разработке. Скоро будет.", self)
        hint.setFont(self.FONTS['label'])
        hint.setStyleSheet("color: #A0A0A0;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)