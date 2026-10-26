# ui/frames/utils_frame.py
"""
Утилиты — меню всех вспомогательных инструментов.

- Карточки с SVG-иконкой, названием, описанием
- Клик по карточке открывает вкладку
- Подсветка при наведении
- Горячие клавиши Ctrl+1..N

ИЗМЕНЕНИЯ:
- Карточка «Анализ Нарушений» больше не «в разработке» —
  открывается как обычная вкладка.
- ФИКС QShortcut: ссылки сохраняются в self._shortcuts.
  Раньше QShortcut создавался локально и не сохранялся —
  Python GC мог его собрать, и горячие клавиши переставали
  работать.
- Добавлены карточки «Принтеры» и «Сетевые папки ГМ».
  Они открывают те же фреймы, что раньше были в сайдбаре.
- Добавлена карточка «ТСД (QR-коды)».
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
        self.in_development = tool.get("in_development", False)

        self.setObjectName("ToolCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(80)

        # Для «в разработке» — приглушённые цвета
        if self.in_development:
            bg = colors.get('card', '#222222')
            border = colors.get('border', '#333333')
            hover_bg = colors.get('card', '#222222')
            hover_border = colors.get('text_dim', '#A0A0A0')
        else:
            bg = colors.get('card', '#222222')
            border = colors.get('border', '#333333')
            hover_bg = colors.get('sidebar', '#2A2A2A')
            hover_border = colors.get('button', '#D42626')

        self.setStyleSheet(f"""
            QFrame#ToolCard {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 12px;
            }}
            QFrame#ToolCard:hover {{
                background-color: {hover_bg};
                border-color: {hover_border};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(15)

        # SVG-иконка
        icon_label = QLabel(self)
        icon_label.setFixedWidth(44)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_color = (
            colors.get('text_dim', '#A0A0A0')
            if self.in_development
            else colors.get('text', '#E0E0E0')
        )
        icon = get_icon_simple(
            tool["icon_name"],
            color=icon_color,
            size=28
        )
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(28, 28))

        layout.addWidget(icon_label)

        # Текстовая часть
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title_color = (
            colors.get('text_dim', '#A0A0A0')
            if self.in_development
            else colors.get('text', '#E0E0E0')
        )
        title = QLabel(tool["title"], self)
        title.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {title_color};"
        )
        text_layout.addWidget(title)

        desc = QLabel(tool["desc"], self)
        desc.setStyleSheet(
            f"font-size: 12px; color: {colors.get('text_dim', '#A0A0A0')};"
        )
        text_layout.addWidget(desc)

        layout.addLayout(text_layout, 1)

        # Кнопка — «Открыть» или «В разработке»
        if self.in_development:
            badge = QPushButton("В разработке", self)
            badge.setCursor(Qt.CursorShape.ForbiddenCursor)
            badge.setFixedSize(140, 40)
            badge.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {colors.get('text_dim', '#A0A0A0')};
                    border: 1px solid {colors.get('border', '#333333')};
                    border-radius: 8px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    border-color: {colors.get('text_dim', '#A0A0A0')};
                }}
            """)
            badge.clicked.connect(lambda: self.clicked.emit(self.tab_name))
            layout.addWidget(badge)
        else:
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

        # ФИКС: сохраняем ссылки на QShortcut, чтобы GC не собрал
        self._shortcuts = []

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
            "Инструменты для аудита. Кликните по карточке или нажмите Ctrl+1..N.",
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

        # Список утилит
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
            {
                "icon_name": "printers",
                "title": "Принтеры",
                "desc": "Установка и переименование принтеров",
                "tab": "printers",
            },
            {
                "icon_name": "gm",
                "title": "Сетевые папки ГМ",
                "desc": "Ярлыки на сетевые папки и папки ПИ",
                "tab": "gm",
            },
            {
                "icon_name": "tsd",
                "title": "ТСД (QR-коды)",
                "desc": "Генерация QR-кодов для настройки терминалов",
                "tab": "tsd",
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
        """Ставит Ctrl+1..N на открытие утилит.

        ФИКС: сохраняем QShortcut в self._shortcuts — иначе Python GC
        может собрать объект, и шорткат перестанет работать.
        """
        for i, tool in enumerate(self._tools, start=1):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            # Замыкаем tab_name через дефолтный аргумент,
            # чтобы не поймать последний tool во всех лямбдах.
            shortcut.activated.connect(
                lambda t=tool["tab"]: self._open_tool(t)
            )
            self._shortcuts.append(shortcut)

    # =========================================================
    # ОТКРЫТИЕ УТИЛИТЫ
    # =========================================================
    def _open_tool(self, tab_name):
        if hasattr(self.app, "show_tab"):
            self.app.show_tab(tab_name)