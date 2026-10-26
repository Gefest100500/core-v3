# ui/frames/web_frame.py
import os
import ctypes

from PyQt6.QtCore import Qt, QUrl, QSize, QSettings, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QStackedWidget, QWidget, QSizePolicy
)

from config import EXTERNAL, FOLDERS
from utils.file_utils import get_base_dir, get_data_dir
from ui.frames.base_frame import BaseFrame
from ui.icons import get_icon_simple
from utils.logger import log

try:
    import pywv2
    WEBVIEW_AVAILABLE = True
except ImportError as e:
    log.warning(f"pywv2 не установлен: {e}")
    WEBVIEW_AVAILABLE = False

BASE_DIR = get_base_dir()
DEFAULT_DOWNLOAD_DIR = os.path.join(FOLDERS.get("info", ""), "Web")
PROFILE_ROOT = os.path.join(get_data_dir(), "webengine")

# Константы WinAPI
SW_HIDE = 0
SW_SHOW = 5


def _get_resources():
    return [
        {"key": "asus", "title": "АСУС", "icon_name": "external-link", "url": EXTERNAL.get("asus_url", "https://rao.corp.tander.ru/")},
    ]


class WebFrame(BaseFrame):
    TITLE = "АСУС"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)
        self.resources = _get_resources()
        self.browsers = {}
        self.containers = {}
        self._settings = QSettings("SilchenkoAleksey", "CoreV3")
        self._setup_ui()
        if WEBVIEW_AVAILABLE:
            self._load_all_browsers()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.stack = QStackedWidget(self)
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.stack.setStyleSheet("QStackedWidget { background-color: #FFFFFF; }")
        root_layout.addWidget(self.stack, 1)

    def _load_all_browsers(self):
        for resource in self.resources:
            key = resource["key"]
            try:
                container = QWidget()
                container.setStyleSheet("background-color: #FFFFFF;")
                container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                self.stack.addWidget(container)
                self.containers[key] = container
                log.info(f"Web[{key}]: контейнер создан")
            except Exception as e:
                log.exception(f"Web[{key}]: ошибка создания контейнера: {e}")

        if self.resources:
            QTimer.singleShot(500, lambda: self._create_webview(self.resources[0]["key"], self.resources[0]["url"]))

    def _create_webview(self, key, url):
        if key in self.browsers:
            return

        container = self.containers.get(key)
        if not container:
            return

        try:
            w = container.width()
            h = container.height()
            if w < 200 or h < 200:
                QTimer.singleShot(200, lambda: self._create_webview(key, url))
                return

            parent_hwnd = int(container.winId())

            view = pywv2.WebView(
                title=f"Web - {key}",
                size=(w, h),
                user_data_dir=os.path.join(PROFILE_ROOT, key),
                parent_hwnd=parent_hwnd,
                auto_pump=True,
                context_menu=False,
            )

            view.start()
            view.navigate(url)
            self.browsers[key] = view
            log.info(f"Web[{key}]: WebView создан с размером {w}x{h}")

        except Exception as e:
            log.exception(f"Web[{key}]: ошибка создания WebView: {e}")

    def showEvent(self, event):
        """При показе вкладки — показываем нативное окно."""
        super().showEvent(event)
        for key, view in self.browsers.items():
            try:
                hwnd = view.hwnd
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW)
                    log.info(f"Web[{key}]: ShowWindow(SW_SHOW)")
            except Exception as e:
                log.warning(f"Web[{key}]: ошибка ShowWindow: {e}")

    def hideEvent(self, event):
        """При скрытии вкладки — прячем нативное окно."""
        super().hideEvent(event)
        for key, view in self.browsers.items():
            try:
                hwnd = view.hwnd
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
                    log.info(f"Web[{key}]: ShowWindow(SW_HIDE)")
            except Exception as e:
                log.warning(f"Web[{key}]: ошибка HideWindow: {e}")

    def on_close(self):
        for key, view in self.browsers.items():
            try:
                view.close()
                log.info(f"Web[{key}]: закрыт")
            except Exception as e:
                log.warning(f"Web[{key}]: ошибка закрытия: {e}")
        self.browsers.clear()