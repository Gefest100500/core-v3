# ui/components/widgets.py
"""
Общие виджеты для Core V3.0.

Совместимо с оригинальным API:
- create_card(master, ...) — карточка с рамкой
- create_title(master, text, font, ...) — заголовок
- style_tabview(tabview, ...) — стилизация QTabWidget

Плюс новые удобные функции:
- SectionTitle, InfoLabel
- PrimaryButton, SecondaryButton
- StyledEntry, StyledCombo
- Row, VStack
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTabWidget
)


# =========================================================
# СОВМЕСТИМОСТЬ С ОРИГИНАЛОМ
# =========================================================
def create_card(master, bg="#222222", border="#333333",
                corner_radius=12, border_width=2):
    """Карточка с рамкой.

    Совместимо с CTk-версией: create_card(master, bg, border, ...).

    В PyQt6 используем QSS-класс Card из ui/app.py.
    Если нужны кастомные цвета — они игнорируются (стиль глобальный),
    но функция возвращает QFrame с layout.
    """
    card = QFrame(master)
    card.setObjectName("Card")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(10)

    return card


def create_title(master, text, font, text_color="#E0E0E0", pady=(25, 12)):
    """Заголовок с отступами сверху и снизу.

    Совместимо с CTk-версией.

    Args:
        master: родитель (QWidget)
        text: текст
        font: QFont
        text_color: цвет текста (строка)
        pady: (сверху, снизу) — отступы в пикселях
    """
    # Обёртка с отступами
    wrapper = QFrame(master)
    wrapper.setFrameShape(QFrame.Shape.NoFrame)

    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, pady[0], 0, pady[1])

    label = QLabel(text, wrapper)
    label.setFont(font)
    label.setStyleSheet(f"color: {text_color};")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(label)

    # Возвращаем label, но обёртка вставлена в master через layout родителя
    # Для совместимости — возвращаем wrapper
    return wrapper


def style_tabview(tabview, card="#222222", sidebar="#2A2A2A",
                  button="#D42626", hover="#B71C1C",
                  text="#E0E0E0", text_dim="#A0A0A0"):
    """Стилизует QTabWidget (аналог CTkTabview).

    Args:
        tabview: QTabWidget
        card, sidebar, button, hover, text, text_dim: цвета
    """
    if not isinstance(tabview, QTabWidget):
        return

    tabview.setStyleSheet(f"""
        QTabWidget::pane {{
            background-color: {card};
            border: 1px solid {sidebar};
            border-radius: 8px;
        }}
        QTabBar::tab {{
            background-color: {sidebar};
            color: {text};
            padding: 8px 20px;
            margin-right: 2px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-size: 13px;
        }}
        QTabBar::tab:selected {{
            background-color: {button};
            color: white;
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {hover};
            color: white;
        }}
    """)


# =========================================================
# НОВЫЕ УДОБНЫЕ ФУНКЦИИ
# =========================================================
def SectionTitle(text, parent=None):
    """Заголовок секции (subtitle-шрифт)."""
    label = QLabel(text, parent)
    label.setObjectName("Subtitle")
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return label


def InfoLabel(text, parent=None):
    """Мелкая серая подпись."""
    label = QLabel(text, parent)
    label.setObjectName("InfoLabel")
    label.setStyleSheet("color: #A0A0A0;")
    return label


def PrimaryButton(text, on_click=None, parent=None):
    """Основная кнопка (красная).

    Args:
        text: надпись
        on_click: callback (без аргументов)
        parent: родитель
    """
    btn = QPushButton(text, parent)
    btn.setObjectName("PrimaryBtn")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(40)
    if on_click:
        btn.clicked.connect(lambda: on_click())
    return btn


def SecondaryButton(text, on_click=None, parent=None):
    """Вторичная кнопка (серая)."""
    btn = QPushButton(text, parent)
    btn.setObjectName("SecondaryBtn")
    btn.setStyleSheet("""
        QPushButton#SecondaryBtn {
            background-color: #333333;
            color: #E0E0E0;
            border: 1px solid #444444;
            border-radius: 8px;
            padding: 8px 16px;
        }
        QPushButton#SecondaryBtn:hover {
            background-color: #444444;
        }
    """)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setMinimumHeight(40)
    if on_click:
        btn.clicked.connect(lambda: on_click())
    return btn


def StyledEntry(placeholder="", parent=None):
    """Поле ввода в тёмном стиле.

    В PyQt6 Ctrl+V работает ИЗ КОРОБКИ. Никаких enable_paste не нужно.
    """
    entry = QLineEdit(parent)
    entry.setObjectName("StyledEntry")
    entry.setPlaceholderText(placeholder)
    entry.setMinimumHeight(36)
    entry.setStyleSheet("""
        QLineEdit#StyledEntry {
            background-color: #2A2A2A;
            color: #E0E0E0;
            border: 1px solid #444444;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 14px;
        }
        QLineEdit#StyledEntry:focus {
            border: 1px solid #D42626;
        }
    """)
    return entry


def StyledCombo(items=None, parent=None):
    """Выпадающий список в тёмном стиле."""
    combo = QComboBox(parent)
    combo.setObjectName("StyledCombo")
    combo.setMinimumHeight(36)
    combo.setStyleSheet("""
        QComboBox#StyledCombo {
            background-color: #2A2A2A;
            color: #E0E0E0;
            border: 1px solid #444444;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 14px;
        }
        QComboBox#StyledCombo::drop-down {
            border: none;
            width: 24px;
        }
        QComboBox#StyledCombo QAbstractItemView {
            background-color: #222222;
            color: #E0E0E0;
            selection-background-color: #D42626;
            selection-color: white;
            border: 1px solid #444444;
        }
    """)
    if items:
        combo.addItems(items)
    return combo


def Row(*widgets, spacing=10, parent=None):
    """Горизонтальный ряд виджетов.

    Пример:
        Row(QLabel("Имя:"), StyledEntry())
    """
    row = QFrame(parent)
    row.setFrameShape(QFrame.Shape.NoFrame)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for w in widgets:
        layout.addWidget(w)
    return row


def VStack(*widgets, spacing=10, parent=None):
    """Вертикальный стек виджетов."""
    stack = QFrame(parent)
    stack.setFrameShape(QFrame.Shape.NoFrame)
    layout = QVBoxLayout(stack)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for w in widgets:
        layout.addWidget(w)
    return stack