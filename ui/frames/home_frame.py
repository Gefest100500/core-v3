# ui/frames/home_frame.py
"""
Главная вкладка.

- Приветствие по времени суток
- Живые часы (обновляются каждую секунду)
- Активная инвентаризация с прогрессом
- Последние действия (история) — с SVG-иконками

ИЗМЕНЕНИЯ:
- gm_data берётся через self.app.get_gm_data() — без try/except
- активная инвентаризация — через self.app.get_active_inventory()
- при отсутствии данных не падаем, а показываем пусто
"""
import os
from datetime import datetime, date

from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QProgressBar, QListWidget, QListWidgetItem,
    QPushButton
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton
)
from ui.components.dialogs import ask_confirm
from ui.icons import get_icon_simple
from utils.logger import log


# --- Русские дни недели и месяцы ---
WEEKDAYS_RU = {
    0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
    4: "пятница", 5: "суббота", 6: "воскресенье",
}

MONTHS_RU_GENITIVE = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

DEFAULT_INVENTORY_DAYS = 5
HISTORY_PREVIEW_COUNT = 10

# --- Маппинг emoji → имя SVG-иконки ---
EMOJI_TO_ICON = {
    "🏪": "inventory",
    "📏": "distance",
    "📝": "comments",
    "🛢": "brak_util",
    "🧩": "pal",
    "📦": "os_mbp",
    "📊": "kv",
    "⚠️": "violations",
    "✅": "check",
    "🔄": "refresh",
    "🗑": "trash",
    "📁": "gm",
    "🏠": "home",
}


class HomeFrame(BaseFrame):

    TITLE = "Главная"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.gm_data = []
        self.active_inventory = None

        self._last_inventory_signature = None
        self._last_history_signature = None

        self._history_loading = False
        self._inventory_loading = False

        # --- Загрузка начального состояния ---
        self.active_inventory = self.app.get_active_inventory()
        self._last_inventory_signature = self.app.data_manager.signature(
            self.active_inventory
        )

        self.gm_data = self.app.get_gm_data()

        self._setup_ui()
        self._load_history()

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

    # =========================================================
    # ЧАСЫ
    # =========================================================
    def _tick_clock(self):
        try:
            now = datetime.now()

            if hasattr(self, "clock_time_label"):
                self.clock_time_label.setText(now.strftime("%H:%M:%S"))

            if hasattr(self, "clock_date_label"):
                weekday = WEEKDAYS_RU[now.weekday()]
                month = MONTHS_RU_GENITIVE[now.month]
                date_text = f"{weekday}, {now.day} {month} {now.year}"
                self.clock_date_label.setText(date_text)
        except Exception:
            pass

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(15, 15, 15, 10)
        root_layout.setSpacing(10)

        # --- Заголовок ---
        title = QLabel("ГЛАВНАЯ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # --- Скролл ---
        self.main_scroll = QScrollArea(self)
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.main_scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(12)

        self.main_scroll.setWidget(self.scroll_content)
        root_layout.addWidget(self.main_scroll, 1)

        # --- Приветствие + Часы ---
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        # Приветствие
        greeting_card = create_card(self.scroll_content)
        greeting_card.setMinimumHeight(140)
        top_row.addWidget(greeting_card, 1)

        now = datetime.now()
        greeting = self._get_greeting(now.hour)

        greeting_title = QLabel(f"{greeting}!", greeting_card)
        greeting_title.setFont(self.FONTS['title'])
        greeting_card.layout().addWidget(greeting_title)

        greeting_sub = QLabel(
            "Хорошего рабочего дня и точных цифр.",
            greeting_card
        )
        greeting_sub.setFont(self.FONTS['label'])
        greeting_sub.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        greeting_card.layout().addWidget(greeting_sub)

        greeting_card.layout().addStretch()

        # Часы
        clock_card = create_card(self.scroll_content)
        clock_card.setFixedWidth(340)
        clock_card.setMinimumHeight(140)
        top_row.addWidget(clock_card)

        self.clock_time_label = QLabel("00:00:00", clock_card)
        self.clock_time_label.setFont(self._make_clock_font())
        self.clock_time_label.setStyleSheet(
            f"color: {self.COLORS.get('button', '#D42626')};"
        )
        self.clock_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clock_card.layout().addWidget(self.clock_time_label)

        self.clock_date_label = QLabel("", clock_card)
        self.clock_date_label.setFont(self.FONTS['label'])
        self.clock_date_label.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )
        self.clock_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock_date_label.setWordWrap(True)
        clock_card.layout().addWidget(self.clock_date_label)

        self.scroll_layout.addLayout(top_row)

        # --- Карточка инвентаризации ---
        self.inventory_card = create_card(self.scroll_content)
        self.scroll_layout.addWidget(self.inventory_card)

        self.inventory_container = QVBoxLayout()
        self.inventory_container.setSpacing(6)
        self.inventory_card.layout().addLayout(self.inventory_container)

        self._render_inventory()

        # --- Карточка истории ---
        self.history_card = create_card(self.scroll_content)
        self.scroll_layout.addWidget(self.history_card)

        history_header = QHBoxLayout()
        history_header.setSpacing(10)

        history_title = QLabel("ПОСЛЕДНИЕ ДЕЙСТВИЯ", self.history_card)
        history_title.setFont(self.FONTS['subtitle'])
        history_header.addWidget(history_title, 1)

        # Кнопка "Очистить" с SVG-иконкой
        btn_clear = QPushButton("Очистить", self.history_card)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setFixedHeight(30)
        btn_clear.setMinimumWidth(130)
        btn_clear.setIcon(get_icon_simple(
            "trash",
            color=self.COLORS.get('error', '#FF5252'),
            size=16
        ))
        btn_clear.setIconSize(QSize(16, 16))
        btn_clear.setStyleSheet(f"""
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
        btn_clear.clicked.connect(self._clear_history)
        history_header.addWidget(btn_clear)

        self.history_card.layout().addLayout(history_header)

        # Список истории
        self.history_list = QListWidget(self.history_card)
        self.history_list.setFont(self.FONTS['small'])
        self.history_list.setMinimumHeight(240)
        self.history_list.setIconSize(QSize(16, 16))
        self.history_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {self.COLORS.get('bg', '#1B1B1B')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: none;
                border-radius: 6px;
                padding: 6px;
            }}
            QListWidget::item {{
                padding: 8px 6px;
                border-bottom: 1px solid {self.COLORS.get('border', '#333333')};
            }}
            QListWidget::item:hover {{
                background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
            }}
        """)
        self.history_card.layout().addWidget(self.history_list)

        self.scroll_layout.addStretch()

    def _make_clock_font(self):
        font = QFont("Consolas", 36)
        font.setWeight(QFont.Weight.Bold)
        return font

    # =========================================================
    # ИНВЕНТАРИЗАЦИЯ
    # =========================================================
    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            child = item.layout()
            if child is not None:
                self._clear_layout(child)

    def _render_inventory(self):
        self._clear_layout(self.inventory_container)

        if not self.active_inventory:
            self._render_inventory_empty()
        else:
            self._render_inventory_active()

    def _render_inventory_empty(self):
        title = QLabel("ИНВЕНТАРИЗАЦИЯ", self.inventory_card)
        title.setFont(self.FONTS['subtitle'])
        self.inventory_container.addWidget(title)

        hint = QLabel(
            "Инвентаризация не активна.\n"
            "Начать её можно на вкладке «Инвентаризация».",
            self.inventory_card
        )
        hint.setFont(self.FONTS['small'])
        hint.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.inventory_container.addWidget(hint)

    def _render_inventory_active(self):
        inv = self.active_inventory

        title = QLabel("АКТИВНАЯ ИНВЕНТАРИЗАЦИЯ", self.inventory_card)
        title.setFont(self.FONTS['subtitle'])
        title.setStyleSheet(
            f"color: {self.COLORS.get('button', '#D42626')};"
        )
        self.inventory_container.addWidget(title)

        gm_text = f"ГМ {inv.get('gm_code', '?')} — {inv.get('gm_name', '?')}"
        gm_label = QLabel(gm_text, self.inventory_card)
        gm_label.setFont(self.FONTS['label'])
        self.inventory_container.addWidget(gm_label)

        address = inv.get("gm_address", "")
        if address:
            addr_label = QLabel(address, self.inventory_card)
            addr_label.setFont(self.FONTS['small'])
            addr_label.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
            )
            self.inventory_container.addWidget(addr_label)

        start_date_str = inv.get("start_date", "")
        days_total = inv.get("days_total", DEFAULT_INVENTORY_DAYS)

        days_passed = 0
        start_date_formatted = "—"
        if start_date_str:
            try:
                sd = datetime.fromisoformat(start_date_str).date()
                days_passed = (date.today() - sd).days + 1
                start_date_formatted = sd.strftime("%d.%m.%Y")
            except Exception:
                pass

        info_row = QHBoxLayout()

        start_label = QLabel(
            f"Начало: {start_date_formatted}",
            self.inventory_card
        )
        start_label.setFont(self.FONTS['small'])
        start_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        info_row.addWidget(start_label, 1)

        days_label = QLabel(
            f"День: {days_passed} из {days_total}",
            self.inventory_card
        )
        days_label.setFont(self.FONTS['label'])
        info_row.addWidget(days_label)

        self.inventory_container.addLayout(info_row)

        progress_value = (
            min(1.0, days_passed / days_total) if days_total > 0 else 0
        )

        progress_bar = QProgressBar(self.inventory_card)
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setValue(int(progress_value * 100))
        progress_bar.setFixedHeight(12)
        progress_bar.setTextVisible(False)

        progress_color = (
            self.COLORS.get('success', '#4CAF50')
            if progress_value >= 1.0
            else self.COLORS.get('button', '#D42626')
        )
        progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {self.COLORS.get('bg', '#1B1B1B')};
                border-radius: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {progress_color};
                border-radius: 6px;
            }}
        """)
        self.inventory_container.addWidget(progress_bar)

        percent_label = QLabel(
            f"{int(progress_value * 100)}%",
            self.inventory_card
        )
        percent_label.setFont(self.FONTS['small'])
        percent_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        percent_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.inventory_container.addWidget(percent_label)

        hint = QLabel(
            "Все действия — в «Инвентаризация»",
            self.inventory_card
        )
        hint.setFont(self.FONTS['small'])
        hint.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.inventory_container.addWidget(hint)

    # =========================================================
    # ИСТОРИЯ — ASYNC
    # =========================================================
    def _load_history(self):
        if self._history_loading:
            return

        dm = self.app.data_manager

        cached = dm.get_history() if hasattr(dm, "get_history") else []
        if cached:
            self._render_history(cached)

        self._history_loading = True

        def _on_history_loaded(data):
            # ⚠️ Вызывается из ФОНОВОГО потока (read_json_async).
            # Все UI-действия — только через run_on_ui.
            self._history_loading = False
            if not data:
                data = []
            signature = dm.signature(data)
            if signature == self._last_history_signature:
                return
            self._last_history_signature = signature
            self.run_on_ui(self._render_history, data)

        try:
            if hasattr(dm, "read_json_async"):
                from utils.data_manager import HISTORY_PATH
                dm.read_json_async("history", HISTORY_PATH, _on_history_loaded)
            else:
                self._render_history(dm.get_history() or [])
        except Exception as e:
            log.debug(f"async history failed, fallback: {e}")
            self._render_history(dm.get_history() or [])

    def _render_history(self, history):
        """Отображает историю с SVG-иконками."""
        self.history_list.clear()

        if not history:
            item = QListWidgetItem("Пока нет действий.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.history_list.addItem(item)
            return

        for entry in history[-HISTORY_PREVIEW_COUNT:][::-1]:
            ts = entry.get("timestamp", "")
            time_text = "—"
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    time_text = dt.strftime("%H:%M")
                except Exception:
                    pass

            emoji = entry.get("icon", "")
            action = entry.get("action", "Действие")
            details = entry.get("details", "")

            text = f"{time_text}   {action}"
            if details:
                text += f"  —  {details}"

            item = QListWidgetItem(text)
            item.setFlags(Qt.ItemFlag.NoItemFlags)

            icon_name = EMOJI_TO_ICON.get(emoji)
            if icon_name:
                icon = get_icon_simple(
                    icon_name,
                    color=self.COLORS.get('text_dim', '#A0A0A0'),
                    size=16
                )
                if not icon.isNull():
                    item.setIcon(icon)

            self.history_list.addItem(item)

    def _clear_history(self):
        ok = ask_confirm(
            self,
            "Очистить историю?",
            "Очистить всю историю действий?\n\n"
            "Это действие нельзя отменить."
        )
        if not ok:
            return

        self.app.data_manager.set_history([])
        self._last_history_signature = None
        self._load_history()

        log.info("История очищена")

    # =========================================================
    # УТИЛИТЫ
    # =========================================================
    @staticmethod
    def _get_greeting(hour):
        if 5 <= hour < 12:
            return "Доброе утро"
        elif 12 <= hour < 18:
            return "Добрый день"
        elif 18 <= hour < 23:
            return "Добрый вечер"
        else:
            return "Доброй ночи"

    # =========================================================
    # REFRESH
    # =========================================================
    def refresh(self):
        self._load_history()

        new_active = self.app.get_active_inventory()
        new_sig = self.app.data_manager.signature(new_active)

        if new_sig != self._last_inventory_signature:
            self.active_inventory = new_active
            self._last_inventory_signature = new_sig
            self._render_inventory()