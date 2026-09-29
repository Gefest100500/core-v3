# ui/frames/kv_frame.py
"""
Автоанализ квантов.

- Выбор двух Excel-файлов (РТП + Кванты)
- Подготовка «Позиции для РТП.txt» (коды с потерями >= 1000 руб)
- Запуск анализа квантов
- Прогресс + результат

Чистые функции парсинга вынесены в utils/parsing.py.
"""
import os

import pandas as pd

from PyQt6.QtCore import Qt, QSettings, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QFileDialog
)

from config import FOLDERS
from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton
)
from ui.components.dialogs import ask_confirm
from ui.icons import get_icon_simple
from utils.logger import log
from utils.parsing import to_float_ru, find_column_ci


KV_COL_CODE = "Код ТП"
KV_COL_LOSS = "Потери (руб без НДС)"
KV_LOSS_MIN = 1000.0
KV_EXPORT_FILE = "Позиции для РТП.txt"


class KvFrame(BaseFrame):

    TITLE = "Автоанализ квантов"

    def __init__(self, parent, name=None, analyzer=None):
        super().__init__(parent, name)

        self.analyzer = analyzer

        self.rtp_path = getattr(parent, "rtp_path", "")
        self.kv_path = getattr(parent, "kv_path", "")

        self._settings = QSettings("SilchenkoAleksey", "CoreV3")

        self._setup_ui()
        self._update_button_state()
        self._restore_file_labels()

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

        title = QLabel("АВТОАНАЛИЗ КВАНТОВ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        card = create_card(self)

        header = QLabel("Исходные файлы", card)
        header.setFont(self.FONTS['subtitle'])
        card.layout().addWidget(header)

        # --- РТП ---
        rtp_row = QHBoxLayout()
        rtp_row.setSpacing(10)

        btn_rtp = PrimaryButton(
            "Выбрать РТП.xlsx",
            on_click=self.choose_rtp,
            parent=card
        )
        btn_rtp.setFixedWidth(240)
        btn_rtp.setMinimumHeight(42)
        rtp_row.addWidget(btn_rtp)

        self.lbl_rtp_status = QLabel("Не выбран", card)
        self.lbl_rtp_status.setFont(self.FONTS['small'])
        self.lbl_rtp_status.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        rtp_row.addWidget(self.lbl_rtp_status, 1)

        card.layout().addLayout(rtp_row)

        # --- Кванты ---
        kv_row = QHBoxLayout()
        kv_row.setSpacing(10)

        btn_kv = PrimaryButton(
            "Выбрать Кванты.xlsx",
            on_click=self.choose_kv,
            parent=card
        )
        btn_kv.setFixedWidth(240)
        btn_kv.setMinimumHeight(42)
        kv_row.addWidget(btn_kv)

        self.lbl_kv_status = QLabel("Не выбран", card)
        self.lbl_kv_status.setFont(self.FONTS['small'])
        self.lbl_kv_status.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        kv_row.addWidget(self.lbl_kv_status, 1)

        card.layout().addLayout(kv_row)

        # --- Подготовить файл ТП ---
        tp_row = QHBoxLayout()
        tp_row.setSpacing(10)

        self.btn_prepare_tp = SecondaryButton(
            "Подготовить файл ТП",
            on_click=self.prepare_tp_file,
            parent=card
        )
        self.btn_prepare_tp.setFixedWidth(240)
        self.btn_prepare_tp.setMinimumHeight(42)
        self.btn_prepare_tp.setEnabled(False)
        pencil_icon = get_icon_simple("pencil", color=self.COLORS.get('text', '#E0E0E0'), size=16)
        if not pencil_icon.isNull():
            self.btn_prepare_tp.setIcon(pencil_icon)
            self.btn_prepare_tp.setIconSize(QSize(16, 16))
        tp_row.addWidget(self.btn_prepare_tp)

        tp_hint = QLabel(
            "Создать «Позиции для РТП.txt» из Квантов (≥ 1000 руб)",
            card
        )
        tp_hint.setFont(self.FONTS['small'])
        tp_hint.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        tp_row.addWidget(tp_hint, 1)

        card.layout().addLayout(tp_row)

        root_layout.addWidget(card)
        root_layout.addStretch()

        # --- Прогресс ---
        progress_panel = QVBoxLayout()
        progress_panel.setSpacing(6)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
                border-radius: 7px;
            }}
            QProgressBar::chunk {{
                background-color: {self.COLORS.get('success', '#4CAF50')};
                border-radius: 7px;
            }}
        """)
        progress_panel.addWidget(self.progress_bar)

        self.status_label = QLabel("Ожидание файлов", self)
        self.status_label.setFont(self.FONTS['status'])
        self.status_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_panel.addWidget(self.status_label)

        root_layout.addLayout(progress_panel)

        # --- Кнопки действий ---
        action_panel = QHBoxLayout()
        action_panel.setSpacing(10)
        action_panel.addStretch()

        self.btn_run_kv = PrimaryButton(
            "ЗАПУСТИТЬ РАСЧЁТ",
            on_click=self.start_analysis,
            parent=self
        )
        self.btn_run_kv.setMinimumWidth(280)
        self.btn_run_kv.setMinimumHeight(48)
        self.btn_run_kv.setEnabled(False)
        action_panel.addWidget(self.btn_run_kv)

        self.btn_open_kv = SecondaryButton(
            "Открыть результат",
            on_click=lambda: self.open_folder("kv"),
            parent=self
        )
        self.btn_open_kv.setMinimumWidth(280)
        self.btn_open_kv.setMinimumHeight(48)
        self.btn_open_kv.setEnabled(False)
        action_panel.addWidget(self.btn_open_kv)

        action_panel.addStretch()
        root_layout.addLayout(action_panel)

    # =========================================================
    # ВОССТАНОВЛЕНИЕ СОСТОЯНИЯ
    # =========================================================
    def _restore_file_labels(self):
        if self.rtp_path and os.path.isfile(self.rtp_path):
            self.lbl_rtp_status.setText(f"✓ {os.path.basename(self.rtp_path)}")
            self.lbl_rtp_status.setStyleSheet(
                f"color: {self.COLORS.get('text', '#E0E0E0')};"
            )

        if self.kv_path and os.path.isfile(self.kv_path):
            self.lbl_kv_status.setText(f"✓ {os.path.basename(self.kv_path)}")
            self.lbl_kv_status.setStyleSheet(
                f"color: {self.COLORS.get('text', '#E0E0E0')};"
            )

    # =========================================================
    # ВЫБОР ФАЙЛОВ
    # =========================================================
    def _get_last_dir(self):
        last = self._settings.value("kv_last_dir", "")
        if last and os.path.isdir(last):
            return last
        return ""

    def _set_last_dir(self, path):
        folder = os.path.dirname(path)
        if folder:
            self._settings.setValue("kv_last_dir", folder)

    def choose_rtp(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл РТП",
            self._get_last_dir(),
            "Excel files (*.xlsx *.xls)"
        )
        if not path:
            return

        self._set_last_dir(path)
        self.rtp_path = path
        self.app.rtp_path = path

        self.lbl_rtp_status.setText(f"✓ {os.path.basename(path)}")
        self.lbl_rtp_status.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )
        self._update_button_state()

    def choose_kv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл Кванты",
            self._get_last_dir(),
            "Excel files (*.xlsx *.xls)"
        )
        if not path:
            return

        self._set_last_dir(path)
        self.kv_path = path
        self.app.kv_path = path

        self.lbl_kv_status.setText(f"✓ {os.path.basename(path)}")
        self.lbl_kv_status.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )
        self._update_button_state()

    def _update_button_state(self):
        ready_run = bool(self.rtp_path and self.kv_path)
        self.btn_run_kv.setEnabled(ready_run)

        ready_tp = bool(self.kv_path and os.path.isfile(self.kv_path))
        self.btn_prepare_tp.setEnabled(ready_tp)

    # =========================================================
    # ПОДГОТОВКА ФАЙЛА ТП
    # =========================================================
    def prepare_tp_file(self):
        if not self.kv_path:
            self.show_warning("Файл ТП", "Сначала выберите файл Кванты")
            return

        if not os.path.isfile(self.kv_path):
            self.show_error("Файл ТП", f"Файл не найден:\n{self.kv_path}")
            return

        try:
            self.set_status("Подготовка файла ТП...")
            self.btn_prepare_tp.setEnabled(False)

            df = pd.read_excel(self.kv_path)
            log.info(f"Кванты.xlsx столбцы: {list(df.columns)}")

            col_code = find_column_ci(df, KV_COL_CODE)
            col_loss = find_column_ci(df, KV_COL_LOSS)

            if col_code is None:
                raise RuntimeError(
                    f"Не найден столбец «{KV_COL_CODE}».\n"
                    f"Есть: {list(df.columns)}"
                )
            if col_loss is None:
                raise RuntimeError(
                    f"Не найден столбец «{KV_COL_LOSS}».\n"
                    f"Есть: {list(df.columns)}"
                )

            df["_loss_num"] = df[col_loss].apply(to_float_ru)
            filtered = df[df["_loss_num"].abs() >= KV_LOSS_MIN]

            log.info(f"После фильтра >= {KV_LOSS_MIN}: {len(filtered)} строк из {len(df)}")

            codes = (
                filtered[col_code]
                .dropna()
                .astype(str)
                .str.strip()
            )
            codes = codes.str.replace(r"\.0$", "", regex=True)
            codes = sorted(set(codes[codes != ""]))

            if not codes:
                self.show_warning(
                    "Файл ТП",
                    f"После фильтра ≥ {KV_LOSS_MIN:.0f} руб кодов не осталось."
                )
                self.set_status("Нет данных", self.COLORS.get('error', '#FF5252'))
                self.btn_prepare_tp.setEnabled(True)
                return

            out_dir = FOLDERS.get("kv")
            if not out_dir:
                raise RuntimeError("Папка «Готовые/Кванты» не найдена в config")

            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, KV_EXPORT_FILE)

            if os.path.exists(out_path):
                ok = ask_confirm(
                    self,
                    "Перезаписать файл?",
                    f"Файл уже существует:\n{out_path}\n\nПерезаписать?"
                )
                if not ok:
                    self.set_status("Отменено", self.COLORS.get('text_dim', '#A0A0A0'))
                    self.btn_prepare_tp.setEnabled(True)
                    return

            with open(out_path, "w", encoding="utf-8") as f:
                for code in codes:
                    f.write(f"{code}\n")

            log.info(f"Файл ТП создан: {out_path} (позиций: {len(codes)})")

            self.set_status(
                f"Файл ТП создан: {KV_EXPORT_FILE} ({len(codes)} позиций)",
                self.COLORS.get('success', '#4CAF50')
            )
            self.show_success(
                "Файл ТП готов",
                f"Создан файл:\n{KV_EXPORT_FILE}\n\n"
                f"Позиций: {len(codes)}\n"
                f"Из {len(df)} строк исходного файла.\n\n"
                f"Позиции с потерями ≥ {KV_LOSS_MIN:.0f} руб."
            )

            try:
                self.dm.add_action(
                    "Подготовка файла ТП",
                    f"Позиций: {len(codes)}",
                    "📝"
                )
            except Exception:
                pass

        except (FileNotFoundError, PermissionError) as e:
            log.error(f"Файловая ошибка при подготовке файла ТП: {e}")
            self.show_error("Файловая ошибка", str(e))
            self.set_status("Файловая ошибка", self.COLORS.get('error', '#FF5252'))
        except (ValueError, KeyError) as e:
            log.error(f"Ошибка данных при подготовке файла ТП: {e}")
            self.show_error("Ошибка данных", str(e))
            self.set_status("Ошибка данных", self.COLORS.get('error', '#FF5252'))
        except Exception as e:
            log.exception("Непредвиденная ошибка подготовки файла ТП")
            self.show_error("Ошибка", str(e))
            self.set_status("Ошибка подготовки файла ТП", self.COLORS.get('error', '#FF5252'))
        finally:
            self.btn_prepare_tp.setEnabled(True)

    # =========================================================
    # ЗАПУСК АНАЛИЗА
    # =========================================================
    def start_analysis(self):
        if not self.rtp_path or not self.kv_path:
            self.show_warning("Ошибка", "Выберите оба файла")
            return

        if self.analyzer is None:
            self.show_error("Ошибка", "Анализатор не подключён.")
            return

        self.btn_run_kv.setEnabled(False)
        self._show_status("Идёт анализ...", "#FFD700")
        self._set_progress(0)

        self.start_progress("Анализ квантов...")

        self.run_in_thread(self._run_in_bg)

    def _run_in_bg(self):
        try:
            result = self.analyzer.run(
                self.rtp_path,
                self.kv_path,
                progress_callback=self._on_progress
            )
            self.run_on_ui(self._on_finish, result)

        except (FileNotFoundError, PermissionError) as e:
            log.error(f"Файловая ошибка при анализе квантов: {e}")
            err = str(e)
            self.run_on_ui(self.show_error, "Файловая ошибка", err)
            self.run_on_ui(self._reset_state, "Файловая ошибка")

        except (ValueError, KeyError) as e:
            log.error(f"Ошибка данных при анализе квантов: {e}")
            err = str(e)
            self.run_on_ui(self.show_error, "Ошибка данных", err)
            self.run_on_ui(self._reset_state, "Ошибка данных")

        except Exception as e:
            log.exception("Непредвиденная ошибка анализа квантов.")
            err = str(e)
            self.run_on_ui(self.show_error, "Ошибка", err)
            self.run_on_ui(self._reset_state, "Ошибка")

    def _on_progress(self, value, message=None):
        try:
            int_value = int(float(value) * 1000)
        except (TypeError, ValueError):
            int_value = 0

        self.run_on_ui(self._set_progress, int_value)
        if message:
            self.run_on_ui(self._show_status, message, "#FFD700")
        self.run_on_ui(self.update_progress, value)

    def _reset_state(self, status_text):
        self._show_status(status_text, self.COLORS.get('error', '#FF5252'))
        self.btn_run_kv.setEnabled(True)
        self.finish_progress(False, status_text)

    def _on_finish(self, res):
        self._set_progress(1000)

        if res and res.get("success"):
            self._show_status(
                "Анализ завершён",
                self.COLORS.get('success', '#4CAF50')
            )
            self.btn_open_kv.setEnabled(True)
            self.finish_progress(True, "Анализ завершён")

            self.show_success(
                "Успех",
                "Анализ завершён.\nРезультаты сохранены в папку Кванты."
            )
        else:
            self._show_status(
                "Ошибка расчёта",
                self.COLORS.get('error', '#FF5252')
            )
            self.finish_progress(False, "Ошибка расчёта")

        self.btn_run_kv.setEnabled(True)

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