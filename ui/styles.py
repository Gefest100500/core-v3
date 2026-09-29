# ui/styles.py
"""
QSS-стили для Core V3.0.

Единый шаблон тёмной темы. Все цвета подставляются из COLORS
(config.json → colors) через плейсхолдеры вида %bg%, %text% и т.д.

Использование:
    from ui.styles import build_qss
    self.setStyleSheet(build_qss())

Когда будем красить под MAGNIT TECH — правим только этот файл
и/или config.json, а не app.py.
"""


# =========================================================
# ШАБЛОН QSS
# =========================================================
# Плейсхолдеры %name% заменяются значениями из COLORS.
# Список ключей COLORS смотри в config.py → DEFAULT_CONFIG["colors"].
QSS_TEMPLATE = """
QMainWindow, QWidget {
    background-color: %bg%;
    color: %text%;
}

QLabel {
    background-color: transparent;
}

QStackedWidget {
    background-color: %bg%;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QScrollBar:vertical {
    background: %sidebar%;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: %border%;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: %text_dim%;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QFrame#Sidebar {
    background-color: %sidebar%;
    border: none;
}

QLabel#Logo {
    color: %text%;
    padding: 20px 0 24px 0;
    background-color: transparent;
}

QPushButton#SidebarBtn {
    background-color: transparent;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
}

QPushButton#SidebarBtn:hover {
    background-color: %hover%;
    border-color: %hover%;
}

QPushButton#SidebarBtn[active="true"] {
    background-color: %button%;
    border-color: %button%;
    color: white;
}

QFrame#StatusBar {
    background-color: %sidebar%;
    border-top: 1px solid %border%;
}

QLabel#StatusText {
    color: %text_dim%;
    padding: 6px 16px;
    background-color: transparent;
}

QLabel#Credit {
    color: #555555;
    padding: 20px 0;
    background-color: transparent;
}

QFrame#Card {
    background-color: %card%;
    border: 1px solid %border%;
    border-radius: 10px;
}

QLabel#Title {
    color: %text%;
    padding: 8px 0 16px 0;
    background-color: transparent;
}

QLabel#Subtitle {
    color: %text%;
    background-color: transparent;
}

QPushButton {
    background-color: %button%;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
}

QPushButton:hover {
    background-color: %hover%;
}

QPushButton:disabled {
    background-color: #555555;
    color: #999999;
}

/* =========================================================
   QDateEdit — поле даты с выпадающим календарём
   ========================================================= */
QDateEdit {
    background-color: %sidebar%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 14px;
}
QDateEdit:hover {
    border: 1px solid %text_dim%;
}
QDateEdit:focus {
    border: 1px solid %button%;
}
QDateEdit::up-button, QDateEdit::down-button {
    width: 0;
    height: 0;
    border: none;
    background: transparent;
}
QDateEdit::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 100%;
    border: none;
    background: transparent;
}
QDateEdit::down-arrow {
    image: none;
    width: 0;
    height: 0;
}

/* =========================================================
   QCalendarWidget — выпадающий календарь (popup у QDateEdit)
   ========================================================= */
QCalendarWidget QWidget {
    background-color: %card%;
    color: %text%;
}
QCalendarWidget QAbstractItemView:enabled {
    background-color: %card%;
    color: %text%;
    selection-background-color: %button%;
    selection-color: white;
    outline: none;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #555555;
}
QCalendarWidget QToolButton {
    background-color: %sidebar%;
    color: %text%;
    border: none;
    padding: 4px 8px;
    font-size: 13px;
}
QCalendarWidget QToolButton:hover {
    background-color: %hover%;
    color: white;
}
QCalendarWidget QMenu {
    background-color: %sidebar%;
    color: %text%;
    border: 1px solid %border%;
}
QCalendarWidget QMenu::item:selected {
    background-color: %button%;
    color: white;
}
QCalendarWidget QSpinBox {
    background-color: %sidebar%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 4px;
    padding: 2px 6px;
}
QCalendarWidget QSpinBox::up-button,
QCalendarWidget QSpinBox::down-button {
    background-color: %sidebar%;
    border: none;
    width: 14px;
}
QCalendarWidget QSpinBox::up-button:hover,
QCalendarWidget QSpinBox::down-button:hover {
    background-color: %hover%;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: %sidebar%;
}
QCalendarWidget QWidget#qt_calendar_calendarview {
    background-color: %card%;
}
"""


# =========================================================
# СБОРКА QSS С ПОДСТАНОВКОЙ ЦВЕТОВ
# =========================================================
def build_qss(colors=None):
    """Собирает QSS из шаблона, подставляя цвета.

    Args:
        colors: словарь цветов. Если None — берётся из config.COLORS.

    Returns:
        Готовая строка QSS.
    """
    if colors is None:
        from config import COLORS as colors

    qss = QSS_TEMPLATE
    for key, value in colors.items():
        qss = qss.replace(f"%{key}%", str(value))
    return qss