# ui/app.py
"""
Главное окно Core V3.0.

Сайдбар + контент. Переключение вкладок по нажатию.
Тёмная тема, единый стиль через QSS (см. ui/styles.py). SVG-иконки.

Анализаторы создаются один раз при старте и передаются в фреймы.

ИЗМЕНЕНИЯ:
- Убрана вкладка «Тандер / Модуль» (RDP не встраивается в Qt)
"""
import os

from PyQt6.QtCore import Qt, QTimer, QSettings, QSize
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QStackedWidget, QFrame, QSizePolicy, QApplication,
    QProgressBar
)

from config import COLORS, get_fonts, init_folders, CONFIG_AUTO_CREATED, FOLDERS
from utils.logger import log
from utils.data_manager import get_data_manager
from ui.icons import get_icon
from ui.styles import build_qss


class AuditApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Core V3.0 - Корпоративный аудит")
        self.resize(1400, 900)
        self.setMinimumSize(1100, 700)

        self.FOLDERS = init_folders()
        self.data_manager = get_data_manager()
        self.data_manager.set_root(self)

        self.FONTS = get_fonts()
        self.COLORS = COLORS

        self._init_analyzers()

        self.rtp_path = ""
        self.kv_path = ""
        self.os_files = []
        self.mbp_files = []
        self.pal_folder = ""
        self.remove_unwanted = True

        self.frames = {}
        self.sidebar_buttons = {}
        self.current_tab_name = None

        self._setup_ui()
        self._apply_style()
        self._restore_geometry()

        log.info("AuditApp инициализирован")

        if CONFIG_AUTO_CREATED:
            QTimer.singleShot(300, self._show_config_notice)

        QTimer.singleShot(1000, self._preload_frames)

    # =========================================================
    # АНАЛИЗАТОРЫ
    # =========================================================
    def _init_analyzers(self):
        self.kv_analyzer = None
        self.pal_analyzer = None
        self.osmbp_analyzer = None

        try:
            from core.kv_analyzer import KvAnalyzer
            self.kv_analyzer = KvAnalyzer()
        except Exception as e:
            log.error(f"Ошибка создания KvAnalyzer: {e}")

        try:
            from core.pal_analyzer import PalAnalyzer
            self.pal_analyzer = PalAnalyzer(self)
        except Exception as e:
            log.error(f"Ошибка создания PalAnalyzer: {e}")

        try:
            from core.os_mbp_analyzer import OsMbpAnalyzer
            self.osmbp_analyzer = OsMbpAnalyzer(self)
        except Exception as e:
            log.error(f"Ошибка создания OsMbpAnalyzer: {e}")

    # =========================================================
    # ДАННЫЕ ДЛЯ ФРЕЙМОВ
    # =========================================================
    def get_gm_data(self):
        try:
            return self.data_manager.get_gm_data()
        except Exception as e:
            log.warning(f"get_gm_data: {e}")
            return []

    def get_active_inventory(self):
        try:
            return self.data_manager.get_active_inventory()
        except Exception as e:
            log.warning(f"get_active_inventory: {e}")
            return None

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Сайдбар ---
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(20, 0, 20, 0)
        sidebar_layout.setSpacing(6)

        logo = QLabel("CORE")
        logo.setObjectName("Logo")
        logo.setFont(self.FONTS['title'])
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo)

        # Кнопки с SVG-иконками
        buttons = [
            ("home", "Главная"),
            ("inventory", "Инвентаризация"),
            ("utils", "Утилиты"),
            ("printers", "Принтеры"),
            ("gm", "Сетевые папки"),
            ("external-link", "АСУС"),
            ("archive", "Архив"),
            ("info", "Информация"),
        ]

        for key, label_text in buttons:
            tab_name = "asus" if key == "external-link" else key

            btn = QPushButton(f"  {label_text}")
            btn.setObjectName("SidebarBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("active", "false")
            btn.setMinimumHeight(42)
            btn.clicked.connect(lambda checked=False, k=tab_name: self.show_tab(k))

            icon = get_icon(key, size=22)
            if not icon.isNull():
                btn.setIcon(icon)
                btn.setIconSize(QSize(22, 22))

            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[tab_name] = btn

        sidebar_layout.addStretch()

        credit = QLabel("by Silchenko Aleksey")
        credit.setObjectName("Credit")
        credit.setFont(self.FONTS['small'])
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(credit)

        main_layout.addWidget(self.sidebar)

        # --- Контент ---
        self.content = QStackedWidget()
        self.content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        main_layout.addWidget(self.content, 1)

        # --- Статус-бар ---
        self.status_bar = QFrame()
        self.status_bar.setObjectName("StatusBar")
        self.status_bar.setFixedHeight(36)

        self.status_label = QLabel("Готов")
        self.status_label.setObjectName("StatusText")
        self.status_label.setFont(self.FONTS['small'])

        self.status_progress = QProgressBar()
        self.status_progress.setRange(0, 1000)
        self.status_progress.setValue(0)
        self.status_progress.setTextVisible(False)
        self.status_progress.setFixedHeight(8)
        self.status_progress.setFixedWidth(200)
        self.status_progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS.get('bg', '#1B1B1B')};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS.get('success', '#4CAF50')};
                border-radius: 4px;
            }}
        """)

        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(12, 0, 12, 0)
        status_layout.setSpacing(12)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.status_progress)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(central, 1)
        container_layout.addWidget(self.status_bar)
        self.setCentralWidget(container)

        self.show_tab("home")

    def _apply_style(self):
        self.setStyleSheet(build_qss())

    # =========================================================
    # ПРЕДЗАГРУЗКА
    # =========================================================
    def _preload_frames(self):
        for name in ("inventory", "archive", "utils"):
            if name in self.frames and self.frames[name] is not None:
                continue
            try:
                frame = self._create_frame(name)
                if frame is not None:
                    self.frames[name] = frame
                    self.content.addWidget(frame)
                    log.debug(f"Preloaded frame: {name}")
            except Exception as e:
                log.debug(f"Preload {name} failed: {e}")

    # =========================================================
    # ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК
    # =========================================================
    def show_tab(self, name):
        if name == self.current_tab_name:
            return

        if name not in self.frames:
            try:
                frame = self._create_frame(name)
                if frame is None:
                    log.warning(f"Вкладка '{name}' пока не реализована")
                    return
                self.frames[name] = frame
                self.content.addWidget(frame)
            except Exception as e:
                log.exception(f"Ошибка создания вкладки {name}: {e}")
                return

        frame = self.frames[name]
        self.content.setCurrentWidget(frame)

        for key, btn in self.sidebar_buttons.items():
            btn.setProperty("active", "true" if key == name else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.current_tab_name = name
        self.set_status("Готов")

        try:
            if hasattr(frame, "refresh"):
                frame.refresh()
        except Exception as e:
            log.warning(f"refresh для {name} упал: {e}")

    # =========================================================
    # СОЗДАНИЕ ФРЕЙМОВ
    # =========================================================
    def _create_frame(self, name):
        if name == "home":
            from ui.frames.home_frame import HomeFrame
            return HomeFrame(self, name)

        if name == "comments":
            from ui.frames.comments_frame import CommentsFrame
            return CommentsFrame(self, name)

        if name == "inventory":
            from ui.frames.inventory_frame import InventoryFrame
            return InventoryFrame(self, name)

        if name == "utils":
            from ui.frames.utils_frame import UtilsFrame
            return UtilsFrame(self, name)

        if name == "printers":
            from ui.frames.printers_frame import PrintersFrame
            return PrintersFrame(self, name)

        if name == "gm":
            from ui.frames.gm_frame import GmFrame
            return GmFrame(self, name)

        if name == "asus":
            from ui.frames.asus_frame import AsusFrame
            return AsusFrame(self, name)

        if name == "archive":
            from ui.frames.archive_frame import ArchiveFrame
            return ArchiveFrame(self, name)

        if name == "info":
            from ui.frames.info_frame import InfoFrame
            return InfoFrame(self, name)

        if name == "kv":
            from ui.frames.kv_frame import KvFrame
            return KvFrame(self, name, self.kv_analyzer)

        if name == "pal":
            from ui.frames.pal_frame import PalFrame
            return PalFrame(self, name, self.pal_analyzer)

        if name == "os_mbp":
            from ui.frames.os_mbp_frame import OsMbpFrame
            return OsMbpFrame(self, name, self.osmbp_analyzer)

        if name == "brak_util":
            from ui.frames.brak_util_frame import BrakUtilFrame
            return BrakUtilFrame(self, name)

        if name == "violations":
            from ui.frames.violations_frame import ViolationsFrame
            return ViolationsFrame(self, name)

        if name == "distance":
            from ui.frames.distance_frame import DistanceFrame
            return DistanceFrame(self, name)

        log.warning(f"Неизвестная вкладка: {name}")
        return None

    # =========================================================
    # ГЕОМЕТРИЯ
    # =========================================================
    def _restore_geometry(self):
        try:
            settings = QSettings("SilchenkoAleksey", "CoreV3")
            geometry = settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except Exception as e:
            log.debug(f"Не удалось восстановить геометрию: {e}")

    def _save_geometry(self):
        try:
            settings = QSettings("SilchenkoAleksey", "CoreV3")
            settings.setValue("geometry", self.saveGeometry())
        except Exception as e:
            log.debug(f"Не удалось сохранить геометрию: {e}")

    # =========================================================
    # СТАТУС И ПРОГРЕСС
    # =========================================================
    def set_status(self, text, color=None):
        self.status_label.setText(text)
        if color:
            self.status_label.setStyleSheet(f"color: {color};")

    def start_progress(self, status_text="Обработка..."):
        self.status_progress.setValue(0)
        self.status_progress.setVisible(True)
        self.set_status(status_text, "#FFD700")

    def update_progress(self, value):
        try:
            self.status_progress.setValue(int(float(value) * 1000))
        except (TypeError, ValueError):
            pass

    def finish_progress(self, success=True, message=None):
        if success:
            self.status_progress.setValue(1000)
            if message:
                self.set_status(message, COLORS.get('success', '#4CAF50'))
        else:
            self.status_progress.setValue(0)
            if message:
                self.set_status(message, COLORS.get('error', '#FF5252'))

    # =========================================================
    # ОТКРЫТИЕ ПАПОК
    # =========================================================
    def open_folder(self, folder_key):
        path = FOLDERS.get(folder_key)
        if not path or not os.path.isdir(path):
            log.warning(f"Папка '{folder_key}' не найдена: {path}")
            return
        try:
            os.startfile(path)
        except Exception as e:
            log.warning(f"Не удалось открыть папку {path}: {e}")

    # =========================================================
    # ПРОЧЕЕ
    # =========================================================
    def _show_config_notice(self):
        log.info("Config был создан автоматически")

    def closeEvent(self, event):
        self._save_geometry()
        try:
            self.data_manager.shutdown()
        except Exception:
            pass
        event.accept()