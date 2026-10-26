# ui/frames/brak_util_frame.py
"""
Брак/Утиль — вкладка для сверки актов списания.

ИЗМЕНЕНИЯ:
- Убраны локальные стили прогресс-бара и статуса.
  Теперь они используют глобальный QSS из ui/styles.py.
- Добавлен setObjectName для прогресс-бара и статуса.
"""
import os

from PyQt6.QtCore import Qt, QStringListModel, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QCompleter, QProgressBar, QPushButton,
    QFileDialog, QLineEdit
)

from config import FOLDERS
from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton, StyledEntry,
    style_popup, AnimatedPlaceholderEntry,
)
from ui.icons import get_icon_simple
from utils.logger import log

FILE1_KEYWORD = "выборочная проверка актов списания утиля"
FILE2_KEYWORD = "операции списания"


class BrakUtilFrame(BaseFrame):

    TITLE = "Брак/Утиль"

    def __init__(self, parent, name=None, analyzer=None):
        super().__init__(parent, name)

        self.analyzer = analyzer

        self.file1_path = ""
        self.file2_path = ""

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

        title = QLabel("БРАК / УТИЛЬ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        card = create_card(self)

        # --- ГМ (с автокомплитом) ---
        gm_row = QHBoxLayout()
        gm_row.setSpacing(10)

        lbl_gm = QLabel("ГМ:", card)
        lbl_gm.setFont(self.FONTS['label'])
        lbl_gm.setFixedWidth(180)
        gm_row.addWidget(lbl_gm)

        self.gm_entry = AnimatedPlaceholderEntry(
            placeholder="Код или название ГМ",
            parent=card
        )
        self.gm_entry.setFixedWidth(300)
        gm_row.addWidget(self.gm_entry)

        gm_row.addStretch()
        card.layout().addLayout(gm_row)

        self._attach_gm_completer(self.gm_entry)

        # --- Файл 1 ---
        f1_row = QHBoxLayout()
        f1_row.setSpacing(10)

        btn_f1 = PrimaryButton(
            "Выбрать файл 1",
            on_click=self._choose_file1,
            parent=card
        )
        btn_f1.setFixedWidth(240)
        f1_row.addWidget(btn_f1)

        self.lbl_f1 = QLabel("Не выбран", card)
        self.lbl_f1.setFont(self.FONTS['small'])
        self.lbl_f1.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        f1_row.addWidget(self.lbl_f1, 1)

        card.layout().addLayout(f1_row)

        # --- Файл 2 ---
        f2_row = QHBoxLayout()
        f2_row.setSpacing(10)

        btn_f2 = PrimaryButton(
            "Выбрать файл 2",
            on_click=self._choose_file2,
            parent=card
        )
        btn_f2.setFixedWidth(240)
        f2_row.addWidget(btn_f2)

        self.lbl_f2 = QLabel("Не выбран", card)
        self.lbl_f2.setFont(self.FONTS['small'])
        self.lbl_f2.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        f2_row.addWidget(self.lbl_f2, 1)

        card.layout().addLayout(f2_row)

        # --- ТВОЯ ПОДСКАЗКА ---
        hint = QLabel(
            "ⓘ  Отчёты → Реестр документов ГМ → Список типовых → Все операции списания\n"
            "Статусы операций: «Отправленная в ГК»",
            card
        )
        hint.setFont(self.FONTS['small'])
        hint.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')}; padding-left: 12px;"
        )
        hint.setWordWrap(True)
        card.layout().addWidget(hint)

        root_layout.addWidget(card)

        # --- Прогресс (глобальный стиль, серый) ---
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("GlobalProgress")
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(14)
        root_layout.addWidget(self.progress_bar)

        # --- Статус (глобальный стиль, нейтральный) ---
        self.status_label = QLabel("Ожидание файлов", self)
        self.status_label.setObjectName("StatusNeutral")
        self.status_label.setFont(self.FONTS['small'])
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(self.status_label)

        # --- Кнопка запуска ---
        action = QHBoxLayout()
        action.addStretch()

        self.btn_run = PrimaryButton(
            "ЗАПУСТИТЬ АНАЛИЗ",
            on_click=self._start_analysis,
            parent=self
        )
        self.btn_run.setMinimumWidth(300)
        self.btn_run.setMinimumHeight(48)
        action.addWidget(self.btn_run)

        action.addStretch()
        root_layout.addLayout(action)

        root_layout.addStretch()

    # =========================================================
    # АВТОКОМПЛИТ ГМ
    # =========================================================
    def _attach_gm_completer(self, entry: QLineEdit):
        gm_data = self.app.get_gm_data() or []
        if not gm_data:
            return

        items = []
        for gm in gm_data:
            code = str(gm.get("Код", "")).strip()
            name = gm.get("Название", "")
            if code:
                items.append(f"{code} — {name}")

        model = QStringListModel(items, entry)
        completer = QCompleter(model, entry)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

        style_popup(completer)

        entry.setCompleter(completer)

    # =========================================================
    # ВЫБОР ФАЙЛОВ
    # =========================================================
    def _choose_file1(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Файл 1", "", "Excel (*.xlsx *.xls)"
        )
        if not path:
            return
            
        if FILE1_KEYWORD not in os.path.basename(path).lower():
            self.lbl_f1.setText("Не тот файл")
            self.lbl_f1.setStyleSheet(f"color: {self.COLORS.get('error', '#FF5252')};")
            self.file1_path = ""
            return

        self.file1_path = path
        self.lbl_f1.setText(f"✓ {os.path.basename(path)}")
        self.lbl_f1.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )

    def _choose_file2(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Файл 2", "", "Excel (*.xlsx *.xls)"
        )
        if not path:
            return
            
        if FILE2_KEYWORD not in os.path.basename(path).lower():
            self.lbl_f2.setText("Не тот файл")
            self.lbl_f2.setStyleSheet(f"color: {self.COLORS.get('error', '#FF5252')};")
            self.file2_path = ""
            return

        self.file2_path = path
        self.lbl_f2.setText(f"✓ {os.path.basename(path)}")
        self.lbl_f2.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )

    # =========================================================
    # ЗАПУСК
    # =========================================================
    def _start_analysis(self):
        if not self.file1_path or not self.file2_path:
            self.show_warning("Ошибка", "Выберите оба файла")
            return

        gm = self.gm_entry.text().strip()
        if not gm:
            self.show_warning("Ошибка", "Введите ГМ")
            return

        if self.analyzer is None:
            self.show_error("Ошибка", "Анализатор не подключён.")
            return

        self.btn_run.setEnabled(False)
        self.status_label.setText("Анализ...")
        self.run_in_thread(self._run_bg, gm)

    def _run_bg(self, gm):
        try:
            result = self.analyzer.run(
                self.file1_path, self.file2_path, gm,
                progress_callback=self._on_progress,
            )
            self.run_on_ui(self._on_finish, result)
        except Exception as e:
            log.exception("brak_util analysis failed")
            self.run_on_ui(self.show_error, "Ошибка", str(e))
            self.run_on_ui(self._reset)

    def _on_progress(self, value, message=None):
        try:
            int_value = int(float(value) * 1000)
        except (TypeError, ValueError):
            int_value = 0
        self.run_on_ui(self.progress_bar.setValue, int_value)
        if message:
            self.run_on_ui(self.status_label.setText, message)

    def _on_finish(self, res):
        self.btn_run.setEnabled(True)
        if res and res.get("success"):
            self.status_label.setText("Анализ завершён")
        else:
            self.status_label.setText("Ошибка")

    def _reset(self):
        self.btn_run.setEnabled(True)

    def refresh(self):
        pass