# ui/frames/archive_frame.py
"""
Архив инвентаризаций.

- Мгновенная загрузка из кэша при открытии
- Асинхронная проверка изменений в фоне
- Клик по карточке → встроенный дашборд (страница QStackedWidget)
- Кнопка «← Назад в архив» — возврат к списку
- Записи НЕ удаляются

Правки:
- Шапка уменьшена. Отступы (20, 20, 20, 20) → (20, 8, 20, 8),
  spacing 10 → 4.
- Заголовок «АРХИВ ИНВЕНТАРИЗАЦИЙ» и счётчик «Всего: N» —
  в одной строке, чтобы не плодить вертикальные отступы.
- QStackedWidget: страница 0 — список, страница 1 — дашборд.
- Карточка кликабельна, при наведении — тонкая красная рамка.
- _open_dashboard: parent для DashboardFrame — сам ArchiveFrame
  (чтобы BaseFrame нашёл FONTS/COLORS), а в layout добавляем
  в dash_container.

ИЗМЕНЕНИЯ:
- ФИКС _card_bg: импорт 'ui.theme' не существует в проекте —
  он всегда падал в except и возвращал хардкод #222222.
  Теперь цвета передаются в ClickableCard.__init__ через параметр
  colors (dict из COLORS). Если не переданы — fallback #222222.
"""
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QStackedWidget
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import create_card, SecondaryButton
from utils.logger import log

from utils.data_manager import INVENTORY_ARCHIVE_PATH


# Цвет «горящей» рамки карточки — как в стиле проекта
CARD_HOVER_BORDER = "#D42626"
CARD_NORMAL_BORDER = "#333333"


class ArchiveFrame(BaseFrame):

    TITLE = "Архив инвентаризаций"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.inventory_archive = []
        self._last_archive_signature = None
        self._loading = False

        self._current_dashboard = None

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
        # Отступы уменьшены: было (20, 20, 20, 20), spacing 10.
        # Шапка занимала слишком много места.
        root_layout.setContentsMargins(20, 8, 20, 8)
        root_layout.setSpacing(4)

        # Заголовок + счётчик в одной строке — чтобы не плодить отступы.
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title = QLabel("АРХИВ ИНВЕНТАРИЗАЦИЙ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(title, 1)

        self.count_label = QLabel("", self)
        self.count_label.setFont(self.FONTS['small'])
        self.count_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.count_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header_row.addWidget(self.count_label)

        root_layout.addLayout(header_row)

        # QStackedWidget: 0 — список, 1 — дашборд
        self.stack = QStackedWidget(self)
        root_layout.addWidget(self.stack, 1)

        # ---- Страница 0 — список ----
        page_list = QWidget()
        list_layout = QVBoxLayout(page_list)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)

        self.scroll = QScrollArea(page_list)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(8)

        self.scroll.setWidget(self.scroll_content)
        list_layout.addWidget(self.scroll, 1)

        self.stack.addWidget(page_list)

        # ---- Страница 1 — контейнер для дашборда ----
        page_dash = QWidget()
        dash_layout = QVBoxLayout(page_dash)
        dash_layout.setContentsMargins(0, 0, 0, 0)
        dash_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.btn_back = SecondaryButton(
            "← Назад в архив",
            on_click=self._on_back_click,
            parent=self
        )
        self.btn_back.setMinimumWidth(180)
        self.btn_back.setMinimumHeight(36)
        top_row.addWidget(self.btn_back)
        top_row.addStretch()

        dash_layout.addLayout(top_row)

        self.dash_container = QWidget()
        self.dash_container_layout = QVBoxLayout(self.dash_container)
        self.dash_container_layout.setContentsMargins(0, 0, 0, 0)
        self.dash_container_layout.setSpacing(0)

        dash_layout.addWidget(self.dash_container, 1)

        self.stack.addWidget(page_dash)

        self.stack.setCurrentIndex(0)

        self._render_archive()

    # =========================================================
    # РЕНДЕР СПИСКА
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
            card.layout().addWidget(
                self._make_empty_label("Пока нет завершённых инвентаризаций.")
            )
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

    # =========================================================
    # КАРТОЧКА (кликабельная)
    # =========================================================
    def _create_archive_card(self, inv):
        """Карточка записи архива. Клик → дашборд по этому ГМ."""
        card = ClickableCard(inv, colors=self.COLORS, parent=self.scroll_content)
        card.clicked.connect(self._on_card_clicked)

        gm_code = inv.get("gm_code", "?")
        gm_name = inv.get("gm_name", "?")
        variant = inv.get("variant", "?")
        address = inv.get("gm_address", "")

        # --- Верхняя строка: ГМ ---
        gm_label = QLabel(f"ГМ {gm_code} — {gm_name}", card)
        gm_label.setFont(self.FONTS['subtitle'])
        gm_label.setStyleSheet("background: transparent;")
        card.layout().addWidget(gm_label)

        # --- Адрес ---
        if address:
            addr_label = QLabel(address, card)
            addr_label.setFont(self.FONTS['small'])
            addr_label.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"background: transparent;"
            )
            card.layout().addWidget(addr_label)

        # --- Даты и вариант ---
        start_fmt = self._fmt_date(inv.get("start_date", ""))
        end_fmt = self._fmt_date(inv.get("end_date", ""))

        final_totals = inv.get("final_totals") or {}
        with_rm = final_totals.get("with_rm") or {}
        amount = with_rm.get("amount")
        amount_text = self._fmt_money(amount) if amount is not None else "—"

        info = (
            f"{start_fmt} → {end_fmt}   "
            f"•   Вариант {variant}   "
            f"•   Итог: {amount_text}"
        )
        info_label = QLabel(info, card)
        info_label.setFont(self.FONTS['small'])
        info_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
            f"background: transparent;"
        )
        card.layout().addWidget(info_label)

        # --- Подсказка ---
        hint = QLabel("Нажмите, чтобы открыть дашборд", card)
        hint.setFont(self.FONTS['small'])
        hint.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#666666')}; "
            f"background: transparent; padding-top: 4px;"
        )
        card.layout().addWidget(hint)

        return card

    # =========================================================
    # ПЕРЕХОД НА ДАШБОРД
    # =========================================================
    def _on_card_clicked(self, inv):
        gm_code = inv.get("gm_code", "")
        if not gm_code:
            return

        self._open_dashboard(gm_code)

    def _open_dashboard(self, gm_code):
        # Удаляем предыдущий дашборд, если был
        self._clear_dashboard()

        try:
            from ui.frames.dashboard_frame import DashboardFrame
        except Exception as e:
            log.exception(f"Не удалось импортировать DashboardFrame: {e}")
            return

        # parent — сам ArchiveFrame (BaseFrame), чтобы BaseFrame
        # нашёл FONTS/COLORS. А в layout добавляем в dash_container.
        dashboard = DashboardFrame(
            self,
            initial_gm_code=gm_code,
            is_embedded=True,
        )
        self.dash_container_layout.addWidget(dashboard)
        self._current_dashboard = dashboard

        self.stack.setCurrentIndex(1)

    def _clear_dashboard(self):
        if self._current_dashboard is not None:
            try:
                self._current_dashboard.setParent(None)
                self._current_dashboard.deleteLater()
            except Exception:
                pass
            self._current_dashboard = None

        # На всякий случай вычищаем всё из контейнера
        while self.dash_container_layout.count():
            item = self.dash_container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _on_back_click(self):
        self._clear_dashboard()
        self.stack.setCurrentIndex(0)

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

    @staticmethod
    def _fmt_money(v):
        if v is None:
            return "—"
        try:
            if v < 0:
                return f"-{abs(v):,.0f} ₽".replace(",", " ")
            return f"{v:,.0f} ₽".replace(",", " ")
        except Exception:
            return str(v)

    # =========================================================
    # ОБНОВЛЕНИЕ
    # =========================================================
    def refresh(self):
        self._load_archive_from_cache()
        self._render_archive()
        self._refresh_async()


# =========================================================
# КЛИКАБЕЛЬНАЯ КАРТОЧКА
# =========================================================
class ClickableCard(QFrame):
    """QFrame, по которому можно кликнуть.

    При наведении — тонкая красная рамка.
    Клик — emit сигнала clicked(inv).

    ИЗМЕНЕНИЯ:
    - colors передаётся в __init__ (dict из COLORS).
      Раньше был импорт 'ui.theme', которого не существует —
      всегда падало в except и возвращало хардкод #222222.
    """

    clicked = pyqtSignal(object)

    def __init__(self, inv, colors=None, parent=None):
        super().__init__(parent)
        self._inv = inv
        self._colors = colors or {}

        bg = self._colors.get("card", "#222222")

        self.setObjectName("ClickableCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame#ClickableCard {{
                background-color: {bg};
                border: 1px solid {CARD_NORMAL_BORDER};
                border-radius: 12px;
            }}
            QFrame#ClickableCard:hover {{
                border: 1px solid {CARD_HOVER_BORDER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                self.clicked.emit(self._inv)
            except Exception:
                pass
        super().mousePressEvent(event)