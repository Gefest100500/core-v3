# ui/frames/violations_frame.py
"""
Анализ нарушений (Трассировщик правил) — интерфейс.

ИЗМЕНЕНИЯ:
- Инвентаризация теперь выводится в виде списка:
  Дата 1: X шт.
  Дата 2: Y шт.
"""
import os

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QFileDialog, QListWidget, QListWidgetItem, QProgressBar,
    QSplitter, QFormLayout, QScrollArea
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton
)
from ui.icons import get_icon_simple
from utils.logger import log


class ViolationsFrame(BaseFrame):

    TITLE = "Анализ нарушений"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.codes_path = ""
        self.rtp_path = ""
        self.results = []

        self._setup_ui()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

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

        title = QLabel("АНАЛИЗ НАРУШЕНИЙ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        self.upload_card = create_card(self)
        upload_layout = self.upload_card.layout()
        upload_layout.setSpacing(10)

        codes_row = QHBoxLayout()
        codes_row.setSpacing(10)

        self.btn_codes = PrimaryButton(
            "Выбрать файл с кодами",
            on_click=self._choose_codes,
            parent=self.upload_card
        )
        self.btn_codes.setFixedWidth(260)
        self.btn_codes.setMinimumHeight(40)
        codes_row.addWidget(self.btn_codes)

        self.lbl_codes = QLabel("Не выбран", self.upload_card)
        self.lbl_codes.setFont(self.FONTS['small'])
        self.lbl_codes.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        codes_row.addWidget(self.lbl_codes, 1)
        upload_layout.addLayout(codes_row)

        rtp_row = QHBoxLayout()
        rtp_row.setSpacing(10)

        self.btn_rtp = PrimaryButton(
            "Выбрать РТП",
            on_click=self._choose_rtp,
            parent=self.upload_card
        )
        self.btn_rtp.setFixedWidth(260)
        self.btn_rtp.setMinimumHeight(40)
        rtp_row.addWidget(self.btn_rtp)

        self.lbl_rtp = QLabel("Не выбран", self.upload_card)
        self.lbl_rtp.setFont(self.FONTS['small'])
        self.lbl_rtp.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        rtp_row.addWidget(self.lbl_rtp, 1)
        upload_layout.addLayout(rtp_row)

        root_layout.addWidget(self.upload_card, 0)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(14)
        root_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ожидание файлов", self)
        self.status_label.setFont(self.FONTS['small'])
        self.status_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(self.status_label)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {self.COLORS.get('border', '#333333')};
                width: 2px;
            }}
        """)

        self.list_widget = QListWidget(self.splitter)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {self.COLORS.get('card', '#222222')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 10px;
                border-bottom: 1px solid #2A2A2A;
                border-left: 3px solid transparent;
            }}
            QListWidget::item:hover {{
                background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
            }}
            QListWidget::item:selected {{
                background-color: #333333;
                color: #FFFFFF;
                border-left: 3px solid {self.COLORS.get('button', '#D42626')};
            }}
        """)
        self.list_widget.itemSelectionChanged.connect(self._on_select)
        self.splitter.addWidget(self.list_widget)

        details_frame = QFrame(self.splitter)
        details_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.COLORS.get('card', '#222222')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
            }}
        """)
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(16, 16, 16, 16)
        details_layout.setSpacing(10)

        details_title = QLabel("ДЕТАЛИ ПОЗИЦИИ", details_frame)
        details_title.setFont(self.FONTS['subtitle'])
        details_title.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )
        details_layout.addWidget(details_title)

        details_scroll = QScrollArea(details_frame)
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        details_scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.details_content = QWidget()
        self.details_form = QFormLayout(self.details_content)
        self.details_form.setContentsMargins(0, 0, 0, 0)
        self.details_form.setSpacing(10)
        self.details_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        details_scroll.setWidget(self.details_content)
        details_layout.addWidget(details_scroll, 1)

        self.splitter.addWidget(details_frame)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([700, 400])

        self.splitter.setVisible(False)
        root_layout.addWidget(self.splitter, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self.btn_run = PrimaryButton(
            "ЗАПУСТИТЬ АНАЛИЗ",
            on_click=self._start_analysis,
            parent=self
        )
        self.btn_run.setMinimumWidth(280)
        self.btn_run.setMinimumHeight(46)
        play_icon = get_icon_simple("check", color="#FFFFFF", size=16)
        if not play_icon.isNull():
            self.btn_run.setIcon(play_icon)
            self.btn_run.setIconSize(QSize(16, 16))
        btn_row.addWidget(self.btn_run)

        self.btn_reset = SecondaryButton(
            "← Назад к загрузке",
            on_click=self._reset_to_upload,
            parent=self
        )
        self.btn_reset.setMinimumWidth(240)
        self.btn_reset.setMinimumHeight(46)
        back_icon = get_icon_simple(
            "refresh", color=self.COLORS.get('text', '#E0E0E0'), size=16
        )
        if not back_icon.isNull():
            self.btn_reset.setIcon(back_icon)
            self.btn_reset.setIconSize(QSize(16, 16))
        self.btn_reset.setVisible(False)
        btn_row.addWidget(self.btn_reset)

        btn_row.addStretch()
        root_layout.addLayout(btn_row)

    # =========================================================
    # ВЫБОР ФАЙЛОВ
    # =========================================================
    def _choose_codes(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Файл с кодами товаров", "",
            "Excel files (*.xlsx *.xls)"
        )
        if not path:
            return
        self.codes_path = path
        self.lbl_codes.setText(f"✓ {os.path.basename(path)}")
        self.lbl_codes.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )

    def _choose_rtp(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Файл РТП", "",
            "Excel files (*.xlsx *.xls)"
        )
        if not path:
            return
        self.rtp_path = path
        self.lbl_rtp.setText(f"✓ {os.path.basename(path)}")
        self.lbl_rtp.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )

    # =========================================================
    # ЗАПУСК
    # =========================================================
    def _start_analysis(self):
        if not self.codes_path:
            self.show_warning("Ошибка", "Выберите файл с кодами товаров.")
            return
        if not self.rtp_path:
            self.show_warning("Ошибка", "Выберите файл РТП.")
            return

        self.btn_run.setEnabled(False)
        self.btn_reset.setVisible(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Анализ...")
        self.status_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )

        self.run_in_thread(self._run_bg, self.codes_path, self.rtp_path)

    def _run_bg(self, codes_path, rtp_path):
        try:
            from core.violations_analyzer import ViolationsAnalyzer
            analyzer = ViolationsAnalyzer()
            result = analyzer.run(
                codes_path,
                rtp_path,
                progress_callback=self._on_progress
            )
            self.run_on_ui(self._on_finish, result)
        except Exception as e:
            log.exception("Ошибка анализа нарушений")
            self.run_on_ui(self._on_error, str(e))

    def _on_progress(self, value, message=None):
        try:
            int_value = int(float(value) * 1000)
        except (TypeError, ValueError):
            int_value = 0
        self.run_on_ui(self.progress_bar.setValue, int_value)
        if message:
            self.run_on_ui(self.status_label.setText, message)

    def _on_finish(self, res):
        if not res or not res.get("success"):
            self._on_error("Анализ не вернул результат.")
            return

        self.results = res.get("rows", [])

        self.upload_card.setVisible(False)
        self.btn_run.setVisible(False)
        self.btn_reset.setVisible(True)
        self.splitter.setVisible(True)

        self._fill_list(self.results)

        if self.results:
            self.status_label.setText(f"Найдено нарушений: {len(self.results)}")
            self.status_label.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
        else:
            self.status_label.setText("Нарушений не найдено")
            self.status_label.setStyleSheet(
                f"color: {self.COLORS.get('success', '#4CAF50')};"
            )

        self.progress_bar.setValue(1000)

    def _on_error(self, err):
        self.btn_run.setEnabled(True)
        self.btn_run.setVisible(True)
        self.btn_reset.setVisible(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Ошибка анализа")
        self.status_label.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        self.show_error("Ошибка", err)

    # =========================================================
    # СБРОС К НАЧАЛУ
    # =========================================================
    def _reset_to_upload(self):
        self.upload_card.setVisible(True)
        self.btn_run.setVisible(True)
        self.btn_run.setEnabled(True)
        self.splitter.setVisible(False)
        self.btn_reset.setVisible(False)
        self.list_widget.clear()
        self._clear_details()
        self.results = []
        self.progress_bar.setValue(0)
        self.status_label.setText("Ожидание файлов")
        self.status_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )

    # =========================================================
    # СПИСОК
    # =========================================================
    def _fill_list(self, rows):
        self.list_widget.clear()

        if not rows:
            item = QListWidgetItem("Нарушений не найдено")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setForeground(QColor(self.COLORS.get('text_dim', '#A0A0A0')))
            self.list_widget.addItem(item)
            return

        for row in rows:
            code = str(row.get("code", ""))
            name = str(row.get("name", ""))
            reason = str(row.get("reason", ""))

            text = f"{code} — {reason}"
            if name:
                text = f"{code} — {name} — {reason}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, row)
            item.setForeground(QColor(self.COLORS.get('error', '#FF5252')))
            self.list_widget.addItem(item)

    # =========================================================
    # ДЕТАЛИ
    # =========================================================
    def _on_select(self):
        items = self.list_widget.selectedItems()
        if not items:
            self._clear_details()
            return

        row = items[0].data(Qt.ItemDataRole.UserRole)
        if not row:
            self._clear_details()
            return

        self._show_details(row)

    def _clear_details(self):
        while self.details_form.count():
            item = self.details_form.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _show_details(self, row):
        self._clear_details()

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

        add_row("Код:", row.get("code", ""))
        add_row("Наименование:", row.get("name", ""))
        add_row("Группа:", row.get("gr20", ""))
        add_row("Знак:", row.get("sign", ""), 
                self.COLORS.get('error', '#FF5252') if row.get("sign") == "Недостача" else self.COLORS.get('success', '#4CAF50'))
        
        add_row("Причина:", row.get("reason", ""), self.COLORS.get('error', '#FF5252'))

        features = row.get("features", {})
        rule = features.get("rule", "")
        if rule:
            rule_text = f"{rule}"
            dev = features.get("deviation")
            if dev:
                rule_text += f" (отклонение {dev})"
            add_row("Сработало правило:", rule_text, self.COLORS.get('text', '#E0E0E0'))

        # Вывод информации об инвентаризации (список)
        inv_details = row.get("inv_details", [])
        
        if inv_details:
            # Добавляем заголовок блока
            add_row("Посчитано в Инвентаризацию:", "", self.COLORS.get('button', '#D42626'))
            
            for (d_str, q_val) in inv_details:
                # Форматируем количество
                if isinstance(q_val, float) and q_val.is_integer():
                    qty_str = str(int(q_val))
                else:
                    qty_str = str(q_val)
                
                add_row(f"  {d_str}:", f"{qty_str} шт.")

    def refresh(self):
        pass