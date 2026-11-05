# ui/frames/pal_frame.py
"""
Анализ паллет.

ИЗМЕНЕНИЯ:
- Убран лейбл «Сумма расхождений» (total_sum больше не считается).
- Подсказка и проверка файлов: имя — 6-значный номер паллеты.
- Добавлена кнопка «Файл инвентаризации» (активна после успешного запуска).
"""
import os
import re

from PyQt6.QtCore import Qt, QSettings, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QFileDialog
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton
)
from ui.icons import get_icon_simple
from utils.logger import log


EXCEL_EXTENSIONS = (".xlsx", ".xls")
PALLET_NAME_RE = re.compile(r"^\d{6}$")


class PalFrame(BaseFrame):

    TITLE = "Анализ паллет"

    def __init__(self, parent, name=None, analyzer=None):
        super().__init__(parent, name)

        self.analyzer = analyzer
        self.pal_folder = getattr(parent, "pal_folder", "")

        self._settings = QSettings("SilchenkoAleksey", "CoreV3")

        self._last_inventory_file = ""

        self._setup_ui()
        self._restore_state()

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

        title = QLabel("АНАЛИЗ ПАЛЛЕТ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        card = create_card(self)

        icon_label = QLabel(card)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        folder_icon = get_icon_simple(
            "gm",
            color=self.COLORS.get('text_dim', '#A0A0A0'),
            size=48
        )
        if not folder_icon.isNull():
            icon_label.setPixmap(folder_icon.pixmap(48, 48))
        card.layout().addWidget(icon_label)

        card_title = QLabel("Выберите папку с файлами паллет", card)
        card_title.setFont(self.FONTS['subtitle'])
        card_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.layout().addWidget(card_title)

        card_hint = QLabel(
            "Имена файлов: номер паллеты (6 цифр), например 528596.xls",
            card
        )
        card_hint.setFont(self.FONTS['small'])
        card_hint.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        card_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.layout().addWidget(card_hint)

        btn_folder = PrimaryButton(
            "Выбрать папку",
            on_click=self.choose_folder,
            parent=card
        )
        btn_folder.setFixedWidth(250)
        btn_folder.setMinimumHeight(40)
        btn_folder_icon = get_icon_simple("gm", color="#FFFFFF", size=16)
        if not btn_folder_icon.isNull():
            btn_folder.setIcon(btn_folder_icon)
            btn_folder.setIconSize(QSize(16, 16))

        btn_folder_wrap = QHBoxLayout()
        btn_folder_wrap.addStretch()
        btn_folder_wrap.addWidget(btn_folder)
        btn_folder_wrap.addStretch()
        card.layout().addLayout(btn_folder_wrap)

        self.lbl_folder_status = QLabel("Папка не выбрана", card)
        self.lbl_folder_status.setFont(self.FONTS['small'])
        self.lbl_folder_status.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        self.lbl_folder_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_folder_status.setWordWrap(True)
        card.layout().addWidget(self.lbl_folder_status)

        self.lbl_folder_path = QLabel("", card)
        self.lbl_folder_path.setFont(self.FONTS['small'])
        self.lbl_folder_path.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.lbl_folder_path.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_folder_path.setWordWrap(True)
        card.layout().addWidget(self.lbl_folder_path)

        root_layout.addWidget(card)
        root_layout.addStretch()

        # --- Прогресс ---
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

        self.status_label = QLabel("Ожидание...", self)
        self.status_label.setObjectName("StatusNeutral")
        self.status_label.setFont(self.FONTS['status'])
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_row.addWidget(self.status_label)

        root_layout.addLayout(progress_row)

        # --- Кнопки ---
        action_panel = QHBoxLayout()
        action_panel.setSpacing(20)
        action_panel.addStretch()

        self.btn_run_pal = PrimaryButton(
            "Собрать отчёт",
            on_click=self.start_analysis,
            parent=self
        )
        self.btn_run_pal.setMinimumWidth(220)
        self.btn_run_pal.setMinimumHeight(45)
        self.btn_run_pal.setEnabled(False)
        action_panel.addWidget(self.btn_run_pal)

        self.btn_inventory = SecondaryButton(
            "Файл инвентаризации",
            on_click=self.open_inventory_file,
            parent=self
        )
        self.btn_inventory.setMinimumWidth(220)
        self.btn_inventory.setMinimumHeight(45)
        self.btn_inventory.setEnabled(False)
        action_panel.addWidget(self.btn_inventory)

        self.btn_open_pal = SecondaryButton(
            "Открыть результат",
            on_click=lambda: self.open_folder("pal"),
            parent=self
        )
        self.btn_open_pal.setMinimumWidth(220)
        self.btn_open_pal.setMinimumHeight(45)
        self.btn_open_pal.setEnabled(False)
        action_panel.addWidget(self.btn_open_pal)

        action_panel.addStretch()
        root_layout.addLayout(action_panel)

    # =========================================================
    # ВОССТАНОВЛЕНИЕ СОСТОЯНИЯ
    # =========================================================
    def _restore_state(self):
        if self.pal_folder and os.path.isdir(self.pal_folder):
            self._update_folder_status(self.pal_folder, check_files=True)

    # =========================================================
    # ВЫБОР ПАПКИ
    # =========================================================
    def _get_last_dir(self):
        last = self._settings.value("pal_last_dir", "")
        if last and os.path.isdir(last):
            return last
        return ""

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку с файлами паллет",
            self._get_last_dir()
        )
        if not path:
            return

        self.pal_folder = path
        self.app.pal_folder = path

        try:
            self._settings.setValue("pal_last_dir", path)
        except Exception:
            pass

        self._update_folder_status(path, check_files=True)

    def _update_folder_status(self, path, check_files=False):
        self.lbl_folder_path.setText(path)

        if not check_files:
            self.lbl_folder_status.setText("Папка выбрана")
            self.lbl_folder_status.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
            )
            self.btn_run_pal.setEnabled(True)
            return

        try:
            files = os.listdir(path)
        except (PermissionError, OSError) as e:
            self.lbl_folder_status.setText(f"Нет доступа: {e}")
            self.lbl_folder_status.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
            self.btn_run_pal.setEnabled(False)
            return

        count = 0
        for f in files:
            base, ext = os.path.splitext(f)
            if ext.lower() not in EXCEL_EXTENSIONS:
                continue
            if PALLET_NAME_RE.match(base):
                count += 1

        if count > 0:
            self.lbl_folder_status.setText(f"Найдено файлов: {count}")
            self.lbl_folder_status.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
            )
            self.btn_run_pal.setEnabled(True)
        else:
            self.lbl_folder_status.setText(
                "Нет файлов с именем из 6 цифр (например, 528596.xls)"
            )
            self.lbl_folder_status.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
            self.btn_run_pal.setEnabled(False)

    # =========================================================
    # ЗАПУСК
    # =========================================================
    def start_analysis(self):
        if self.analyzer is None:
            self.show_error("Ошибка", "Анализатор не подключён.")
            return

        self.btn_run_pal.setEnabled(False)
        self.btn_inventory.setEnabled(False)
        self._set_progress(0)
        self._show_status("Сборка...", self.COLORS.get('text_dim', '#A0A0A0'))

        if hasattr(self.app, "start_progress"):
            self.app.start_progress("Сборка паллет...")

        self.run_in_thread(self._run_in_bg)

    def _run_in_bg(self):
        try:
            result = self.analyzer.run(self.pal_folder)
            self.run_on_ui(self._on_finish, result)

        except (FileNotFoundError, PermissionError) as e:
            log.error(f"Файловая ошибка при сборке паллет: {e}")
            err = str(e)
            self.run_on_ui(self.show_error, "Файловая ошибка", err)
            self.run_on_ui(self._reset_state, "Файловая ошибка")

        except (ValueError, KeyError) as e:
            log.error(f"Ошибка данных при сборке паллет: {e}")
            err = str(e)
            self.run_on_ui(self.show_error, "Ошибка данных", err)
            self.run_on_ui(self._reset_state, "Ошибка данных")

        except Exception as e:
            log.exception("Непредвиденная ошибка сборки паллет.")
            err = str(e)
            self.run_on_ui(self.show_error, "Ошибка", err)
            self.run_on_ui(self._reset_state, "Ошибка")

    def _reset_state(self, status_text):
        self._show_status(status_text, self.COLORS.get('error', '#FF5252'))
        self.btn_run_pal.setEnabled(True)
        if hasattr(self.app, "finish_progress"):
            self.app.finish_progress(False, status_text)

    def _on_finish(self, res):
        self._set_progress(1000)

        if res and res.get("success"):
            self._show_status(
                "Готово!",
                self.COLORS.get('text_dim', '#A0A0A0')
            )

            self._last_inventory_file = res.get("inventory_file", "")

            self.btn_open_pal.setEnabled(True)
            if self._last_inventory_file and os.path.isfile(self._last_inventory_file):
                self.btn_inventory.setEnabled(True)

            if hasattr(self.app, "finish_progress"):
                self.app.finish_progress(True, "Готово")

            try:
                self.dm.add_action(
                    "Анализ паллет",
                    "Сводка готова",
                    "🧩"
                )
            except Exception:
                pass

        else:
            self._show_status(
                "Провал",
                self.COLORS.get('error', '#FF5252')
            )
            if hasattr(self.app, "finish_progress"):
                self.app.finish_progress(False, "Провал")

        self.btn_run_pal.setEnabled(True)

    # =========================================================
    # ФАЙЛ ИНВЕНТАРИЗАЦИИ
    # =========================================================
    def open_inventory_file(self):
        if not self._last_inventory_file or not os.path.isfile(self._last_inventory_file):
            self.show_warning("Файл не найден", "Сначала выполните сборку отчёта.")
            return

        self.show_success(
            "Файл инвентаризации",
            f"Файл создан:\n{self._last_inventory_file}"
        )

        try:
            os.startfile(os.path.dirname(self._last_inventory_file))
        except Exception as e:
            log.warning(f"Не удалось открыть папку: {e}")

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