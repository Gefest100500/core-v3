# main.py
"""
Core V3.0 — Корпоративный аудит.
Точка входа. Запускает QApplication и AuditApp.

ВАЖНО:
- QtWebEngineWidgets нужно импортировать ДО создания QApplication.
- Тёмный title bar — через Windows DWM API (DwmSetWindowAttribute).
  Работает на Windows 10 (build 17763+) и Windows 11.
"""
import sys
import ctypes

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

# 🆕 Устанавливаем флаг ДО создания QApplication
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

# 🆕 Импортируем QtWebEngineWidgets ДО создания QApplication
try:
    from PyQt6 import QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass  # Если не установлен — вкладка АСУС покажет ошибку

from ui.app import AuditApp


# =========================================================
# ТЁМНЫЙ TITLE BAR (Windows API)
# =========================================================
def set_dark_title_bar(widget):
    """Красит системный заголовок окна в тёмный цвет.

    Работает через DwmSetWindowAttribute (Windows 10 1809+ / Windows 11).
    На старых ОС — тихо игнорирует.

    Args:
        widget: QWidget (обычно QMainWindow)
    """
    try:
        hwnd = int(widget.winId())

        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 10 build 18985+)
        # На более старых сборках — 19. Пробуем оба.
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)

        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )

        # Если не сработало — пробуем старый ID
        if result != 0:
            DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
    except Exception:
        # На не-Windows или при отсутствии DWM — тихо игнорируем
        pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Core V3.0")
    app.setOrganizationName("Silchenko Aleksey")

    window = AuditApp()
    window.show()

    # 🆕 Красим title bar в тёмный (только Windows)
    set_dark_title_bar(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()