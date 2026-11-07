# ui/app.py
"""
Главное окно Core V3.0.
"""
import os
import json
from datetime import datetime, timedelta

from PyQt6.QtCore import (
    Qt, QTimer, QSettings, QSize, QPropertyAnimation, QEasingCurve,
    pyqtSignal
)
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QStackedWidget, QFrame, QSizePolicy, QApplication,
    QProgressBar
)

from config import get_config, get_fonts
from utils.logger import log
from utils.data_manager import get_data_manager, EMAILS_PATH
from ui.icons import get_icon, get_icon_simple
from ui.styles import build_qss


SIDEBAR_WIDTH_COLLAPSED = 64
SIDEBAR_WIDTH_EXPANDED = 260
SIDEBAR_ANIM_MS = 280
SIDEBAR_COLLAPSE_DELAY_MS = 100

AUTO_FETCH_DELAY_MS = 5000
SYNC_INTERVAL_HOURS = 24

SETTINGS_ORG = "SilchenkoAleksey"
SETTINGS_APP = "CoreV3"
LAST_SYNC_KEY = "emails_last_sync"

ICON_SIZE = 22
ICON_LEFT_MARGIN = 21
ICON_CENTER_OFFSET = 2


class AuditApp(QMainWindow):

    _status_call = pyqtSignal(str)
    ready = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Core V3.0 - Корпоративный аудит")
        self.resize(1400, 900)
        self.setMinimumSize(1100, 700)

        cfg = get_config()
        self.FOLDERS = cfg.init_folders()
        self.data_manager = get_data_manager()
        self.data_manager.set_root(self)

        self.FONTS = get_fonts()
        self.COLORS = cfg.COLORS

        self._init_analyzers()

        self.rtp_path = ""
        self.kv_path = ""
        self.os_files = []
        self.mbp_files = []
        self.pal_folder = ""
        self.remove_unwanted = True

        self.frames = {}
        self.sidebar_buttons = {}
        self.sidebar_icons = {}
        self.current_tab_name = None

        self._sidebar_collapsed = True
        self._sidebar_anim = None
        self._sidebar_anim_max = None
        self._collapse_timer = None

        self._splash = None
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._splash_watch_timer = None

        self._status_call.connect(self._on_status_from_bg)

        self._setup_ui()
        self._apply_style()
        self._restore_geometry()
        self._setup_sidebar_animation()
        self._install_sidebar_hover()
        self._apply_sidebar_state(collapsed=True)

        log.info("AuditApp инициализирован")

    def _init_analyzers(self):
        self.kv_analyzer = None
        self.pal_analyzer = None
        self.osmbp_analyzer = None
        self.brak_util_analyzer = None

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

        try:
            from core.brak_util_analyzer import BrakUtilAnalyzer
            self.brak_util_analyzer = BrakUtilAnalyzer()
        except Exception as e:
            log.error(f"Ошибка создания BrakUtilAnalyzer: {e}")

    def _needs_sync(self) -> bool:
        try:
            last = self._settings.value(LAST_SYNC_KEY, "")
            if not last:
                return True
            last_dt = datetime.fromisoformat(str(last))
            return datetime.now() - last_dt > timedelta(hours=SYNC_INTERVAL_HOURS)
        except Exception:
            return True

    def _mark_sync_done(self):
        try:
            now = datetime.now().isoformat()
            self._settings.setValue(LAST_SYNC_KEY, now)
            log.info(f"Синхронизация почты: {now}")
        except Exception as e:
            log.warning(f"Не удалось сохранить дату синхронизации: {e}")

    def start_background_init(self, splash=None):
        self._splash = splash

        preload_names = [
            "inventory", "archive", "utils", "ai",
            "timesheet", "terminal", "web",
        ]
        self._init_total = len(preload_names) + 1
        self._init_done = 0

        self._update_splash("Загрузка модулей...", 0)

        self._preload_index = 0
        self._preload_names = preload_names
        QTimer.singleShot(50, self._preload_next)

    def _preload_next(self):
        if self._preload_index >= len(self._preload_names):
            self._start_email_fetch()
            return

        name = self._preload_names[self._preload_index]
        self._preload_index += 1

        pct = int(100 * self._preload_index / max(self._init_total, 1))
        self._update_splash(f"Загрузка: {name}...", pct)

        try:
            if name not in self.frames or self.frames[name] is None:
                frame = self._create_frame(name)
                if frame is not None:
                    self.frames[name] = frame
                    self.content.addWidget(frame)
                    frame.hide()
                    log.debug(f"Preloaded frame: {name}")
        except Exception as e:
            log.debug(f"Preload {name} failed: {e}")

        self._init_done += 1
        QTimer.singleShot(30, self._preload_next)

    def _start_email_fetch(self):
        if not self._needs_sync():
            log.info("auto_fetch: пропуск — синхронизация была меньше 24 часов назад")
            self._update_splash("Готово", 100)
            QTimer.singleShot(0, self._on_init_finished)
            return

        self._update_splash("Загрузка писем из Outlook...", 90)

        # Запускаем таймер на 200 мс (быстрее), чтобы ловить сохранение
        self._last_emails_count = -1
        self._splash_watch_timer = QTimer(self)
        self._splash_watch_timer.timeout.connect(self._check_emails_progress)
        self._splash_watch_timer.start(200)

        import threading

        def _worker():
            try:
                from core.email_service import collect_emails
                result = collect_emails(days_back=None)
                log.info(
                    f"auto_fetch: fetched={result.get('fetched')}, "
                    f"saved={result.get('saved')}, "
                    f"duplicates={result.get('duplicates')}, "
                    f"failed={result.get('failed')}"
                )
                if result.get("success"):
                    self._mark_sync_done()
            except Exception:
                log.exception("auto_fetch: ошибка сбора писем")
            finally:
                # Обязательно ждем завершения, затем проверяем финальный размер
                QTimer.singleShot(0, self._stop_watch_and_finish)

        threading.Thread(target=_worker, daemon=True).start()

    def _check_emails_progress(self):
        """Читает emails.json и обновляет заставку."""
        if not self._splash:
            return
        try:
            if os.path.exists(EMAILS_PATH):
                with open(EMAILS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    count = len(data) if isinstance(data, list) else 0
                    
                    if count != self._last_emails_count:
                        self._last_emails_count = count
                        self._splash.set_counter(count, count)
                        self._splash.set_status(f"Найдено писем в базе: {count}")
        except Exception as e:
            log.debug(f"Ошибка чтения emails.json для заставки: {e}")

    def _stop_watch_and_finish(self):
        if self._splash_watch_timer:
            self._splash_watch_timer.stop()
        
        # Принудительно обновляем счетчик в последний раз перед закрытием
        self._check_emails_progress()
        
        # Ставим полный прогресс и переходим к завершению
        self._update_splash("Готово", 100)
        QTimer.singleShot(100, self._on_init_finished)

    def _on_init_finished(self):
        try:
            self.ready.emit()
        except Exception:
            pass

    def _update_splash(self, text, progress):
        if self._splash is None:
            return
        try:
            self._splash.set_status(text)
            self._splash.set_progress(progress)
            QApplication.processEvents()
        except Exception:
            pass

    def _on_status_from_bg(self, text):
        try:
            self.set_status(text)
        except Exception:
            pass

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

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Сайдбар ---
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(SIDEBAR_WIDTH_COLLAPSED)
        self.sidebar.setMouseTracking(True)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(6, 10, 6, 10)
        sidebar_layout.setSpacing(6)

        buttons = [
            ("home", "Главная"),
            ("inventory", "Инвентаризация"),
            ("utils", "Утилиты"),
            ("terminal", "Терминал"),
            ("globe", "АСУС"),
            ("dashboard", "Дашборд"),
            ("ai", "AI"),
            ("archive", "Архив"),
            ("timesheet", "Табель"),
            ("settings", "Настройки"),
            ("info", "Информация"),
        ]

        for key, label_text in buttons:
            tab_name = "web" if key == "globe" else key
            icon_name = "chart" if key == "dashboard" else key
            if key == "settings":
                icon_name = "settings"

            btn = QPushButton("")
            btn.setObjectName("SidebarBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("active", "false")
            btn.setProperty("collapsed", "true")
            btn.setProperty("full_label", label_text)
            btn.setMinimumHeight(44)
            
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            icon_lbl = QLabel(btn)
            icon_lbl.setFixedSize(ICON_SIZE, ICON_SIZE)
            icon_lbl.move(ICON_LEFT_MARGIN + ICON_CENTER_OFFSET, (44 - ICON_SIZE) // 2)
            icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

            icon = get_icon(icon_name, size=ICON_SIZE)
            if not icon.isNull():
                icon_lbl.setPixmap(icon.pixmap(ICON_SIZE, ICON_SIZE))

            btn.clicked.connect(lambda checked=False, k=tab_name: self.show_tab(k))

            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[tab_name] = btn
            self.sidebar_icons[tab_name] = icon_lbl

        sidebar_layout.addStretch()

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

        self.btn_calc = QPushButton(self.status_bar)
        self.btn_calc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_calc.setFixedSize(24, 24)
        self.btn_calc.setToolTip("Калькулятор")
        icon_calc = get_icon_simple("calculator", color=self.COLORS.get('text_dim', '#A0A0A0'), size=16)
        if not icon_calc.isNull():
            self.btn_calc.setIcon(icon_calc)
            self.btn_calc.setIconSize(QSize(16, 16))
        self.btn_calc.setStyleSheet("""
            QPushButton { background: transparent; border: none; }
            QPushButton:hover { background-color: #333333; border-radius: 4px; }
        """)
        self.btn_calc.clicked.connect(self._open_calculator)

        self.btn_notepad = QPushButton(self.status_bar)
        self.btn_notepad.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_notepad.setFixedSize(24, 24)
        self.btn_notepad.setToolTip("Блокнот")
        icon_notepad = get_icon_simple("notebook", color=self.COLORS.get('text_dim', '#A0A0A0'), size=16)
        if not icon_notepad.isNull():
            self.btn_notepad.setIcon(icon_notepad)
            self.btn_notepad.setIconSize(QSize(16, 16))
        self.btn_notepad.setStyleSheet("""
            QPushButton { background: transparent; border: none; }
            QPushButton:hover { background-color: #333333; border-radius: 4px; }
        """)
        self.btn_notepad.clicked.connect(self._open_notepad)

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
                background-color: {self.COLORS.get('bg', '#1B1B1B')};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {self.COLORS.get('text_dim', '#A0A0A0')};
                border-radius: 4px;
            }}
        """)

        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(12, 0, 12, 0)
        status_layout.setSpacing(12)
        
        status_layout.addWidget(self.btn_calc)
        status_layout.addWidget(self.btn_notepad)
        status_layout.addSpacing(10)
        
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
        QTimer.singleShot(500, self._fix_web_size)

    def _fix_web_size(self):
        web_frame = self.frames.get("web")
        if web_frame and hasattr(web_frame, "refresh_size"):
            web_frame.refresh_size()

    def _open_calculator(self):
        from ui.components.calculator_dialog import CalculatorDialog
        dialog = CalculatorDialog(self, self.COLORS)
        dialog.exec()

    def _open_notepad(self):
        from ui.components.notepad_dialog import NotepadDialog
        dialog = NotepadDialog(self, self.COLORS)
        dialog.exec()

    def _apply_style(self):
        qss = build_qss(self.COLORS)
        self.setStyleSheet(qss)

    def _setup_sidebar_animation(self):
        self._sidebar_anim = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self._sidebar_anim.setDuration(SIDEBAR_ANIM_MS)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.OutQuint)

        self._sidebar_anim_max = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self._sidebar_anim_max.setDuration(SIDEBAR_ANIM_MS)
        self._sidebar_anim_max.setEasingCurve(QEasingCurve.Type.OutQuint)

        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.setInterval(SIDEBAR_COLLAPSE_DELAY_MS)
        self._collapse_timer.timeout.connect(self._collapse_sidebar)

    def _animate_sidebar(self, target_width):
        self._sidebar_anim.stop()
        self._sidebar_anim_max.stop()

        current = self.sidebar.width()

        self._sidebar_anim.setStartValue(current)
        self._sidebar_anim.setEndValue(target_width)

        self._sidebar_anim_max.setStartValue(current)
        self._sidebar_anim_max.setEndValue(target_width)

        self._sidebar_anim.start()
        self._sidebar_anim_max.start()

    def _apply_sidebar_state(self, collapsed):
        self._sidebar_collapsed = collapsed

        for tab_name, btn in self.sidebar_buttons.items():
            btn.setProperty("collapsed", "true" if collapsed else "false")
            if collapsed:
                btn.setText("")
            else:
                full_label = btn.property("full_label") or ""
                btn.setText(full_label)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

            icon_lbl = self.sidebar_icons.get(tab_name)
            if icon_lbl is not None:
                if collapsed:
                    x = (44 - ICON_SIZE) // 2 + ICON_CENTER_OFFSET
                else:
                    x = ICON_LEFT_MARGIN + ICON_CENTER_OFFSET
                icon_lbl.move(x, (44 - ICON_SIZE) // 2)

    def _expand_sidebar(self):
        if self._collapse_timer.isActive():
            self._collapse_timer.stop()

        if not self._sidebar_collapsed and self.sidebar.width() == SIDEBAR_WIDTH_EXPANDED:
            return

        self._apply_sidebar_state(collapsed=False)
        self._animate_sidebar(SIDEBAR_WIDTH_EXPANDED)

    def _collapse_sidebar(self):
        self._apply_sidebar_state(collapsed=True)
        self._animate_sidebar(SIDEBAR_WIDTH_COLLAPSED)

    def _install_sidebar_hover(self):
        self.sidebar.enterEvent = self._on_sidebar_enter
        self.sidebar.leaveEvent = self._on_sidebar_leave

    def _on_sidebar_enter(self, event):
        if self.current_tab_name == "web":
            return
        self._expand_sidebar()

    def _on_sidebar_leave(self, event):
        if self.current_tab_name == "web":
            return
        self._collapse_timer.start()

    def show_tab(self, name):
        if name == self.current_tab_name:
            return

        if self.current_tab_name:
            old = self.frames.get(self.current_tab_name)
            if old is not None:
                try:
                    if hasattr(old, "on_hide"):
                        old.on_hide()
                except Exception as e:
                    log.warning(f"on_hide для {self.current_tab_name} упал: {e}")

        if name not in self.frames:
            try:
                frame = self._create_frame(name)
                if frame is None:
                    log.warning(f"Вкладка '{name}' пока не реализована")
                    return
                self.frames[name] = frame
                self.content.addWidget(frame)
                frame.hide()
            except Exception as e:
                log.exception(f"Ошибка создания вкладки {name}: {e}")
                return

        frame = self.frames[name]
        frame.show()
        self.content.setCurrentWidget(frame)

        for key, btn in self.sidebar_buttons.items():
            btn.setProperty("active", "true" if key == name else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.current_tab_name = name
        self.set_status("Готов")

        if name == "web":
            self._apply_sidebar_state(collapsed=True)
            self._animate_sidebar(SIDEBAR_WIDTH_COLLAPSED)

        try:
            if hasattr(frame, "refresh"):
                frame.refresh()
        except Exception as e:
            log.warning(f"refresh для {name} упал: {e}")

    def _create_frame(self, name):
        if name == "home":
            from ui.frames.home_frame import HomeFrame
            return HomeFrame(self, name)

        if name == "dashboard":
            from ui.frames.dashboard_frame import DashboardFrame
            return DashboardFrame(self, name)

        if name == "ai":
            from ui.frames.ai_frame import AIFrame
            return AIFrame(self, name)

        if name == "comments":
            from ui.frames.comments_frame import CommentsFrame
            return CommentsFrame(self, name)

        if name == "inventory":
            from ui.frames.inventory_frame import InventoryFrame
            return InventoryFrame(self, name)

        if name == "utils":
            from ui.frames.utils_frame import UtilsFrame
            return UtilsFrame(self, name)

        if name == "terminal":
            from ui.frames.terminal_frame import TerminalFrame
            return TerminalFrame(self, name)

        if name == "printers":
            from ui.frames.printers_frame import PrintersFrame
            return PrintersFrame(self, name)

        if name == "gm":
            from ui.frames.gm_frame import GmFrame
            return GmFrame(self, name)

        if name == "web":
            from ui.frames.web_frame import WebFrame
            return WebFrame(self, name)

        if name == "archive":
            from ui.frames.archive_frame import ArchiveFrame
            return ArchiveFrame(self, name)

        if name == "timesheet":
            from ui.frames.timesheet_frame import TimesheetFrame
            return TimesheetFrame(self, name)

        if name == "settings":
            from ui.frames.settings_frame import SettingsFrame
            return SettingsFrame(self, name)

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
            return BrakUtilFrame(self, name, self.brak_util_analyzer)

        if name == "distance":
            from ui.frames.distance_frame import DistanceFrame
            return DistanceFrame(self, name)

        if name == "violations":
            from ui.frames.violations_frame import ViolationsFrame
            return ViolationsFrame(self, name)

        if name == "tsd":
            from ui.frames.tsd_frame import TsdFrame
            return TsdFrame(self, name)

        log.warning(f"Неизвестная вкладка: {name}")
        return None

    def _restore_geometry(self):
        try:
            geometry = self._settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except Exception as e:
            log.debug(f"Не удалось восстановить геометрию: {e}")

    def _save_geometry(self):
        try:
            self._settings.setValue("geometry", self.saveGeometry())
        except Exception as e:
            log.debug(f"Не удалось сохранить геометрию: {e}")

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
                self.set_status(message, self.COLORS.get('success', '#4CAF50'))
        else:
            self.status_progress.setValue(0)
            if message:
                self.set_status(message, self.COLORS.get('error', '#FF5252'))

    def open_folder(self, folder_key):
        path = self.FOLDERS.get(folder_key)
        if not path or not os.path.isdir(path):
            log.warning(f"Папка '{folder_key}' не найдена: {path}")
            return

        try:
            from ui.components.files_dialog import FilesDialog
            dialog = FilesDialog(
                self, folder_key,
                bg=self.COLORS.get("bg", "#1B1B1B"),
                card=self.COLORS.get("card", "#222222"),
                text=self.COLORS.get("text", "#E0E0E0"),
                button=self.COLORS.get("button", "#D42626"),
                hover=self.COLORS.get("hover", "#B71C1C"),
                text_dim=self.COLORS.get("text_dim", "#A0A0A0"),
                border=self.COLORS.get("border", "#333333"),
            )
            dialog.exec()
        except Exception as e:
            log.exception(f"Не удалось открыть FilesDialog: {e}")
            try:
                os.startfile(path)
            except Exception as e2:
                log.warning(f"Не удалось открыть папку {path}: {e2}")

    def closeEvent(self, event):
        for name, frame in self.frames.items():
            if frame is None:
                continue
            try:
                if hasattr(frame, "on_close"):
                    frame.on_close()
            except Exception as e:
                log.warning(f"on_close для {name} упал: {e}")

        self._save_geometry()
        try:
            self.data_manager.shutdown()
        except Exception:
            pass
        event.accept()