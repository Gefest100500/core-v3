# ui/frames/archive_frame.py
"""
Архив инвентаризаций.

- Мгновенная загрузка из кэша при открытии
- Асинхронная проверка изменений в фоне
- Удаление записи с подтверждением
- Запись в историю действий

Улучшения по сравнению с CTk-версией:
- Свой диалог заменён на ask_confirm из dialogs.py
- Убраны манипуляции с winfo_x/y
- Убраны root.after
- Хранилище dm = self.app.data_manager через property

Правки стиля:
- Убраны все эмодзи
- Кнопка «Удалить» — с SVG-иконкой
"""
from datetime import datetime

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import create_card, SecondaryButton
from ui.components.dialogs import ask_confirm
from ui.icons import get_icon_simple
from utils.logger import log

from utils.data_manager import INVENTORY_ARCHIVE_PATH


class ArchiveFrame(BaseFrame):

    TITLE = "Архив инвентаризаций"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.inventory_archive = []
        self._last_archive_signature = None
        self._loading = False

        self._load_archive_from_cache()
        self._setup_ui()
        self._refresh_async()

    # =========================================================
    # ПРОПЕРТИ
    # =========================================================
    @property
    def dm(self):
        return self.app.data_manager

    # =========================================================
    # ЗАГРУЗКА — из кэша
    # =========================================================
    def _load_archive_from_cache(self):
        self.inventory_archive = self.dm.get_inventory_archive() or []
        self._last_archive_signature = self.dm.signature(self.inventory_archive)

    # =========================================================
    # ЗАГРУЗКА — async
    # =========================================================
    def _refresh_async(self):
        if self._loading:
            return
        self._loading = True

        def _on_archive_loaded(data):
            self._loading = False
            if data is None:
                data = []

            signature = self.dm.signature(data)
            if signature == self._last_archive_signature:
                return

            self.inventory_archive = data
            self._last_archive_signature = signature
            self._render_archive()

        try:
            if hasattr(self.dm, "read_json_async"):
                self.dm.read_json_async(
                    "inventory_archive",
                    INVENTORY_ARCHIVE_PATH,
                    _on_archive_loaded
                )
            else:
                _on_archive_loaded(self.dm.get_inventory_archive() or [])
        except Exception as e:
            log.debug(f"async archive failed, fallback: {e}")
            self._loading = False
            _on_archive_loaded(self.dm.get_inventory_archive() or [])

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(10)

        # Заголовок (без эмодзи)
        title = QLabel("АРХИВ ИНВЕНТАРИЗАЦИЙ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # Счётчик записей
        self.count_label = QLabel("", self)
        self.count_label.setFont(self.FONTS['small'])
        self.count_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root_layout.addWidget(self.count_label)

        # Скролл
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(8)

        self.scroll.setWidget(self.scroll_content)
        root_layout.addWidget(self.scroll, 1)

        self._render_archive()

    # =========================================================
    # РЕНДЕР
    # =========================================================
    def _render_archive(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        total = len(self.inventory_archive)
        if total:
            self.count_label.setText(f"Всего: {total}")
        else:
            self.count_label.setText("")

        if not self.inventory_archive:
            card = create_card(self.scroll_content)
            card.layout().addWidget(self._make_empty_label("Пока нет завершённых инвентаризаций."))
            self.scroll_layout.addWidget(card)
            self.scroll_layout.addStretch()
            return

        for inv in reversed(self.inventory_archive):
            card = self._create_archive_card(inv)
            self.scroll_layout.addWidget(card)

        self.scroll_layout.addStretch()

    def _make_empty_label(self, text):
        label = QLabel(text, self.scroll_content)
        label.setFont(self.FONTS['label'])
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; padding: 30px;"
        )
        return label

    def _create_archive_card(self, inv):
        """Создаёт карточку одной записи архива (без эмодзи)."""
        card = create_card(self.scroll_content)

        gm_code = inv.get("gm_code", "?")
        gm_name = inv.get("gm_name", "?")
        variant = inv.get("variant", "?")
        address = inv.get("gm_address", "")

        # --- Верхняя строка: ГМ + кнопка Удалить ---
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        gm_label = QLabel(f"ГМ {gm_code} — {gm_name}", card)
        gm_label.setFont(self.FONTS['subtitle'])
        top_row.addWidget(gm_label, 1)

        # 🆕 Кнопка "Удалить" с SVG-иконкой
        btn_delete = QPushButton("Удалить", card)
        btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_delete.setFixedHeight(32)
        btn_delete.setMinimumWidth(120)
        btn_delete.setIcon(get_icon_simple("trash", color=self.COLORS.get('error', '#FF5252'), size=14))
        btn_delete.setIconSize(QSize(14, 14))
        btn_delete.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {self.COLORS.get('error', '#FF5252')};
                border: 1px solid {self.COLORS.get('error', '#FF5252')};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #5A1A1A;
            }}
        """)
        btn_delete.clicked.connect(
            lambda checked=False, i=inv: self._delete_inventory(i)
        )
        top_row.addWidget(btn_delete)

        card.layout().addLayout(top_row)

        # --- Адрес ---
        if address:
            addr_label = QLabel(address, card)
            addr_label.setFont(self.FONTS['small'])
            addr_label.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
            )
            card.layout().addWidget(addr_label)

        # --- Даты и вариант ---
        start_fmt = self._fmt_date(inv.get("start_date", ""))
        end_fmt = self._fmt_date(inv.get("end_date", ""))
        days_passed = inv.get("days_passed", "?")

        info = (
            f"{start_fmt} → {end_fmt}   "
            f"•   {days_passed} дн.   "
            f"•   Вариант {variant}"
        )
        info_label = QLabel(info, card)
        info_label.setFont(self.FONTS['small'])
        info_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        card.layout().addWidget(info_label)

        return card

    # =========================================================
    # УДАЛЕНИЕ
    # =========================================================
    def _delete_inventory(self, inv):
        code = inv.get("gm_code", "?")
        name = inv.get("gm_name", "?")
        start = self._fmt_date(inv.get("start_date", ""))

        ok = ask_confirm(
            self,
            "Удалить инвентаризацию?",
            f"ГМ {code} — {name}\n"
            f"Дата начала: {start}\n\n"
            f"Запись будет удалена из архива. Действие необратимо."
        )
        if not ok:
            return

        self.inventory_archive = [x for x in self.inventory_archive if x is not inv]
        self.dm.set_inventory_archive(self.inventory_archive)
        self._last_archive_signature = self.dm.signature(self.inventory_archive)

        log.info(f"Удалена запись из архива: ГМ {code} — {name}")

        try:
            self.dm.add_action(
                "Удалена инвентаризация",
                f"ГМ {code} — {name}",
                "🗑"
            )
        except Exception:
            pass

        self._render_archive()

    # =========================================================
    # УТИЛИТЫ
    # =========================================================
    @staticmethod
    def _fmt_date(iso_str):
        if not iso_str:
            return "—"
        try:
            return datetime.fromisoformat(iso_str).strftime("%d.%m.%Y")
        except Exception:
            return iso_str

    # =========================================================
    # ОБНОВЛЕНИЕ
    # =========================================================
    def refresh(self):
        self._load_archive_from_cache()
        self._render_archive()
        self._refresh_async()