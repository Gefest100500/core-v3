# ui/styles.py
"""
QSS-стили для Core V3.0.

ИЗМЕНЕНИЯ:
- Добавлены глобальные правила для QProgressBar (серый).
- Убраны жёсткие padding у QLabel (чтобы не влиять на статусы).
- Для QLabel#StatusNeutral (серый текст) добавлено отдельное правило.
"""


# =========================================================
# ШАБЛОН QSS
# =========================================================
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

/* =========================================================
   Кнопки сайдбара
   ========================================================= */
QPushButton#SidebarBtn {
    background-color: transparent;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 8px;
    padding: 10px 14px;
    padding-left: 50px;
    text-align: left;
    font-size: 13px;
}

QPushButton#SidebarBtn:hover {
    background-color: %hover%;
    border-color: %hover%;
    color: white;
}

QPushButton#SidebarBtn[active="true"] {
    background-color: %button%;
    border-color: %button%;
    color: white;
}

QPushButton#SidebarBtn[collapsed="true"] {
    text-align: center;
    padding: 0px;
    border: none;
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
   Глобальный QProgressBar — серый, единый стиль
   ========================================================= */
QProgressBar {
    background-color: %sidebar%;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: %text%;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: %text_dim%;
    border-radius: 4px;
}

/* =========================================================
   Статусные метки (если используются)
   ========================================================= */
QLabel#StatusNeutral {
    color: %text_dim%;
    background: transparent;
}

QLabel#StatusSuccess {
    color: %text_dim%; /* серый, а не зелёный */
    background: transparent;
}

QLabel#StatusError {
    color: %error%;
    background: transparent;
}

/* =========================================================
   QComboBox
   ========================================================= */
QComboBox {
    background-color: %sidebar%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 14px;
    min-height: 20px;
}

QComboBox:hover {
    border: 1px solid %text_dim%;
}

QComboBox:focus {
    border: 1px solid %button%;
}

QComboBox:disabled {
    background-color: #2A2A2A;
    color: #666666;
    border: 1px solid #333333;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    background: transparent;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid %text_dim%;
    width: 0;
    height: 0;
    margin-right: 6px;
}

QComboBox::down-arrow:hover {
    border-top: 5px solid %text%;
}

QComboBox QAbstractItemView {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: %button%;
    selection-color: white;
}

QComboBox QAbstractItemView::item {
    background-color: %card%;
    color: %text%;
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 22px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: %hover%;
    color: white;
}

QComboBox QAbstractItemView::item:selected {
    background-color: %button%;
    color: white;
}

/* =========================================================
   QCompleter
   ========================================================= */
QCompleter QAbstractItemView,
QListView {
    background-color: %card%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: %button%;
    selection-color: white;
}

QCompleter QAbstractItemView::item,
QListView::item {
    background-color: %card%;
    color: %text%;
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 22px;
}

QCompleter QAbstractItemView::item:hover,
QListView::item:hover {
    background-color: %hover%;
    color: white;
}

QCompleter QAbstractItemView::item:selected,
QListView::item:selected {
    background-color: %button%;
    color: white;
}

/* =========================================================
   QDateEdit
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
   QCalendarWidget
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
    """Собирает QSS из шаблона, подставляя цвета."""
    if colors is None:
        from config import COLORS as colors

    qss = QSS_TEMPLATE
    for key, value in colors.items():
        qss = qss.replace(f"%{key}%", str(value))
    return qss