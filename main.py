# main.py
"""
Core V3.0 — Корпоративный аудит.
"""
import sys
import ctypes
import traceback

from PyQt6.QtCore import Qt, QTimer, QEvent, QObject, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QApplication, QGraphicsOpacityEffect, QDialog

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

try:
    from PyQt6 import QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from config import get_config, get_fonts
from ui.app import AuditApp
from ui.splash import SplashScreen
from ui.components.wizard_dialog import WizardDialog
from utils.logger import log

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19

def apply_dark_title_bar(widget):
    try:
        hwnd = int(widget.winId())
        value = ctypes.c_int(1)
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
        if result != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass

class DarkTitleBarFilter(QObject):
    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self._widget = widget
    def eventFilter(self, obj, event):
        et = event.type()
        if et in (QEvent.Type.Show, QEvent.Type.ShowToParent, QEvent.Type.WindowStateChange, QEvent.Type.WindowActivate):
            apply_dark_title_bar(self._widget)
        return super().eventFilter(obj, event)

def install_dark_title_bar(widget):
    apply_dark_title_bar(widget)
    flt = DarkTitleBarFilter(widget)
    widget.installEventFilter(flt)
    timer = QTimer(widget)
    timer.timeout.connect(lambda: apply_dark_title_bar(widget))
    timer.start(1000)
    widget._dark_title_filter = flt
    widget._dark_title_timer = timer
    return flt

def _show_startup_error(app, title, message, tb_text):
    from utils.logger import log, LOG_FILE
    log.error(f"{title}: {message}\n{tb_text}")
    error_text = f"{message}\n\nПодробности записаны в лог:\n{LOG_FILE}\n\nЕсли проблема повторяется — пришлите этот файл разработчику."
    if app is None:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {title}", file=sys.stderr)
        print(error_text, file=sys.stderr)
        print(tb_text, file=sys.stderr)
        return
    try:
        from PyQt6.QtWidgets import QMessageBox
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(error_text)
        box.setDetailedText(tb_text)
        box.exec()
    except Exception:
        pass

def main():
    app = None
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Core V3.0")
        app.setOrganizationName("Silchenko Aleksey")
    except Exception as e:
        _show_startup_error(None, "Ошибка запуска", f"Не удалось создать QApplication:\n{e}", traceback.format_exc())
        sys.exit(1)

    window = None
    try:
        cfg = get_config()
        window = AuditApp()
    except Exception as e:
        _show_startup_error(app, "Ошибка запуска", f"Не удалось создать главное окно:\n{e}", traceback.format_exc())
        sys.exit(1)

    completed = window._settings.value("wizard_completed", "false")
    if completed != "true":
        wizard = WizardDialog(window, window.COLORS, window.FONTS)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            window._settings.remove("emails_last_sync")
            log.info("Мастер первого запуска успешно пройден.")
        else:
            sys.exit(0)

    splash = None
    try:
        cfg = get_config()
        fonts = get_fonts()
        splash = SplashScreen(cfg.COLORS, fonts)
        splash.show()
        app.processEvents()
    except Exception as e:
        log.warning(f"Не удалось показать заставку: {e}")
        splash = None

    try:
        window.start_background_init(splash)
    except Exception as e:
        log.warning(f"Ошибка фоновой инициализации: {e}")

    def _on_ready():
        try:
            if splash is not None:
                splash.set_progress(100)
                splash.set_status("Готово")
                app.processEvents()

            opacity_effect = QGraphicsOpacityEffect(window)
            window.setGraphicsEffect(opacity_effect)
            opacity_effect.setOpacity(0.0)

            window.showMaximized()
            install_dark_title_bar(window)

            fade_in = QPropertyAnimation(opacity_effect, b"opacity")
            fade_in.setDuration(400)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
            fade_in.start()

            window._fade_in_anim = fade_in

            if splash is not None:
                splash.fade_out_and_close()
        except Exception as e:
            log.warning(f"Ошибка при показе главного окна: {e}")

    window.ready.connect(_on_ready)

    try:
        sys.exit(app.exec())
    except Exception as e:
        _show_startup_error(app, "Ошибка работы", f"Приложение завершилось с ошибкой:\n{e}", traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()