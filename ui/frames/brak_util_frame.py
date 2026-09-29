# ui/frames/brak_util_frame.py
"""
Проверка Брак/Утиль.

- Выбор двух Excel-файлов (Выборочная проверка + Операции списания)
- Ввод названия ГМ с автокомплитом (QCompleter)
- Прогресс-бар + статус
- Результат с подсветкой расхождений

Улучшения по сравнению с CTk-версией:
- QFileDialog вместо filedialog
- QCompleter вместо самодельного GmAutocomplete
- run_on_ui вместо after(0, ...)
- Исправлен баг с lambda замыканием (NameError 'e')
- Запоминается последняя папка для диалогов (QSettings)

Правки стиля:
- Убраны все эмодзи
- Кнопки — SVG-иконки
"""
import os

from PyQt6.QtCore import Qt, QStringListModel, QSettings, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QCompleter, QProgressBar, QPushButton, QFileDialog, QLineEdit
)

from config import FOLDERS
from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, StyledEntry, PrimaryButton, SecondaryButton
)
from ui.icons import get_icon_simple
from utils.logger import log


FILE1_KEYWORD = "выборочная проверка актов списания утиля"
FILE2_KEYWORD = "операции списания"

GM_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "gm_data.json"
)


class BrakUtilFrame(BaseFrame):

    TITLE = "Проверка Брак/Утиль"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.file1_path = ""
        self.file2_path = ""
        self.gm_data = []

        self._settings = QSettings("SilchenkoAleksey", "CoreV3")

        self._load_gm_data()
        self._setup_ui()

    # =========================================================
    # ЗАГРУЗКА GM_DATA
    # =========================================================
    def _load_gm_data(self):
        import json

        if not os.path.isfile(GM_DATA_PATH):
            log.warning(f"gm_data.json не найден: {GM_DATA_PATH}")
            self.gm_data = []
            return
        try:
            with open(GM_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.gm_data = data
        except Exception as e:
            log.error(f"Ошибка загрузки gm_data.json: {e}")
            self.gm_data = []

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
        title = QLabel("ПРОВЕРКА БРАК/УТИЛЬ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # --- Карточка с настройками ---
        card = create_card(self)

        card_title = QLabel("Выберите исходные файлы", card)
        card_title.setFont(self.FONTS['subtitle'])
        card.layout().addWidget(card_title)

        # --- Файл 1 ---
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        btn_file1 = PrimaryButton(
            "Выборочная проверка...",
            on_click=self._choose_file1,
            parent=card
        )
        btn_file1.setFixedWidth(280)
        btn_file1.setMinimumHeight(42)
        # Иконка файла
        file_icon = get_icon_simple("file", color="#FFFFFF", size=16)
        if not file_icon.isNull():
            btn_file1.setIcon(file_icon)
            btn_file1.setIconSize(QSize(16, 16))
        row1.addWidget(btn_file1)

        self.lbl_file1 = QLabel("Не выбран", card)
        self.lbl_file1.setFont(self.FONTS['small'])
        self.lbl_file1.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        row1.addWidget(self.lbl_file1, 1)

        card.layout().addLayout(row1)

        # --- Файл 2 ---
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        btn_file2 = PrimaryButton(
            "Операции списания",
            on_click=self._choose_file2,
            parent=card
        )
        btn_file2.setFixedWidth(280)
        btn_file2.setMinimumHeight(42)
        file_icon2 = get_icon_simple("file", color="#FFFFFF", size=16)
        if not file_icon2.isNull():
            btn_file2.setIcon(file_icon2)
            btn_file2.setIconSize(QSize(16, 16))
        row2.addWidget(btn_file2)

        self.lbl_file2 = QLabel("Не выбран", card)
        self.lbl_file2.setFont(self.FONTS['small'])
        self.lbl_file2.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        row2.addWidget(self.lbl_file2, 1)

        card.layout().addLayout(row2)

        # --- Подсказка (оставляем символ ⓘ — не эмодзи) ---
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

        # --- Название ГМ ---
        gm_row = QHBoxLayout()
        gm_row.setSpacing(10)

        gm_lbl = QLabel("Название ГМ:", card)
        gm_lbl.setFont(self.FONTS['label'])
        gm_lbl.setFixedWidth(180)
        gm_row.addWidget(gm_lbl)

        self.gm_input = StyledEntry(
            placeholder="Начните вводить название ГМ",
            parent=card
        )
        self.gm_input.setMinimumWidth(400)
        self._attach_gm_completer(self.gm_input)
        self.gm_input.textChanged.connect(self._update_button_state)
        self.gm_input.returnPressed.connect(self._on_enter_pressed)

        gm_row.addWidget(self.gm_input, 1)
        card.layout().addLayout(gm_row)

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

        self.btn_run = PrimaryButton(
            "ЗАПУСТИТЬ АНАЛИЗ",
            on_click=self.start_analysis,
            parent=self
        )
        self.btn_run.setMinimumWidth(280)
        self.btn_run.setMinimumHeight(48)
        self.btn_run.setEnabled(False)
        action_panel.addWidget(self.btn_run)

        self.btn_open = SecondaryButton(
            "Открыть папку с результатом",
            on_click=self._open_result_folder,
            parent=self
        )
        self.btn_open.setMinimumWidth(280)
        self.btn_open.setMinimumHeight(48)
        self.btn_open.setEnabled(False)
        folder_icon = get_icon_simple("gm", color=self.COLORS.get('text', '#E0E0E0'), size=16)
        if not folder_icon.isNull():
            self.btn_open.setIcon(folder_icon)
            self.btn_open.setIconSize(QSize(16, 16))
        action_panel.addWidget(self.btn_open)

        action_panel.addStretch()
        root_layout.addLayout(action_panel)

    # =========================================================
    # АВТОКОМПЛИТ ГМ
    # =========================================================
    def _attach_gm_completer(self, entry: QLineEdit):
        if not self.gm_data:
            return

        items = []
        for gm in self.gm_data:
            code = str(gm.get("Код", ""))
            name = gm.get("Название", "")
            items.append(f"{code} — {name}")

        model = QStringListModel(items, entry)
        completer = QCompleter(model, entry)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(10)

        entry.setCompleter(completer)

        def _on_activated(text):
            if " — " in text:
                name_only = text.split(" — ", 1)[1]
            else:
                name_only = text
            entry.setText(name_only)

        completer.activated.connect(_on_activated)

    # =========================================================
    # ВЫБОР ФАЙЛОВ
    # =========================================================
    def _get_last_dir(self):
        last = self._settings.value("last_dir_brak_util", "")
        if last and os.path.isdir(last):
            return last
        return ""

    def _set_last_dir(self, path):
        folder = os.path.dirname(path)
        if folder:
            self._settings.setValue("last_dir_brak_util", folder)

    def _choose_file1(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл «Выборочная проверка актов списания утиля»",
            self._get_last_dir(),
            "Excel files (*.xlsx *.xls)"
        )
        if not path:
            return

        self._set_last_dir(path)

        if FILE1_KEYWORD not in os.path.basename(path).lower():
            self.lbl_file1.setText("Не тот файл")
            self.lbl_file1.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
            self.file1_path = ""
            self._update_button_state()
            return

        self.file1_path = path
        self.lbl_file1.setText(f"✓ {os.path.basename(path)}")
        self.lbl_file1.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )
        self._update_button_state()

    def _choose_file2(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл «Операции списания»",
            self._get_last_dir(),
            "Excel files (*.xlsx *.xls)"
        )
        if not path:
            return

        self._set_last_dir(path)

        if FILE2_KEYWORD not in os.path.basename(path).lower():
            self.lbl_file2.setText("Не тот файл")
            self.lbl_file2.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
            self.file2_path = ""
            self._update_button_state()
            return

        self.file2_path = path
        self.lbl_file2.setText(f"✓ {os.path.basename(path)}")
        self.lbl_file2.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )
        self._update_button_state()

    def _update_button_state(self):
        ready = (
            bool(self.file1_path)
            and bool(self.file2_path)
            and bool(self.gm_input.text().strip())
        )
        self.btn_run.setEnabled(ready)

    def _on_enter_pressed(self):
        if self.btn_run.isEnabled():
            self.start_analysis()

    # =========================================================
    # ЗАПУСК
    # =========================================================
    def start_analysis(self):
        if not self.file1_path or not self.file2_path:
            self.show_warning("Ошибка", "Выберите оба файла.")
            return

        gm_name = self.gm_input.text().strip()
        if not gm_name:
            self.show_warning("Ошибка", "Введите название ГМ.")
            return

        self.btn_run.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Подготовка...")
        self.status_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )

        if hasattr(self.app, "start_progress"):
            self.app.start_progress("Проверка Брак/Утиль...")

        self.run_in_thread(self._run_in_bg, gm_name)

    def _run_in_bg(self, gm_name):
        from core.brak_util_analyzer import BrakUtilAnalyzer

        def on_progress(value, message=None):
            self.run_on_ui(self._update_progress, value, message)

        try:
            analyzer = BrakUtilAnalyzer()
            result = analyzer.run(
                self.file1_path,
                self.file2_path,
                gm_name,
                progress_callback=on_progress
            )
            self.run_on_ui(self._on_finish, result)

        except (FileNotFoundError, PermissionError) as e:
            log.error(f"Файловая ошибка Брак/Утиль: {e}")
            err = f"Файловая ошибка:\n{e}"
            self.run_on_ui(self._on_error, err)

        except (ValueError, KeyError) as e:
            log.error(f"Ошибка данных Брак/Утиль: {e}")
            err = f"Ошибка данных:\n{e}"
            self.run_on_ui(self._on_error, err)

        except Exception as e:
            log.exception("Непредвиденная ошибка Брак/Утиль")
            err = str(e)
            self.run_on_ui(self._on_error, err)

    def _update_progress(self, value, message):
        self.progress_bar.setValue(int(value * 1000))

        if message:
            self.status_label.setText(message)
            self.status_label.setStyleSheet(
                f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
            )
            if hasattr(self.app, "set_status"):
                self.app.set_status(message)

    # =========================================================
    # РЕЗУЛЬТАТ / ОШИБКИ
    # =========================================================
    def _on_finish(self, res):
        self.btn_run.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.progress_bar.setValue(1000)

        total = res.get("total", 0)
        discrepancies = res.get("discrepancies", [])
        cnt = len(discrepancies)

        if cnt == 0:
            self.status_label.setText("Анализ завершён без расхождений")
            self.status_label.setStyleSheet(
                f"color: {self.COLORS.get('success', '#4CAF50')};"
            )
            if hasattr(self.app, "finish_progress"):
                self.app.finish_progress(True, "Без расхождений")
            self.show_success(
                "Готово",
                f"Анализ завершён без расхождений.\n\n"
                f"Обработано строк: {total}\n\n"
                f"Файл сохранён в папку «Готовые → Брак_утиль»."
            )
        else:
            self.status_label.setText(f"Найдено расхождений: {cnt}")
            self.status_label.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )
            if hasattr(self.app, "finish_progress"):
                self.app.finish_progress(False, f"Расхождений: {cnt}")

            preview = []
            for d in discrepancies[:10]:
                if d.get("sum2") is not None:
                    preview.append(
                        f"• Номер {d['number']}: "
                        f"{d['sum1']:.2f} → {d['sum2']:.2f}  ({d['reason']})"
                    )
                else:
                    preview.append(
                        f"• Номер {d['number']}: {d['reason']}"
                    )
            more = f"\n... и ещё {cnt - 10}" if cnt > 10 else ""

            self.show_warning(
                "Найдены расхождения!",
                f"Найдено расхождений: {cnt}\n\n"
                + "\n".join(preview) + more
                + "\n\nСтроки с расхождениями подсвечены красным.\n"
                + "Файл сохранён в папку «Готовые → Брак_утиль»."
            )

        try:
            self.app.data_manager.add_action(
                "Проверка Брак/Утиль",
                f"Строк: {total}, расхождений: {cnt}",
                "🛢"
            )
        except Exception:
            pass

    def _on_error(self, message):
        self.btn_run.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Ошибка")
        self.status_label.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        if hasattr(self.app, "finish_progress"):
            self.app.finish_progress(False, "Ошибка анализа")
        self.show_error("Ошибка анализа", message)

    # =========================================================
    # ОТКРЫТИЕ ПАПКИ
    # =========================================================
    def _open_result_folder(self):
        folder = FOLDERS.get("brak_util")
        if not folder or not os.path.isdir(folder):
            self.show_warning("Папка", "Папка результата ещё не создана.")
            return
        try:
            os.startfile(folder)
        except Exception as e:
            self.show_error("Ошибка", f"Не удалось открыть папку:\n{e}")