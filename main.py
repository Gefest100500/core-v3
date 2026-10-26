# main.py
"""
Core V3.0 — Корпоративный аудит.
Точка входа. Запускает QApplication, показывает заставку,
создаёт AuditApp и переключается на него, когда всё готово.

ИЗМЕНЕНИЯ:
- Заставка плавно исчезает (fade-out).
- Главное окно плавно появляется (fade-in).
- Перед созданием AuditApp выполняется одноразовая миграция
  data/ из корня проекта в %LOCALAPPDATA%/Core_V3_0/data.
"""
import sys
import ctypes
import traceback

from PyQt6.QtCore import Qt, QTimer, QEvent, QObject, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QApplication, QGraphicsOpacityEffect

# Устанавливаем флаг ДО создания QApplication
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

# Импортируем QtWebEngineWidgets ДО создания QApplication
try:
    from PyQt6 import QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from config import get_config, get_fonts
from ui.app import AuditApp
from ui.splash import SplashScreen


# =========================================================
# ТЁМНЫЙ TITLE BAR (Windows API)
# =========================================================
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19


def apply_dark_title_bar(widget):
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
    except Exception:
        pass


class DarkTitleBarFilter(QObject):
    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self._widget = widget

    def eventFilter(self, obj, event):
        et = event.type()
        if et in (
            QEvent.Type.Show,
            QEvent.Type.ShowToParent,
            QEvent.Type.WindowStateChange,
            QEvent.Type.WindowActivate,
        ):
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


# =========================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =========================================================
def _show_startup_error(app, title, message, tb_text):
    from utils.logger import log, LOG_FILE

    log.error(f"{title}: {message}\n{tb_text}")

    error_text = (
        f"{message}\n\n"
        f"Подробности записаны в лог:\n{LOG_FILE}\n\n"
        f"Если проблема повторяется — пришлите этот файл разработчику."
    )

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
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {title}", file=sys.stderr)
        print(error_text, file=sys.stderr)
        print(tb_text, file=sys.stderr)


def _run_data_migration():
    """Одноразовая миграция data/ в %LOCALAPPDATA%.

    Не роняет приложение: любые ошибки логируются и игнорируются.
    """
    try:
        from utils.data_migration import migrate_data_if_needed
        from utils.logger import log

        moved = migrate_data_if_needed()
        if moved:
            log.info("main: миграция data/ выполнена")
    except Exception as e:
        try:
            from utils.logger import log
            log.warning(f"main: миграция data/ пропущена из-за ошибки: {e}")
        except Exception:
            pass


def main():
    app = None

    # --- Шаг 1: создаём QApplication ---
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Core V3.0")
        app.setOrganizationName("Silchenko Aleksey")
    except Exception as e:
        tb_text = traceback.format_exc()
        _show_startup_error(
            None,
            "Ошибка запуска",
            f"Не удалось создать QApplication:\n{e}",
            tb_text,
        )
        sys.exit(1)

    # --- Шаг 1.5: миграция data/ (до AuditApp) ---
    _run_data_migration()

    # --- Шаг 2: создаём AuditApp (но не показываем) ---
    window = None
    try:
        cfg = get_config()
        window = AuditApp()
    except Exception as e:
        tb_text = traceback.format_exc()
        _show_startup_error(
            app,
            "Ошибка запуска",
            f"Не удалось создать главное окно:\n{e}",
            tb_text,
        )
        sys.exit(1)

    # --- Шаг 3: создаём и показываем заставку ---
    splash = None
    try:
        cfg = get_config()
        fonts = get_fonts()
        splash = SplashScreen(cfg.COLORS, fonts)
        splash.show()
        app.processEvents()
    except Exception as e:
        from utils.logger import log
        log.warning(f"Не удалось показать заставку: {e}")
        splash = None

    # --- Шаг 4: запускаем фоновую инициализацию ---
    try:
        window.start_background_init(splash)
    except Exception as e:
        from utils.logger import log
        log.warning(f"Ошибка фоновой инициализации: {e}")

    # --- Шаг 5: когда ready — скрываем заставку, показываем окно ---
    def _on_ready():
        try:
            if splash is not None:
                splash.set_progress(100)
                splash.set_status("Готово")
                app.processEvents()

            # Создаём эффект прозрачности для окна
            opacity_effect = QGraphicsOpacityEffect(window)
            window.setGraphicsEffect(opacity_effect)
            opacity_effect.setOpacity(0.0)

            window.show()
            install_dark_title_bar(window)

            # Анимация появления окна
            fade_in = QPropertyAnimation(opacity_effect, b"opacity")
            fade_in.setDuration(400)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
            fade_in.start()

            # Сохраняем ссылку, чтобы анимация не удалилась
            window._fade_in_anim = fade_in

            # Плавно скрываем заставку
            if splash is not None:
                splash.fade_out_and_close()

        except Exception as e:
            from utils.logger import log
            log.warning(f"Ошибка при показе главного окна: {e}")

    window.ready.connect(_on_ready)

    # --- Шаг 6: цикл событий ---
    try:
        sys.exit(app.exec())
    except Exception as e:
        tb_text = traceback.format_exc()
        _show_startup_error(
            app,
            "Ошибка работы",
            f"Приложение завершилось с ошибкой:\n{e}",
            tb_text,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()