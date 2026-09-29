# ui/frames/utils_frame.py
"""
Утилиты — меню всех вспомогательных инструментов.

- Карточки с SVG-иконкой, названием, описанием
- Клик по карточке открывает вкладку
- Подсветка при наведении
- Горячие клавиши Ctrl+1..7

Улучшения по сравнению с CTk-версией:
- Вся карточка кликабельна (не только кнопка «Открыть»)
- Hover-эффект на карточке
- Горячие клавиши Ctrl+1..Ctrl+7

Правки стиля:
- Убраны эмодзи из заголовка
- SVG-иконки вместо эмодзи на карточках
"""
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QKeySequence, QShortcut, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton
)

from ui.frames.base_frame import BaseFrame
from ui.icons import get_icon_simple


class ToolCard(QFrame):
    """Карточка одной утилиты.

    Клик по любому месту — открывает вкладку.
    """

    clicked = pyqtSignal(str)  # tab_name

    def __init__(self, tool, colors, parent=None):
        super().__init__(parent)
        self.tab_name = tool["tab"]
        self.colors = colors

        self.setObjectName("ToolCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(80)

        self.setStyleSheet(f"""
            QFrame#ToolCard {{
                background-color: {colors.get('card', '#222222')};
                border: 2px solid {colors.get('border', '#333333')};
                border-radius: 12px;
            }}
            QFrame#ToolCard:hover {{
                background-color: {colors.get('sidebar', '#2A2A2A')};
                border-color: {colors.get('button', '#D42626')};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(15)

        # 🆕 SVG-иконка
        icon_label = QLabel(self)
        icon_label.setFixedWidth(44)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = get_icon_simple(
            tool["icon_name"],
            color=colors.get('text', '#E0E0E0'),
            size=28
        )
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(28, 28))

        layout.addWidget(icon_label)

        # Текстовая часть
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title = QLabel(tool["title"], self)
        title.setStyleSheet(
            f"font-size: 15px; font-weight: bold; "
            f"color: {colors.get('text', '#E0E0E0')};"
        )
        text_layout.addWidget(title)

        desc = QLabel(tool["desc"], self)
        desc.setStyleSheet(
            f"font-size: 12px; color: {colors.get('text_dim', '#A0A0A0')};"
        )
        text_layout.addWidget(desc)

        layout.addLayout(text_layout, 1)

        # Кнопка «Открыть»
        btn = QPushButton("Открыть →", self)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(140, 40)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors.get('button', '#D42626')};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {colors.get('hover', '#B71C1C')};
            }}
        """)
        btn.clicked.connect(lambda: self.clicked.emit(self.tab_name))
        layout.addWidget(btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.tab_name)
        super().mousePressEvent(event)


class UtilsFrame(BaseFrame):

    TITLE = "Утилиты"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)
        self._setup_ui()
        self._setup_hotkeys()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 10)
        root_layout.setSpacing(10)

        # Заголовок (без эмодзи)
        title = QLabel("УТИЛИТЫ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # Подзаголовок
        info = QLabel(
            "Инструменты для аудита. Кликните по карточке или нажмите Ctrl+1..7.",
            self
        )
        info.setFont(self.FONTS['small'])
        info.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(info)

        # Скролл
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_layout.setSpacing(10)

        self.scroll.setWidget(self.scroll_content)
        root_layout.addWidget(self.scroll, 1)

        # 🆕 Список утилит — icon_name вместо emoji
        self._tools = [
            {
                "icon_name": "kv",
                "title": "Кванты",
                "desc": "Автоматический анализ квантов",
                "tab": "kv",
            },
            {
                "icon_name": "pal",
                "title": "Паллеты",
                "desc": "Анализ и сборка отчёта по паллетам",
                "tab": "pal",
            },
            {
                "icon_name": "os_mbp",
                "title": "ОС и МБП",
                "desc": "Сборка свода ОС и МБП",
                "tab": "os_mbp",
            },
            {
                "icon_name": "brak_util",
                "title": "Брак/утиль",
                "desc": "Проверка актов списания утиля",
                "tab": "brak_util",
            },
            {
                "icon_name": "violations",
                "title": "Анализ Нарушений",
                "desc": "Анализ нарушений БП по РТП",
                "tab": "violations",
            },
            {
                "icon_name": "comments",
                "title": "Стандартные комментарии",
                "desc": "Готовые тексты для отчётов",
                "tab": "comments",
            },
            {
                "icon_name": "distance",
                "title": "Расстояние между ГМ",
                "desc": "Рассчитать расстояние между магазинами",
                "tab": "distance",
            },
        ]

        for tool in self._tools:
            card = ToolCard(tool, self.COLORS, self.scroll_content)
            card.clicked.connect(self._open_tool)
            self.scroll_layout.addWidget(card)

        self.scroll_layout.addStretch()

    # =========================================================
    # ГОРЯЧИЕ КЛАВИШИ
    # =========================================================
    def _setup_hotkeys(self):
        for i, tool in enumerate(self._tools, start=1):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            shortcut.activated.connect(
                lambda t=tool["tab"]: self._open_tool(t)
            )

    # =========================================================
    # ОТКРЫТИЕ УТИЛИТЫ
    # =========================================================
    def _open_tool(self, tab_name):
        if hasattr(self.app, "show_tab"):
            self.app.show_tab(tab_name)