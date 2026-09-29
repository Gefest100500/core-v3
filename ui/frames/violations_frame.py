# ui/frames/violations_frame.py
"""
Анализ нарушений — заглушка.

Инструмент находится в разработке.
Показывает планы + контакты для обратной связи.

Правки стиля:
- Убраны все эмодзи
- Кнопки — SVG-иконки
"""
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QApplication
)

from config import LOG_DIR
from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton
)
from ui.icons import get_icon_simple


PLANS = [
    "Загрузка РТП и шаблона «Нарушения БП»",
    "Автоматический анализ по правилам",
    "Распределение нарушений между ревизорами",
    "Подсветка найденных расхождений",
    "Формирование итогового отчёта",
]


class ViolationsFrame(BaseFrame):

    TITLE = "Анализ нарушений"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)
        self._setup_ui()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        # --- Верхняя панель: Назад ---
        top = QHBoxLayout()
        btn_back = SecondaryButton(
            "Назад в утилиты",
            on_click=lambda: self.app.show_tab("utils"),
            parent=self
        )
        btn_back.setMinimumWidth(180)
        top.addWidget(btn_back)
        top.addStretch()
        root_layout.addLayout(top)

        # --- Заголовок (без эмодзи) ---
        title = QLabel("АНАЛИЗ НАРУШЕНИЙ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # --- Основная карточка ---
        card = create_card(self)
        card_layout = card.layout()
        card_layout.setSpacing(15)

        # 🆕 SVG-иконка "конус" вместо 🚧
        icon_label = QLabel(card)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        construction_icon = get_icon_simple(
            "construction",
            color=self.COLORS.get('button', '#D42626'),
            size=72
        )
        if not construction_icon.isNull():
            icon_label.setPixmap(construction_icon.pixmap(72, 72))
        card_layout.addWidget(icon_label)

        # Подзаголовок
        subtitle = QLabel("В РАЗРАБОТКЕ", card)
        subtitle.setStyleSheet(
            f"font-size: 24px; font-weight: bold; "
            f"color: {self.COLORS.get('button', '#D42626')};"
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(subtitle)

        # Описание
        desc = QLabel(
            "Инструмент анализа нарушений бизнес-процессов\n"
            "находится в стадии разработки.",
            card
        )
        desc.setFont(self.FONTS['label'])
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(desc)

        # --- Планы ---
        plans_frame = QFrame(card)
        plans_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        plans_layout = QVBoxLayout(plans_frame)
        plans_layout.setContentsMargins(20, 15, 20, 15)
        plans_layout.setSpacing(6)

        plans_title = QLabel("ПЛАНИРУЕТСЯ", plans_frame)
        plans_title.setFont(self.FONTS['subtitle'])
        plans_layout.addWidget(plans_title)

        for plan in PLANS:
            row = QHBoxLayout()
            row.setSpacing(10)

            bullet = QLabel("•", plans_frame)
            bullet.setStyleSheet(
                f"color: {self.COLORS.get('button', '#D42626')}; "
                f"font-size: 16px; font-weight: bold;"
            )
            bullet.setFixedWidth(15)
            row.addWidget(bullet)

            plan_label = QLabel(plan, plans_frame)
            plan_label.setFont(self.FONTS['small'])
            plan_label.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
            )
            row.addWidget(plan_label, 1)

            plans_layout.addLayout(row)

        card_layout.addWidget(plans_frame)

        # Подпись (без ✨)
        footer = QLabel("Следите за обновлениями", card)
        footer.setFont(self.FONTS['small'])
        footer.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(footer)

        root_layout.addWidget(card)
        root_layout.addStretch()

        # --- Кнопки внизу ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_copy = SecondaryButton(
            "Скопировать план",
            on_click=self._copy_plans,
            parent=self
        )
        btn_copy.setMinimumWidth(220)
        btn_copy.setMinimumHeight(40)
        # 🆕 Иконка copy
        copy_icon = get_icon_simple("copy", color=self.COLORS.get('text', '#E0E0E0'), size=16)
        if not copy_icon.isNull():
            btn_copy.setIcon(copy_icon)
            btn_copy.setIconSize(QSize(16, 16))
        btn_row.addWidget(btn_copy)

        btn_logs = SecondaryButton(
            "Открыть логи",
            on_click=lambda: self.open_folder("info"),
            parent=self
        )
        btn_logs.setMinimumWidth(220)
        btn_logs.setMinimumHeight(40)
        # 🆕 Иконка папки (используем gm.svg)
        folder_icon = get_icon_simple("gm", color=self.COLORS.get('text', '#E0E0E0'), size=16)
        if not folder_icon.isNull():
            btn_logs.setIcon(folder_icon)
            btn_logs.setIconSize(QSize(16, 16))
        btn_row.addWidget(btn_logs)

        btn_row.addStretch()
        root_layout.addLayout(btn_row)

    # =========================================================
    # КОПИРОВАНИЕ ПЛАНА
    # =========================================================
    def _copy_plans(self):
        text = "Анализ нарушений — что планируется:\n\n"
        for i, plan in enumerate(PLANS, 1):
            text += f"{i}. {plan}\n"

        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

            if clipboard.text() == text:
                self.show_success(
                    "Скопировано",
                    "Список планов скопирован в буфер обмена."
                )
            else:
                raise RuntimeError("Буфер не принял текст")
        except Exception as e:
            self.show_error("Ошибка", f"Не удалось скопировать:\n{e}")