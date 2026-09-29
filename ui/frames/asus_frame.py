# ui/frames/asus_frame.py
"""
АСУС — встроенный браузер.

- Загружает https://rao.corp.tander.ru/
- Постоянный профиль — cookies, localStorage, IndexedDB сохраняются
- Скачивание файлов — диалог «Сохранить как», запоминает последнюю папку
- Кнопка «Открыть папку загрузок» — открывает последнюю папку скачивания
- F5 — обновить страницу
- Ctrl+H — на главную
- Ctrl+Shift+I — DevTools
- Тонкий статус снизу — «Загрузка...» / «Скачивание: X%» / «Готово»

ИЗМЕНЕНИЯ:
- Убран QWebEngineSettings.WebAttribute.DownloadsEnabled (нет в PyQt6 6.11)
- page привязан к browser (а не к self) — правильный порядок удаления
- Добавлена кнопка «Открыть папку загрузок»
- Счётчик скачанных файлов за сессию
"""
import os
from datetime import datetime

from PyQt6.QtCore import Qt, QUrl, QSize, QSettings
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QFileDialog,
    QPushButton
)

from config import EXTERNAL, FOLDERS
from ui.frames.base_frame import BaseFrame
from ui.icons import get_icon_simple
from utils.logger import log


# Проверка QtWebEngine
WEBENGINE_AVAILABLE = False
QWebEngineView = None
QWebEngineProfile = None
QWebEnginePage = None
QWebEngineSettings = None
QWebEngineDownloadRequest = None

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError as e:
    log.warning(f"QtWebEngineWidgets не установлен: {e}")

if WEBENGINE_AVAILABLE:
    try:
        from PyQt6.QtWebEngineCore import (
            QWebEngineProfile,
            QWebEnginePage,
            QWebEngineSettings,
        )
    except ImportError:
        try:
            from PyQt6.QtWebEngineWidgets import (
                QWebEngineProfile,
                QWebEnginePage,
            )
            QWebEngineSettings = None
        except ImportError as e:
            log.warning(f"QtWebEngineCore не установлен: {e}")
            QWebEngineProfile = None
            QWebEnginePage = None
            QWebEngineSettings = None

    try:
        from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest
    except ImportError:
        QWebEngineDownloadRequest = None


ASUS_URL = EXTERNAL.get("asus_url", "https://rao.corp.tander.ru/")
ASUS_HOME = EXTERNAL.get("asus_home", ASUS_URL)

PROFILE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "webengine"
)

# Дефолтная папка для первого скачивания
DEFAULT_DOWNLOAD_DIR = os.path.join(FOLDERS.get("info", ""), "АСУС")


class AsusFrame(BaseFrame):

    TITLE = "АСУС"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.asus_url = ASUS_URL
        self.asus_home = ASUS_HOME
        self.browser = None
        self.page = None
        self.profile = None

        # Счётчик скачанных файлов за сессию
        self.download_count = 0

        # Настройки для запоминания последней папки
        self._settings = QSettings("SilchenkoAleksey", "CoreV3")

        self._setup_ui()
        self._setup_hotkeys()
        self._load_url()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        if not WEBENGINE_AVAILABLE:
            self._show_webengine_error(root_layout)
            return

        browser_container = QFrame(self)
        browser_container.setStyleSheet("background-color: #FFFFFF;")
        root_layout.addWidget(browser_container, 1)

        browser_layout = QVBoxLayout(browser_container)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)

        try:
            self.browser = self._create_browser()
        except Exception as e:
            log.exception(f"Ошибка создания QWebEngineView: {e}")
            self._show_webengine_error(root_layout)
            return

        if self.browser is None:
            self._show_webengine_error(root_layout)
            return

        self.browser.loadStarted.connect(self._on_load_started)
        self.browser.loadProgress.connect(self._on_load_progress)
        self.browser.loadFinished.connect(self._on_load_finished)
        self.browser.urlChanged.connect(self._on_url_changed)

        browser_layout.addWidget(self.browser, 1)

        # Статус снизу
        self.status_bar = QFrame(self)
        self.status_bar.setFixedHeight(28)
        self.status_bar.setStyleSheet("""
            QFrame {
                background-color: #2A2A2A;
                border-top: 1px solid #333333;
            }
        """)
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(10, 0, 10, 0)
        status_layout.setSpacing(10)

        self.status_label = QLabel("Инициализация...", self.status_bar)
        self.status_label.setStyleSheet(
            "color: #A0A0A0; font-size: 11px; background: transparent;"
        )

        # Кнопка «Открыть папку загрузок»
        self.btn_open_downloads = QPushButton("  Папка загрузок", self.status_bar)
        self.btn_open_downloads.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_downloads.setFixedHeight(22)
        self.btn_open_downloads.setMinimumWidth(160)
        self.btn_open_downloads.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #E0E0E0;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        folder_icon = get_icon_simple(
            "gm", color="#E0E0E0", size=12
        )
        if not folder_icon.isNull():
            self.btn_open_downloads.setIcon(folder_icon)
            self.btn_open_downloads.setIconSize(QSize(12, 12))
        self.btn_open_downloads.clicked.connect(self._open_downloads_folder)

        self.url_label = QLabel("", self.status_bar)
        self.url_label.setStyleSheet(
            "color: #666666; font-size: 11px; background: transparent;"
        )
        self.url_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.btn_open_downloads)
        status_layout.addWidget(self.url_label)

        root_layout.addWidget(self.status_bar)

    def _create_browser(self):
        """Создаёт QWebEngineView с постоянным профилем.

        ВАЖНО: page привязан к browser (а не к self) —
        чтобы при удалении AsusFrame сначала удалился browser
        вместе с page, а потом profile. Иначе QtWebEngine ругается:
        «Release of profile requested but WebEnginePage still not deleted».
        """
        if QWebEngineProfile is None or QWebEnginePage is None:
            log.warning("QWebEngineProfile/QWebEnginePage недоступны")
            return QWebEngineView(self)

        os.makedirs(PROFILE_DIR, exist_ok=True)
        storage_path = os.path.join(PROFILE_DIR, "storage")
        cache_path = os.path.join(PROFILE_DIR, "cache")
        os.makedirs(storage_path, exist_ok=True)
        os.makedirs(cache_path, exist_ok=True)

        log.info(f"АСУС: профиль — {PROFILE_DIR}")

        self.profile = QWebEngineProfile("AsusProfile", self)
        self.profile.setPersistentStoragePath(storage_path)
        self.profile.setCachePath(cache_path)

        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )

        try:
            self.profile.setHttpCacheType(
                QWebEngineProfile.HttpCacheType.DiskHttpCache
            )
        except Exception:
            pass

        try:
            self.profile.setPersistentPermissionsPolicy(
                QWebEngineProfile.PersistentPermissionsPolicy.StoreOnDisk
            )
        except Exception:
            pass

        # Обработка скачивания
        try:
            self.profile.downloadRequested.connect(self._on_download_requested)
            log.info("АСУС: обработчик скачивания подключён")
        except Exception as e:
            log.warning(f"Не удалось подключить downloadRequested: {e}")

        # Настройки профиля (без DownloadsEnabled — его нет в PyQt6 6.11)
        if QWebEngineSettings is not None:
            try:
                profile_settings = self.profile.settings()
                profile_settings.setAttribute(
                    QWebEngineSettings.WebAttribute.LocalStorageEnabled, True
                )
                profile_settings.setAttribute(
                    QWebEngineSettings.WebAttribute.JavascriptEnabled, True
                )
                profile_settings.setAttribute(
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
                )
                profile_settings.setAttribute(
                    QWebEngineSettings.WebAttribute.PluginsEnabled, True
                )
                # ВАЖНО: DownloadsEnabled — НЕ используем, этого атрибута
                # нет в PyQt6 6.11. Скачивание работает через downloadRequested.
            except Exception as e:
                log.warning(f"Настройки профиля: {e}")

        # Создаём browser
        browser = QWebEngineView(self)

        # ВАЖНО: page — ребёнок browser, а не self.
        # Это гарантирует, что при удалении AsusFrame сначала удалится
        # browser (и его page), а потом уже profile.
        self.page = QWebEnginePage(self.profile, browser)
        browser.setPage(self.page)

        return browser

    def _show_webengine_error(self, layout):
        error_frame = QFrame(self)
        error_layout = QVBoxLayout(error_frame)
        error_layout.setContentsMargins(40, 40, 40, 40)
        error_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("QtWebEngine не установлен", error_frame)
        title.setStyleSheet(
            "color: #FF5252; font-size: 20px; font-weight: bold;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_layout.addWidget(title)

        hint = QLabel(
            "Для работы вкладки АСУС установите пакет:\n\n"
            "py -3.13 -m pip install PyQt6-WebEngine PyQt6-WebEngine-Qt6",
            error_frame
        )
        hint.setStyleSheet("color: #A0A0A0; font-size: 13px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        error_layout.addWidget(hint)

        layout.addWidget(error_frame, 1)

    # =========================================================
    # ОТКРЫТИЕ ПАПКИ ЗАГРУЗОК
    # =========================================================
    def _open_downloads_folder(self):
        """Открывает папку последнего скачивания (или дефолтную)."""
        last_dir = self._settings.value("asus_last_download_dir", "")
        if last_dir and os.path.isdir(last_dir):
            path = last_dir
        else:
            path = DEFAULT_DOWNLOAD_DIR
            os.makedirs(path, exist_ok=True)

        try:
            os.startfile(path)
        except Exception as e:
            log.warning(f"Не удалось открыть папку загрузок {path}: {e}")

    # =========================================================
    # СКАЧИВАНИЕ — ДИАЛОГ СОХРАНЕНИЯ
    # =========================================================
    def _on_download_requested(self, download):
        """Обрабатывает запрос на скачивание.

        Показывает диалог «Сохранить как».
        Запоминает последнюю папку через QSettings.
        """
        try:
            suggested_name = download.downloadFileName()
            if not suggested_name:
                url = download.url().toString()
                suggested_name = os.path.basename(url) or "download"

            last_dir = self._settings.value("asus_last_download_dir", "")
            if not last_dir or not os.path.isdir(last_dir):
                last_dir = DEFAULT_DOWNLOAD_DIR
                os.makedirs(last_dir, exist_ok=True)

            default_path = os.path.join(last_dir, suggested_name)

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить файл из АСУС",
                default_path,
                "Все файлы (*.*)"
            )

            if not file_path:
                log.info(f"АСУС: скачивание отменено — {suggested_name}")
                download.cancel()
                self.status_label.setText("Скачивание отменено")
                self.status_label.setStyleSheet(
                    "color: #A0A0A0; font-size: 11px; background: transparent;"
                )
                return

            self._settings.setValue(
                "asus_last_download_dir",
                os.path.dirname(file_path)
            )

            log.info(f"АСУС: скачивание {suggested_name} → {file_path}")

            download.setDownloadDirectory(os.path.dirname(file_path))
            download.setDownloadFileName(os.path.basename(file_path))

            download.receivedBytesChanged.connect(
                lambda d=download: self._on_download_progress(d)
            )
            download.isFinishedChanged.connect(
                lambda d=download: self._on_download_finished(d, file_path)
            )

            download.accept()

            self.status_label.setText(
                f"Скачивание: {os.path.basename(file_path)}"
            )
            self.status_label.setStyleSheet(
                "color: #FFD700; font-size: 11px; background: transparent;"
            )

        except Exception as e:
            log.exception(f"Ошибка обработки скачивания: {e}")
            try:
                download.cancel()
            except Exception:
                pass
            self.status_label.setText("Ошибка скачивания")
            self.status_label.setStyleSheet(
                "color: #FF5252; font-size: 11px; background: transparent;"
            )

    def _on_download_progress(self, download):
        """Обновляет статус во время скачивания."""
        try:
            received = download.receivedBytes()
            total = download.totalBytes()
            if total > 0:
                percent = int(received * 100 / total)
                name = download.downloadFileName()
                self.status_label.setText(
                    f"Скачивание: {name} — {percent}%"
                )
        except Exception:
            pass

    def _on_download_finished(self, download, target_path):
        """Вызывается по завершении скачивания."""
        try:
            state = download.state()
            state_str = str(state).lower()
            success = "completed" in state_str or "finished" in state_str

            if success:
                self.download_count += 1

                self.status_label.setText(
                    f"Скачано: {os.path.basename(target_path)} "
                    f"(за сессию: {self.download_count})"
                )
                self.status_label.setStyleSheet(
                    "color: #4CAF50; font-size: 11px; background: transparent;"
                )

                log.info(f"АСУС: файл сохранён — {target_path}")

                try:
                    self.app.data_manager.add_action(
                        "Скачан файл из АСУС",
                        os.path.basename(target_path),
                        "📥"
                    )
                except Exception:
                    pass
            else:
                self.status_label.setText("Скачивание не удалось")
                self.status_label.setStyleSheet(
                    "color: #FF5252; font-size: 11px; background: transparent;"
                )
                log.warning(
                    f"АСУС: скачивание не удалось, state={state}"
                )

        except Exception as e:
            log.exception(f"Ошибка обработки завершения скачивания: {e}")

    # =========================================================
    # ГОРЯЧИЕ КЛАВИШИ
    # =========================================================
    def _setup_hotkeys(self):
        if not WEBENGINE_AVAILABLE:
            return

        QShortcut(QKeySequence("F5"), self, activated=self._reload)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._reload)
        QShortcut(QKeySequence("Ctrl+H"), self, activated=self._go_home)

        try:
            QShortcut(
                QKeySequence("Ctrl+Shift+I"),
                self,
                activated=self._open_devtools
            )
        except Exception:
            pass

    # =========================================================
    # ЗАГРУЗКА
    # =========================================================
    def _load_url(self):
        if not WEBENGINE_AVAILABLE or self.browser is None:
            return

        log.info(f"АСУС: загрузка {self.asus_url}")
        self.browser.setUrl(QUrl(self.asus_url))
        self.set_status("Загрузка АСУС...")

    def _reload(self):
        if not WEBENGINE_AVAILABLE or self.browser is None:
            return
        self.browser.reload()

    def _go_home(self):
        if not WEBENGINE_AVAILABLE or self.browser is None:
            return
        self.browser.setUrl(QUrl(self.asus_home))

    def _open_devtools(self):
        if not WEBENGINE_AVAILABLE or self.browser is None:
            return
        try:
            dev_view = QWebEngineView()
            dev_view.setWindowTitle("АСУС — DevTools")
            dev_view.resize(1000, 700)
            self.browser.page().setDevToolsPage(dev_view.page())
            dev_view.show()
            self._devtools_view = dev_view
        except Exception as e:
            log.warning(f"Не удалось открыть DevTools: {e}")

    # =========================================================
    # СИГНАЛЫ
    # =========================================================
    def _on_load_started(self):
        self.status_label.setText("Загрузка...")
        self.status_label.setStyleSheet(
            "color: #FFD700; font-size: 11px; background: transparent;"
        )

    def _on_load_progress(self, progress):
        if progress < 100:
            self.status_label.setText(f"Загрузка {progress}%...")

    def _on_load_finished(self, ok):
        if ok:
            self.status_label.setText("Готово")
            self.status_label.setStyleSheet(
                "color: #4CAF50; font-size: 11px; background: transparent;"
            )
            log.info("АСУС: загружено")
        else:
            self.status_label.setText("Ошибка загрузки")
            self.status_label.setStyleSheet(
                "color: #FF5252; font-size: 11px; background: transparent;"
            )
            log.warning("АСУС: ошибка загрузки")

    def _on_url_changed(self, url):
        url_text = url.toString()
        if len(url_text) > 80:
            url_text = url_text[:77] + "..."
        self.url_label.setText(url_text)

    # =========================================================
    # REFRESH
    # =========================================================
    def refresh(self):
        pass