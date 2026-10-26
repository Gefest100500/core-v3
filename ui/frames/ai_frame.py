# ui/frames/ai_frame.py
"""
AI — вкладка «Стажёр» (v0.5.5).

Показывает ОБЪЯСНЕНИЯ решений правил от Shadow Engine и позволяет
ревизору размечать их: «Согласен» / «Не согласен».

ИЗМЕНЕНИЯ (v0.5.5):
- Добавлена попытка скругления выделенных ячеек в таблице (border-radius).
- Добавлены отступы (padding) для ячеек, чтобы выделение выглядело как "плашка".
"""
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QCheckBox, QWidget,
    QDoubleSpinBox, QLineEdit, QSplitter, QScrollArea,
    QFormLayout, QProgressBar, QComboBox
)

from ui.frames.base_frame import BaseFrame
from ui.components.dialogs import ask_confirm
from ui.icons import get_icon_simple
from utils.logger import log


PAGE_SIZE = 100


class AIFrame(BaseFrame):

    TITLE = "AI"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self._all_hypotheses = []
        self._page_hypotheses = []
        self._feedback_map = {}
        self._only_unlabeled = False
        self._max_confidence = None
        self._search_text = ""
        self._selected_group = "Все"
        self._current_page = 0
        self._selected_hid = None

        self._setup_ui()
        self.refresh()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # --- Шапка ---
        header = QFrame(self)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {self.COLORS.get('card', '#222222')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(16)

        self.summary_label = QLabel("Записей: 0   Размечено: 0   Уверенность: —", header)
        self.summary_label.setFont(self.FONTS['label'])
        self.summary_label.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; font-size: 14px;"
        )
        header_layout.addWidget(self.summary_label, 1)

        btn_refresh = QPushButton("  Обновить", header)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setMinimumHeight(36)
        btn_refresh.setStyleSheet(self._btn_style())
        icon_refresh = get_icon_simple(
            "refresh", color=self.COLORS.get('text_dim', '#A0A0A0'), size=16
        )
        if not icon_refresh.isNull():
            btn_refresh.setIcon(icon_refresh)
            btn_refresh.setIconSize(QSize(16, 16))
        btn_refresh.clicked.connect(self.refresh)
        header_layout.addWidget(btn_refresh)

        btn_export = QPushButton("  Экспорт", header)
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setMinimumHeight(36)
        btn_export.setStyleSheet(self._btn_style())
        icon_export = get_icon_simple(
            "archive", color=self.COLORS.get('text_dim', '#A0A0A0'), size=16
        )
        if not icon_export.isNull():
            btn_export.setIcon(icon_export)
            btn_export.setIconSize(QSize(16, 16))
        btn_export.clicked.connect(self._export_feedback)
        header_layout.addWidget(btn_export)

        btn_clear = QPushButton("  Очистить", header)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setMinimumHeight(36)
        btn_clear.setStyleSheet(self._btn_style())
        icon_clear = get_icon_simple(
            "trash", color=self.COLORS.get('error', '#FF5252'), size=16
        )
        if not icon_clear.isNull():
            btn_clear.setIcon(icon_clear)
            btn_clear.setIconSize(QSize(16, 16))
        btn_clear.clicked.connect(self._clear_database)
        header_layout.addWidget(btn_clear)

        root.addWidget(header)

        # --- Прогресс ---
        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)

        self.progress_label = QLabel("Размечено: 0 из 0 (0%)", self)
        self.progress_label.setFont(self.FONTS['small'])
        self.progress_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; font-size: 12px;"
        )
        progress_row.addWidget(self.progress_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {self.COLORS.get('bg', '#1B1B1B')};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {self.COLORS.get('text_dim', '#A0A0A0')};
                border-radius: 4px;
            }}
        """)
        progress_row.addWidget(self.progress_bar, 1)

        root.addLayout(progress_row)

        # --- Фильтры (в карточке) ---
        filters_card = QFrame(self)
        filters_card.setStyleSheet(f"""
            QFrame {{
                background-color: {self.COLORS.get('card', '#222222')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
            }}
        """)
        filters_layout = QHBoxLayout(filters_card)
        filters_layout.setContentsMargins(16, 10, 16, 10)
        filters_layout.setSpacing(16)

        self.chk_only_unlabeled = QCheckBox("Только неразмеченные", filters_card)
        self.chk_only_unlabeled.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; font-size: 13px;"
        )
        self.chk_only_unlabeled.stateChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.chk_only_unlabeled)

        filters_layout.addSpacing(10)

        # Фильтр по Группе
        lbl_group = QLabel("Группа:", filters_card)
        lbl_group.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; font-size: 13px;"
        )
        filters_layout.addWidget(lbl_group)

        self.combo_group = QComboBox(filters_card)
        self.combo_group.setMinimumWidth(150)
        self.combo_group.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; "
            f"background-color: {self.COLORS.get('bg', '#1B1B1B')}; "
            f"border: 1px solid {self.COLORS.get('border', '#333333')}; "
            f"border-radius: 4px; padding: 4px 8px; font-size: 13px;"
        )
        self.combo_group.currentTextChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.combo_group)

        filters_layout.addSpacing(10)

        lbl_conf = QLabel("Уверенность ≤", filters_card)
        lbl_conf.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; font-size: 13px;"
        )
        filters_layout.addWidget(lbl_conf)

        self.spin_confidence = QDoubleSpinBox(filters_card)
        self.spin_confidence.setRange(0.0, 1.0)
        self.spin_confidence.setSingleStep(0.1)
        self.spin_confidence.setValue(1.0)
        self.spin_confidence.setDecimals(2)
        self.spin_confidence.setFixedWidth(90)
        self.spin_confidence.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; "
            f"background-color: {self.COLORS.get('bg', '#1B1B1B')}; "
            f"border: 1px solid {self.COLORS.get('border', '#333333')}; "
            f"border-radius: 4px; padding: 4px 8px; font-size: 13px;"
        )
        self.spin_confidence.valueChanged.connect(self._on_filter_changed)
        filters_layout.addWidget(self.spin_confidence)

        filters_layout.addSpacing(10)

        lbl_search = QLabel("Поиск:", filters_card)
        lbl_search.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; font-size: 13px;"
        )
        filters_layout.addWidget(lbl_search)

        self.search_input = QLineEdit(filters_card)
        self.search_input.setPlaceholderText("Код ТП или причина…")
        self.search_input.setMinimumWidth(260)
        self.search_input.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; "
            f"background-color: {self.COLORS.get('bg', '#1B1B1B')}; "
            f"border: 1px solid {self.COLORS.get('border', '#333333')}; "
            f"border-radius: 4px; padding: 6px 10px; font-size: 13px;"
        )
        self.search_input.textChanged.connect(self._on_search_changed)
        filters_layout.addWidget(self.search_input)

        filters_layout.addStretch()
        root.addWidget(filters_card)

        # --- Splitter: таблица + детали ---
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {self.COLORS.get('border', '#333333')};
                width: 2px;
            }}
        """)

        # --- ТАБЛИЦА ---
        self.table = QTableWidget(splitter)
        self.table.setColumnCount(5) 
        self.table.setHorizontalHeaderLabels([
            "Группа", "Код ТП", "Увер.", "Объяснение", "Разметка"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems # <-- Копирование
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # --- СТИЛИ ТАБЛИЦЫ (С ПОПЫТКОЙ СКРУГЛЕНИЯ) ---
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {self.COLORS.get('card', '#222222')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
                gridline-color: transparent; /* Убираем линии сетки для чистоты */
                font-size: 13px;
                outline: none;
            }}
            QTableWidget::item {{
                outline: none;
                border: none;
                padding: 6px 8px; /* Отступы для эффекта плашки */
            }}
            QTableWidget::item:selected {{
                background-color: {self.COLORS.get('button', '#D42626')};
                color: #FFFFFF;
                border-radius: 6px; /* <-- Попытка скругления ячейки */
            }}
            QHeaderView::section {{
                background-color: {self.COLORS.get('bg', '#1B1B1B')};
                color: {self.COLORS.get('text_dim', '#A0A0A0')};
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid {self.COLORS.get('border', '#333333')};
                outline: none;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
            }}
        """)

        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self.table)

        # --- БОКОВАЯ ПАНЕЛЬ ДЕТАЛЕЙ ---
        details_frame = QFrame(splitter)
        details_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.COLORS.get('card', '#222222')};
                border-radius: 8px;
            }}
        """)
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(16, 16, 16, 16)
        details_layout.setSpacing(12)

        details_title = QLabel("ДЕТАЛИ СТРОКИ", details_frame)
        details_title.setFont(self.FONTS['subtitle'])
        details_title.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; font-size: 16px; font-weight: bold;"
        )
        details_layout.addWidget(details_title)

        details_scroll = QScrollArea(details_frame)
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        details_scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.details_content = QWidget()
        self.details_content.setStyleSheet("background: transparent;")
        self.details_form = QFormLayout(self.details_content)
        self.details_form.setContentsMargins(0, 0, 0, 0)
        self.details_form.setSpacing(10)
        self.details_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        details_scroll.setWidget(self.details_content)
        details_layout.addWidget(details_scroll, 1)

        # --- Контейнер для кнопок разметки ---
        self.details_btns_widget = QWidget(details_frame)
        self.details_btns_widget.setStyleSheet("background: transparent;")
        details_btns = QHBoxLayout(self.details_btns_widget)
        details_btns.setContentsMargins(0, 0, 0, 0)
        details_btns.setSpacing(8)

        self.btn_detail_agree = QPushButton("Согласен", self.details_btns_widget)
        self.btn_detail_agree.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_detail_agree.setMinimumHeight(40)
        self.btn_detail_agree.setIcon(
            get_icon_simple("check", color=self.COLORS.get('success', '#4CAF50'), size=16)
        )
        self.btn_detail_agree.setIconSize(QSize(16, 16))
        self.btn_detail_agree.setStyleSheet(self._verdict_btn_style("agree"))
        self.btn_detail_agree.clicked.connect(
            lambda: self._on_verdict(self._selected_hid, "agree")
        )
        details_btns.addWidget(self.btn_detail_agree)

        self.btn_detail_disagree = QPushButton("Не согласен", self.details_btns_widget)
        self.btn_detail_disagree.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_detail_disagree.setMinimumHeight(40)
        self.btn_detail_disagree.setIcon(
            get_icon_simple("x", color=self.COLORS.get('error', '#FF5252'), size=16)
        )
        self.btn_detail_disagree.setIconSize(QSize(16, 16))
        self.btn_detail_disagree.setStyleSheet(self._verdict_btn_style("disagree"))
        self.btn_detail_disagree.clicked.connect(
            lambda: self._on_verdict(self._selected_hid, "disagree")
        )
        details_btns.addWidget(self.btn_detail_disagree)

        details_layout.addWidget(self.details_btns_widget)

        # --- Текст статуса "Уже размечено" ---
        self.lbl_already_labeled = QLabel("", details_frame)
        self.lbl_already_labeled.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_already_labeled.setMinimumHeight(40)
        self.lbl_already_labeled.setStyleSheet(
            f"font-size: 14px; font-weight: bold;"
        )
        self.lbl_already_labeled.hide()
        details_layout.addWidget(self.lbl_already_labeled)

        splitter.addWidget(details_frame)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 350])

        root.addWidget(splitter, 1)

        # --- ПАГИНАЦИЯ + МАССОВАЯ РАЗМЕТКА ---
        pagination = QHBoxLayout()
        pagination.setSpacing(12)

        self.btn_prev = QPushButton("← Пред", self)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setMinimumHeight(36)
        self.btn_prev.setStyleSheet(self._btn_style())
        self.btn_prev.clicked.connect(self._prev_page)
        pagination.addWidget(self.btn_prev)

        self.page_label = QLabel("Стр. 1 из 1", self)
        self.page_label.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; font-size: 13px;"
        )
        self.page_label.setMinimumWidth(160)
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination.addWidget(self.page_label)

        self.btn_next = QPushButton("След →", self)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setMinimumHeight(36)
        self.btn_next.setStyleSheet(self._btn_style())
        self.btn_next.clicked.connect(self._next_page)
        pagination.addWidget(self.btn_next)

        pagination.addStretch()

        bulk_label = QLabel("Выделено:", self)
        bulk_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; font-size: 13px;"
        )
        pagination.addWidget(bulk_label)

        self.bulk_count_label = QLabel("0", self)
        self.bulk_count_label.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')}; font-size: 13px; "
            f"font-weight: bold;"
        )
        pagination.addWidget(self.bulk_count_label)

        pagination.addSpacing(10)

        self.btn_bulk_agree = QPushButton("Согласен для выбранных", self)
        self.btn_bulk_agree.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bulk_agree.setMinimumHeight(36)
        self.btn_bulk_agree.setIcon(
            get_icon_simple("check", color=self.COLORS.get('success', '#4CAF50'), size=16)
        )
        self.btn_bulk_agree.setIconSize(QSize(16, 16))
        self.btn_bulk_agree.setStyleSheet(self._verdict_btn_style("agree"))
        self.btn_bulk_agree.clicked.connect(
            lambda: self._bulk_verdict("agree")
        )
        self.btn_bulk_agree.setEnabled(False)
        pagination.addWidget(self.btn_bulk_agree)

        self.btn_bulk_disagree = QPushButton("Не согласен", self)
        self.btn_bulk_disagree.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bulk_disagree.setMinimumHeight(36)
        self.btn_bulk_disagree.setIcon(
            get_icon_simple("x", color=self.COLORS.get('error', '#FF5252'), size=16)
        )
        self.btn_bulk_disagree.setIconSize(QSize(16, 16))
        self.btn_bulk_disagree.setStyleSheet(self._verdict_btn_style("disagree"))
        self.btn_bulk_disagree.clicked.connect(
            lambda: self._bulk_verdict("disagree")
        )
        self.btn_bulk_disagree.setEnabled(False)
        pagination.addWidget(self.btn_bulk_disagree)

        root.addLayout(pagination)

        self.table.itemSelectionChanged.connect(self._update_bulk_buttons)

    def _btn_style(self):
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {self.COLORS.get('text_dim', '#A0A0A0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
                color: {self.COLORS.get('text', '#E0E0E0')};
            }}
            QPushButton:disabled {{
                color: {self.COLORS.get('text_dim', '#A0A0A0')};
                background-color: transparent;
                border-color: {self.COLORS.get('border', '#333333')};
            }}
        """

    def _verdict_btn_style(self, kind):
        if kind == "agree":
            color = self.COLORS.get('success', '#4CAF50')
        else:
            color = self.COLORS.get('error', '#FF5252')
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: 1px solid {color};
                border-radius: 6px;
                font-size: 13px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: #FFFFFF;
            }}
            QPushButton:disabled {{
                color: {self.COLORS.get('text_dim', '#A0A0A0')};
                border-color: {self.COLORS.get('border', '#333333')};
                background-color: transparent;
            }}
        """

    def _confidence_color(self, confidence):
        if confidence is None:
            return self.COLORS.get('text_dim', '#A0A0A0')
        if confidence < 0.4:
            return self.COLORS.get('error', '#FF5252')
        if confidence < 0.7:
            return "#FFD700"
        return self.COLORS.get('success', '#4CAF50')

    # =========================================================
    # ФИЛЬТРЫ
    # =========================================================
    def _on_filter_changed(self):
        self._only_unlabeled = self.chk_only_unlabeled.isChecked()
        self._selected_group = self.combo_group.currentText()
        val = self.spin_confidence.value()
        self._max_confidence = val if val < 1.0 else None
        self._current_page = 0
        self._load_hypotheses()

    def _on_search_changed(self, text):
        self._search_text = text.strip().lower()
        self._current_page = 0
        self._apply_filters_and_render()

    # =========================================================
    # ЗАГРУЗКА
    # =========================================================
    def _load_hypotheses(self):
        try:
            from ml.shadow import get_hypotheses, get_confidence_stats
            from ml.feedback import get_feedback_stats
            from ml.storage import get_connection

            self._all_hypotheses = get_hypotheses(
                only_unlabeled=self._only_unlabeled,
                max_confidence=self._max_confidence,
            )

            self._feedback_map = {}
            conn = get_connection()
            if conn is not None:
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT hypothesis_id, verdict FROM feedback")
                    for hid, verdict in cur.fetchall():
                        self._feedback_map[hid] = verdict
                except Exception as e:
                    log.warning(f"AI: не удалось прочитать feedback — {e}")
                finally:
                    conn.close()

            stats = get_feedback_stats()
            conf_stats = get_confidence_stats()

            self.summary_label.setText(
                f"Записей: {len(self._all_hypotheses)}   "
                f"Размечено: {stats['total']}   "
                f"Средняя уверенность: {conf_stats['avg']}"
            )

            total = len(self._all_hypotheses)
            labeled = stats['total']
            percent = int(labeled * 100 / total) if total > 0 else 0
            self.progress_label.setText(
                f"Размечено: {labeled} из {total} ({percent}%)"
            )

            self.progress_bar.setValue(percent)

            # Заполняем выпадающий список Группами
            current_group = self.combo_group.currentText() or "Все"
            self.combo_group.blockSignals(True)
            self.combo_group.clear()
            self.combo_group.addItem("Все")
            
            unique_groups = set()
            for h in self._all_hypotheses:
                gr = h.get("features", {}).get("gr20")
                if gr:
                    unique_groups.add(gr)
            
            for gr in sorted(unique_groups):
                self.combo_group.addItem(gr)
            
            # Восстанавливаем выбор, если он был
            idx = self.combo_group.findText(current_group)
            if idx >= 0:
                self.combo_group.setCurrentIndex(idx)
            self.combo_group.blockSignals(False)

            self._apply_filters_and_render()
        except Exception as e:
            log.exception(f"AI: ошибка загрузки — {e}")

    def _apply_filters_and_render(self):
        # 1. Сначала фильтруем по поиску
        if self._search_text:
            filtered = [
                h for h in self._all_hypotheses
                if self._search_text in str(h.get("row_key", "")).lower()
                or self._search_text in str(h.get("ai_hypothesis", "")).lower()
                or self._search_text in str(h.get("rule_fired", "")).lower()
                or self._search_text in str(h.get("features", {}).get("tp_code", "")).lower()
            ]
        else:
            filtered = self._all_hypotheses

        # 2. Фильтруем по Группе (ГР 20)
        if self._selected_group and self._selected_group != "Все":
            filtered = [
                h for h in filtered
                if str(h.get("features", {}).get("gr20", "")) == self._selected_group
            ]

        total_pages = max(1, (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE)
        if self._current_page >= total_pages:
            self._current_page = total_pages - 1
        if self._current_page < 0:
            self._current_page = 0

        start = self._current_page * PAGE_SIZE
        end = start + PAGE_SIZE
        self._page_hypotheses = filtered[start:end]

        self.page_label.setText(
            f"Стр. {self._current_page + 1} из {total_pages} "
            f"(всего: {len(filtered)})"
        )
        self.btn_prev.setEnabled(self._current_page > 0)
        self.btn_next.setEnabled(self._current_page < total_pages - 1)

        self._render_table()

    def _render_table(self):
        self.table.setRowCount(0)

        if not self._page_hypotheses:
            return

        self.table.setRowCount(len(self._page_hypotheses))

        for row_idx, hyp in enumerate(self._page_hypotheses):
            hid = hyp.get("id")
            confidence = hyp.get("confidence")
            features = hyp.get("features", {}) or {}

            # Колонка 0: Группа (ГР 20)
            gr20_val = features.get("gr20", "—")
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(gr20_val)))

            # Колонка 1: Код ТП
            tp_code = features.get("tp_code", "—")
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(tp_code)))

            # Колонка 2: Уверенность
            conf_item = QTableWidgetItem(
                f"{confidence:.2f}" if confidence is not None else "—"
            )
            conf_item.setForeground(QColor(self._confidence_color(confidence)))
            self.table.setItem(row_idx, 2, conf_item)

            # Колонка 3: Объяснение
            self.table.setItem(
                row_idx, 3, QTableWidgetItem(hyp.get("ai_hypothesis", ""))
            )

            # Колонка 4: Разметка
            verdict = self._feedback_map.get(hid)
            if verdict == "agree":
                item_verdict = QTableWidgetItem("Согласен")
                item_verdict.setForeground(QColor(self.COLORS.get('success', '#4CAF50')))
            elif verdict == "disagree":
                item_verdict = QTableWidgetItem("Не согласен")
                item_verdict.setForeground(QColor(self.COLORS.get('error', '#FF5252')))
            else:
                item_verdict = QTableWidgetItem("—")
            self.table.setItem(row_idx, 4, item_verdict)

    # =========================================================
    # ПАГИНАЦИЯ
    # =========================================================
    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._apply_filters_and_render()

    def _next_page(self):
        total = len(self._all_hypotheses)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._apply_filters_and_render()

    # =========================================================
    # ВЫДЕЛЕНИЕ → ДЕТАЛИ
    # =========================================================
    def _on_row_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            # При выделении отдельных ячеек (для копирования) selectedRows() может быть пустым
            # Берем текущую ячейку
            current_idx = self.table.currentIndex()
            if not current_idx.isValid():
                return
            row_idx = current_idx.row()
        else:
            row_idx = rows[0].row()

        if row_idx >= len(self._page_hypotheses):
            return

        hyp = self._page_hypotheses[row_idx]
        hid = hyp.get("id")
        self._selected_hid = hid

        # Очищаем форму
        while self.details_form.count():
            item = self.details_form.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        features = hyp.get("features", {}) or {}

        try:
            from ml.shadow import RULE_LABELS
            rule_code = features.get("rule") or hyp.get("rule_fired") or ""
            rule_label = RULE_LABELS.get(rule_code, rule_code or "—")
        except Exception:
            rule_label = features.get("rule", "—")

        # --- Заголовки и строки ---
        def add_section(title):
            lbl = QLabel(title)
            lbl.setStyleSheet(
                f"color: {self.COLORS.get('button', '#D42626')}; "
                f"font-size: 11px; font-weight: bold; "
                f"text-transform: uppercase; letter-spacing: 0.5px; "
                f"margin-top: 12px;"
            )
            self.details_form.addRow(lbl)

        def add_row(label, value, value_color=None):
            lbl = QLabel(str(label))
            lbl.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; "
                f"font-size: 12px;"
            )
            val = QLabel(str(value) if value not in (None, "") else "—")
            color = value_color or self.COLORS.get('text', '#E0E0E0')
            val.setStyleSheet(
                f"color: {color}; font-size: 13px;"
            )
            val.setWordWrap(True)
            self.details_form.addRow(lbl, val)

        add_section("ОБЩЕЕ")
        add_row("ID:", hid)
        add_row("Правило:", rule_label)
        add_row("Уверенность:",
                f"{hyp.get('confidence', 0):.2f}",
                self._confidence_color(hyp.get("confidence")))

        add_section("ТОВАР")
        tp_code = features.get("tp_code", "")
        add_row("Код ТП:", tp_code)

        operation = features.get("operation", "")
        add_row("Операция из РТП:", operation or "(не найдена)")

        name = features.get("name", "")
        add_row("Наименование ТП:", name)

        gr20 = features.get("gr20", "")
        add_row("Группа:", gr20)

        sign = features.get("sign", "")
        sign_color = None
        if sign == "Излишек":
            sign_color = self.COLORS.get('success', '#4CAF50')
        elif sign == "Недостача":
            sign_color = self.COLORS.get('error', '#FF5252')
        add_row("Излишек/Недостача:", sign, sign_color)

        loss = features.get("loss_amount", 0.0)
        try:
            loss_text = f"{float(loss):,.2f} руб".replace(",", " ")
        except (ValueError, TypeError):
            loss_text = str(loss)
        add_row("Сумма потерь:", loss_text)

        doc = features.get("doc", "")
        add_row("Номер документа:", doc)

        add_section("ОБЪЯСНЕНИЕ")
        reason = features.get("reason", "")
        add_row("Типовая причина:", reason)

        explanation = hyp.get("ai_hypothesis", "")
        add_row("Объяснение ИИ:", explanation)

        # --- ЛОГИКА ОТОБРАЖЕНИЯ КНОПОК / СТАТУСА ---
        verdict = self._feedback_map.get(hid)
        if verdict:
            self.details_btns_widget.hide()
            
            self.lbl_already_labeled.show()
            if verdict == "agree":
                self.lbl_already_labeled.setText("✓ Строка уже размечена: Согласен")
                self.lbl_already_labeled.setStyleSheet(
                    f"font-size: 14px; font-weight: bold; color: {self.COLORS.get('success', '#4CAF50')};"
                )
            else:
                self.lbl_already_labeled.setText("✕ Строка уже размечена: Не согласен")
                self.lbl_already_labeled.setStyleSheet(
                    f"font-size: 14px; font-weight: bold; color: {self.COLORS.get('error', '#FF5252')};"
                )
        else:
            self.details_btns_widget.show()
            self.lbl_already_labeled.hide()
            self.btn_detail_agree.setEnabled(True)
            self.btn_detail_disagree.setEnabled(True)

    # =========================================================
    # МАССОВАЯ РАЗМЕТКА
    # =========================================================
    def _update_bulk_buttons(self):
        rows = self.table.selectionModel().selectedRows()
        count = len(rows)
        self.bulk_count_label.setText(str(count))
        self.btn_bulk_agree.setEnabled(count > 0)
        self.btn_bulk_disagree.setEnabled(count > 0)

    def _bulk_verdict(self, verdict):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return

        hids = []
        for index in rows:
            row_idx = index.row()
            if row_idx < len(self._page_hypotheses):
                hid = self._page_hypotheses[row_idx].get("id")
                if hid is not None:
                    hids.append(hid)

        if not hids:
            return

        label = "Согласен" if verdict == "agree" else "Не согласен"
        ok = ask_confirm(
            self,
            "Массовая разметка",
            f"Разметить {len(hids)} строк как «{label}»?"
        )
        if not ok:
            return

        try:
            from ml.feedback import add_feedback
            success = 0
            for hid in hids:
                if add_feedback(hid, verdict):
                    self._feedback_map[hid] = verdict
                    success += 1

            self._load_hypotheses()
        except Exception as e:
            log.exception(f"AI: ошибка массовой разметки — {e}")

    # =========================================================
    # РАЗМЕТКА
    # =========================================================
    def _on_verdict(self, hypothesis_id, verdict):
        if hypothesis_id is None:
            return

        try:
            from ml.feedback import add_feedback

            ok = add_feedback(hypothesis_id, verdict)
            if not ok:
                return

            self._feedback_map[hypothesis_id] = verdict
            self._load_hypotheses()
        except Exception as e:
            log.exception(f"AI: ошибка сохранения разметки — {e}")

    # =========================================================
    # ЭКСПОРТ
    # =========================================================
    def _export_feedback(self):
        try:
            from ml.feedback import export_feedback
            path = export_feedback()
            if path:
                self.summary_label.setText(f"Экспортировано в: {path}")
            else:
                self.summary_label.setText("Нечего экспортировать")
        except Exception as e:
            log.exception(f"AI: ошибка экспорта — {e}")

    # =========================================================
    # ОЧИСТКА БАЗЫ
    # =========================================================
    def _clear_database(self):
        ok = ask_confirm(
            self,
            "Очистить базу?",
            "Удалить все записи hypotheses?\n\n"
            "Разметка (feedback) будет СОХРАНЕНА в архив\n"
            "data/ml/exports/feedback_archive.jsonl."
        )
        if not ok:
            return

        try:
            from ml.storage import clear_all_hypotheses
            res = clear_all_hypotheses(archive_feedback=True)
            self.refresh()
        except Exception as e:
            log.exception(f"AI: ошибка очистки — {e}")

    # =========================================================
    # REFRESH
    # =========================================================
    def refresh(self):
        self._current_page = 0
        self._selected_hid = None
        self._load_hypotheses()