# ui/frames/os_mbp_frame.py
"""
Сборка свода ОС и МБП.

ИЗМЕНЕНИЯ:
- Убраны локальные стили прогресс-бара и статуса.
  Теперь они используют глобальный QSS из ui/styles.py.
- Добавлен setObjectName для прогресс-бара и статуса.
- В _on_finish убран зелёный цвет (теперь серый).
"""
import os

from PyQt6.QtCore import Qt, QSettings, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QFileDialog, QCheckBox
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton
)
from ui.icons import get_icon_simple
from utils.logger import log


OS_FILE_KEYWORDS = ("более 100 тыс.", "менее 100 тыс.")
MBP_FILE_KEYWORDS = ("забалансе", "по мбп")


class OsMbpFrame(BaseFrame):

    TITLE = "ОС и МБП"

    def __init__(self, parent, name=None, analyzer=None):
        super().__init__(parent, name)

        self.analyzer = analyzer

        self.os_files = getattr(parent, "os_files", [])
        self.mbp_files = getattr(parent, "mbp_files", [])

        self._settings = QSettings("SilchenkoAleksey", "CoreV3")

        saved = self._settings.value("os_mbp_remove_unwanted", True)
        if isinstance(saved, str):
            saved = saved.lower() in ("true", "1", "yes")
        self._remove_unwanted = bool(saved)

        self._setup_ui()
        self._restore_file_labels()
        self._check_ready()

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

        # --- Заголовок ---
        title = QLabel("ОС И МБП — СБОРКА СВОДА", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # --- Тумблер «Убрать лишнее» ---
        switch_row = QHBoxLayout()
        switch_row.addStretch()

        self.chk_remove_unwanted = QCheckBox("Убрать лишнее", self)
        self.chk_remove_unwanted.setChecked(self._remove_unwanted)
        self.chk_remove_unwanted.setFont(self.FONTS['label'])
        self.chk_remove_unwanted.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_remove_unwanted.setStyleSheet(f"""
            QCheckBox {{
                background-color: transparent;
                color: {self.COLORS.get('text', '#E0E0E0')};
                spacing: 10px;
                padding: 6px 12px;
            }}
            QCheckBox::indicator {{
                width: 22px;
                height: 22px;
                border: 2px solid {self.COLORS.get('border', '#333333')};
                border-radius: 4px;
                background-color: transparent;
            }}
            QCheckBox::indicator:hover {{
                border-color: {self.COLORS.get('text_dim', '#A0A0A0')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.COLORS.get('button', '#D42626')};
                border-color: {self.COLORS.get('button', '#D42626')};
            }}
        """)
        self.chk_remove_unwanted.stateChanged.connect(self._on_remove_unwanted_changed)
        switch_row.addWidget(self.chk_remove_unwanted)

        switch_row.addStretch()
        root_layout.addLayout(switch_row)

        # --- Две карточки: ОС + МБП ---
        cards_row = QHBoxLayout()
        cards_row.setSpacing(15)

        # Карточка ОС
        card_os = create_card(self)
        cards_row.addWidget(card_os, 1)

        os_icon_label = QLabel(card_os)
        os_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        os_icon = get_icon_simple(
            "os_mbp",
            color=self.COLORS.get('text', '#E0E0E0'),
            size=36
        )
        if not os_icon.isNull():
            os_icon_label.setPixmap(os_icon.pixmap(36, 36))
        card_os.layout().addWidget(os_icon_label)

        os_title = QLabel("ОС (Основные средства)", card_os)
        os_title.setFont(self.FONTS['subtitle'])
        os_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_os.layout().addWidget(os_title)

        os_hint = QLabel("Требуется: ведомость по ОС", card_os)
        os_hint.setFont(self.FONTS['small'])
        os_hint.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        os_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_os.layout().addWidget(os_hint)

        btn_os = PrimaryButton(
            "Выбрать файлы ОС",
            on_click=self.choose_os_files,
            parent=card_os
        )
        btn_os.setFixedWidth(220)
        btn_os.setMinimumHeight(44)
        os_btn_icon = get_icon_simple("os_mbp", color="#FFFFFF", size=16)
        if not os_btn_icon.isNull():
            btn_os.setIcon(os_btn_icon)
            btn_os.setIconSize(QSize(16, 16))

        btn_os_wrap = QHBoxLayout()
        btn_os_wrap.addStretch()
        btn_os_wrap.addWidget(btn_os)
        btn_os_wrap.addStretch()
        card_os.layout().addLayout(btn_os_wrap)

        self.lbl_os_status = QLabel("Файлы не выбраны", card_os)
        self.lbl_os_status.setFont(self.FONTS['small'])
        self.lbl_os_status.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        self.lbl_os_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_os_status.setWordWrap(True)
        card_os.layout().addWidget(self.lbl_os_status)

        card_os.layout().addStretch()

        # Карточка МБП
        card_mbp = create_card(self)
        cards_row.addWidget(card_mbp, 1)

        mbp_icon_label = QLabel(card_mbp)
        mbp_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mbp_icon = get_icon_simple(
            "os_mbp",
            color=self.COLORS.get('text', '#E0E0E0'),
            size=36
        )
        if not mbp_icon.isNull():
            mbp_icon_label.setPixmap(mbp_icon.pixmap(36, 36))
        card_mbp.layout().addWidget(mbp_icon_label)

        mbp_title = QLabel("МБП (Малоценные предметы)", card_mbp)
        mbp_title.setFont(self.FONTS['subtitle'])
        mbp_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_mbp.layout().addWidget(mbp_title)

        mbp_hint = QLabel("Требуется: реестр МБП", card_mbp)
        mbp_hint.setFont(self.FONTS['small'])
        mbp_hint.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        mbp_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_mbp.layout().addWidget(mbp_hint)

        btn_mbp = PrimaryButton(
            "Выбрать файлы МБП",
            on_click=self.choose_mbp_files,
            parent=card_mbp
        )
        btn_mbp.setFixedWidth(220)
        btn_mbp.setMinimumHeight(44)
        mbp_btn_icon = get_icon_simple("os_mbp", color="#FFFFFF", size=16)
        if not mbp_btn_icon.isNull():
            btn_mbp.setIcon(mbp_btn_icon)
            btn_mbp.setIconSize(QSize(16, 16))

        btn_mbp_wrap = QHBoxLayout()
        btn_mbp_wrap.addStretch()
        btn_mbp_wrap.addWidget(btn_mbp)
        btn_mbp_wrap.addStretch()
        card_mbp.layout().addLayout(btn_mbp_wrap)

        self.lbl_mbp_status = QLabel("Файлы не выбраны", card_mbp)
        self.lbl_mbp_status.setFont(self.FONTS['small'])
        self.lbl_mbp_status.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        self.lbl_mbp_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mbp_status.setWordWrap(True)
        card_mbp.layout().addWidget(self.lbl_mbp_status)

        card_mbp.layout().addStretch()

        root_layout.addLayout(cards_row)
        root_layout.addStretch()

        # --- Прогресс (глобальный стиль, серый) ---
        progress_row = QVBoxLayout()
        progress_row.setSpacing(6)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("GlobalProgress")
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(14)
        progress_row.addWidget(self.progress_bar)

        # --- Статус (глобальный стиль, нейтральный) ---
        self.status_label = QLabel("Ожидание файлов", self)
        self.status_label.setObjectName("StatusNeutral")
        self.status_label.setFont(self.FONTS['status'])
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_row.addWidget(self.status_label)

        root_layout.addLayout(progress_row)

        # --- Кнопки ---
        action_panel = QHBoxLayout()
        action_panel.setSpacing(10)
        action_panel.addStretch()

        self.btn_run_osmbp = PrimaryButton(
            "СФОРМИРОВАТЬ СВОД",
            on_click=self.start_analysis,
            parent=self
        )
        self.btn_run_osmbp.setMinimumWidth(360)
        self.btn_run_osmbp.setMinimumHeight(52)
        self.btn_run_osmbp.setEnabled(False)
        action_panel.addWidget(self.btn_run_osmbp)

        action_panel.addStretch()
        root_layout.addLayout(action_panel)

        action_panel2 = QHBoxLayout()
        action_panel2.addStretch()

        self.btn_open_osmbp = SecondaryButton(
            "Открыть результат",
            on_click=lambda: self.open_folder("os_mbp"),
            parent=self
        )
        self.btn_open_osmbp.setMinimumWidth(250)
        self.btn_open_osmbp.setMinimumHeight(45)
        self.btn_open_osmbp.setEnabled(False)
        folder_icon = get_icon_simple("gm", color=self.COLORS.get('text', '#E0E0E0'), size=16)
        if not folder_icon.isNull():
            self.btn_open_osmbp.setIcon(folder_icon)
            self.btn_open_osmbp.setIconSize(QSize(16, 16))
        action_panel2.addWidget(self.btn_open_osmbp)

        action_panel2.addStretch()
        root_layout.addLayout(action_panel2)

    # =========================================================
    # ВОССТАНОВЛЕНИЕ СОСТОЯНИЯ
    # =========================================================
    def _restore_file_labels(self):
        self._update_os_label()
        self._update_mbp_label()

    def _update_os_label(self):
        n = len(self.os_files)
        if n == 2:
            self.lbl_os_status.setText("Выбрано: 2")
            self.lbl_os_status.setStyleSheet(
                f"color: {self.COLORS.get('text', '#E0E0E0')};"
            )
        elif n == 0:
            self.lbl_os_status.setText("Файлы не выбраны")
            self.lbl_os_status.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
        else:
            self.lbl_os_status.setText(f"Выбрано: {n} (нужно ровно 2)")
            self.lbl_os_status.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )

    def _update_mbp_label(self):
        n = len(self.mbp_files)
        if n == 2:
            self.lbl_mbp_status.setText("Выбрано: 2")
            self.lbl_mbp_status.setStyleSheet(
                f"color: {self.COLORS.get('text', '#E0E0E0')};"
            )
        elif n == 0:
            self.lbl_mbp_status.setText("Файлы не выбраны")
            self.lbl_mbp_status.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
        else:
            self.lbl_mbp_status.setText(f"Выбрано: {n} (нужно ровно 2)")
            self.lbl_mbp_status.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )

    # =========================================================
    # ТУМБЛЕР
    # =========================================================
    def _on_remove_unwanted_changed(self, state):
        self._remove_unwanted = (state == Qt.CheckState.Checked.value)
        self.app.remove_unwanted = self._remove_unwanted
        try:
            self._settings.setValue("os_mbp_remove_unwanted", self._remove_unwanted)
        except Exception:
            pass

    # =========================================================
    # ВЫБОР ФАЙЛОВ
    # =========================================================
    def _get_last_dir(self):
        last = self._settings.value("os_mbp_last_dir", "")
        if last and os.path.isdir(last):
            return last
        return ""

    def _set_last_dir(self, files):
        if files:
            folder = os.path.dirname(files[0])
            if folder:
                self._settings.setValue("os_mbp_last_dir", folder)

    def choose_os_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы ОС",
            self._get_last_dir(),
            "Excel files (*.xlsx *.xls)"
        )
        if not files:
            return

        self._set_last_dir(files)

        filtered = [f for f in files if any(kw in f.lower() for kw in OS_FILE_KEYWORDS)]

        self.os_files = filtered
        self.app.os_files = filtered

        self._update_os_label()
        self._check_ready()

    def choose_mbp_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы МБП",
            self._get_last_dir(),
            "Excel files (*.xlsx *.xls)"
        )
        if not files:
            return

        self._set_last_dir(files)

        filtered = [f for f in files if any(kw in f.lower() for kw in MBP_FILE_KEYWORDS)]

        self.mbp_files = filtered
        self.app.mbp_files = filtered

        self._update_mbp_label()
        self._check_ready()

    def _check_ready(self):
        ready = (len(self.os_files) == 2 and len(self.mbp_files) == 2)
        self.btn_run_osmbp.setEnabled(ready)

    # =========================================================
    # ЗАПУСК
    # =========================================================
    def start_analysis(self):
        if self.analyzer is None:
            self.show_error("Ошибка", "Анализатор не подключён.")
            return

        self.btn_run_osmbp.setEnabled(False)
        self._set_progress(0)
        self._show_status("Сборка...", self.COLORS.get('text_dim', '#A0A0A0'))

        if hasattr(self.app, "start_progress"):
            self.app.start_progress("Сборка ОС/МБП...")

        self.run_in_thread(self._run_in_bg)

    def _run_in_bg(self):
        try:
            result = self.analyzer.run(
                self.os_files,
                self.mbp_files,
                self._remove_unwanted
            )
            self.run_on_ui(self._on_finish, result)

        except (FileNotFoundError, PermissionError) as e:
            log.error(f"Файловая ошибка при сборке ОС/МБП: {e}")
            err = str(e)
            self.run_on_ui(self.show_error, "Файловая ошибка", err)
            self.run_on_ui(self._reset_state, "Файловая ошибка")

        except (ValueError, KeyError) as e:
            log.error(f"Ошибка данных при сборке ОС/МБП: {e}")
            err = str(e)
            self.run_on_ui(self.show_error, "Ошибка данных", err)
            self.run_on_ui(self._reset_state, "Ошибка данных")

        except Exception as e:
            log.exception("Непредвиденная ошибка сборки ОС/МБП.")
            err = str(e)
            self.run_on_ui(self.show_error, "Ошибка", err)
            self.run_on_ui(self._reset_state, "Ошибка")

    def _reset_state(self, status_text):
        self._show_status(status_text, self.COLORS.get('error', '#FF5252'))
        self.btn_run_osmbp.setEnabled(True)
        if hasattr(self.app, "finish_progress"):
            self.app.finish_progress(False, status_text)

    def _on_finish(self, res):
        self._set_progress(1000)

        if res and res.get("success"):
            self.btn_open_osmbp.setEnabled(True)
            self._show_status(
                "Свод сформирован",
                self.COLORS.get('text_dim', '#A0A0A0')  # Серый, не зелёный
            )
            if hasattr(self.app, "finish_progress"):
                self.app.finish_progress(True, "Свод сформирован")

            self.show_success("Успех", "Свод сформирован.")

            try:
                self.dm.add_action(
                    "Свод ОС/МБП",
                    f"ОС: {len(self.os_files)}, МБП: {len(self.mbp_files)}",
                    "📦"
                )
            except Exception:
                pass
        else:
            self._show_status(
                "Ошибка",
                self.COLORS.get('error', '#FF5252')
            )
            if hasattr(self.app, "finish_progress"):
                self.app.finish_progress(False, "Ошибка")
            self.show_error("Ошибка", "Не удалось сформировать свод.")

        self.btn_run_osmbp.setEnabled(True)

    # =========================================================
    # ПРОГРЕСС / СТАТУС
    # =========================================================
    def _set_progress(self, value):
        self.progress_bar.setValue(int(value))

    def _show_status(self, text, color=None):
        self.status_label.setText(text)
        if color:
            self.status_label.setStyleSheet(f"color: {color};")

    # =========================================================
    # ПРОПЕРТИ
    # =========================================================
    @property
    def dm(self):
        return self.app.data_manager