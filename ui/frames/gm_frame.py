# ui/frames/gm_frame.py
"""
Сетевые папки ГМ.

- Поиск ГМ по коду или названию (с автокомплитом)
- Создание папки ПИ ГМ {Название} {ДД.ММ.ГГГГ} в сетевой папке
- Создание 5 подпапок внутри (1-4 сутки + Итоговые)
- Создание ярлыка на рабочем столе

Улучшения по сравнению с CTk-версией:
- QCompleter вместо ручного поиска
- win32com.client для создания ярлыков (быстрее PowerShell)
- Fallback на PowerShell, если win32com не сработал
- Двойной клик по результату — сразу создать ярлык
- Запоминание последнего запроса (QSettings)

Правки стиля:
- Убраны все эмодзи
- Кнопки — SVG-иконки
"""
import os
import json
import subprocess
from datetime import datetime

from PyQt6.QtCore import Qt, QStringListModel, QSettings, QSize
from PyQt6.QtGui import QIcon, QMouseEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QCompleter, QPushButton, QLineEdit
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, StyledEntry, PrimaryButton, SecondaryButton
)
from ui.icons import get_icon_simple
from utils.logger import log


GM_REQUIRED_KEYS = ("Код", "Название", "Папка")
MAX_SHORTCUT_NAME_LEN = 100
PI_SUBFOLDERS = ["1 сутки", "2 сутки", "3 сутки", "4 сутки", "Итоговые"]

GM_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "gm_data.json"
)


class GmFrame(BaseFrame):

    TITLE = "Сетевые папки ГМ"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.selected_gm = None
        self.selected_gm_row = None

        self._settings = QSettings("SilchenkoAleksey", "CoreV3")

        self._setup_ui()
        self._restore_last_query()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        # Заголовок (без эмодзи)
        title = QLabel("СЕТЕВЫЕ ПАПКИ ГМ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # Поле поиска
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        search_row.addStretch()

        self.entry_gm = StyledEntry(
            placeholder="Введите код или название магазина",
            parent=self
        )
        self.entry_gm.setMinimumWidth(500)
        self.entry_gm.setMinimumHeight(40)
        self.entry_gm.returnPressed.connect(self.search)
        search_row.addWidget(self.entry_gm)

        # 🆕 Кнопка "Найти" с SVG
        btn_search = PrimaryButton(
            "Найти",
            on_click=self.search,
            parent=self
        )
        btn_search.setFixedWidth(200)
        btn_search.setMinimumHeight(40)
        search_icon = get_icon_simple("search", color="#FFFFFF", size=16)
        if not search_icon.isNull():
            btn_search.setIcon(search_icon)
            btn_search.setIconSize(QSize(16, 16))
        search_row.addWidget(btn_search)

        search_row.addStretch()
        root_layout.addLayout(search_row)

        # Статус
        self.status_label = QLabel("Введите запрос для поиска", self)
        self.status_label.setFont(self.FONTS['small'])
        self.status_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(self.status_label)

        # Контейнер результатов
        results_label = QLabel("Результаты поиска", self)
        results_label.setFont(self.FONTS['subtitle'])
        root_layout.addWidget(results_label)

        self.results_scroll = QScrollArea(self)
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.results_scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.results_content = QWidget()
        self.results_layout = QVBoxLayout(self.results_content)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(4)

        self.results_scroll.setWidget(self.results_content)
        root_layout.addWidget(self.results_scroll, 1)

        # Кнопка создания ярлыка
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_create_shortcut = PrimaryButton(
            "Создать ярлык и папку ПИ",
            on_click=self.create_shortcut,
            parent=self
        )
        self.btn_create_shortcut.setMinimumWidth(340)
        self.btn_create_shortcut.setMinimumHeight(42)
        self.btn_create_shortcut.setEnabled(False)
        # 🆕 Иконка link
        link_icon = get_icon_simple("link", color="#FFFFFF", size=18)
        if not link_icon.isNull():
            self.btn_create_shortcut.setIcon(link_icon)
            self.btn_create_shortcut.setIconSize(QSize(18, 18))
        btn_row.addWidget(self.btn_create_shortcut)

        btn_row.addStretch()
        root_layout.addLayout(btn_row)

    # =========================================================
    # ЗАГРУЗКА GM_DATA
    # =========================================================
    def _load_gm_data(self):
        if not os.path.exists(GM_DATA_PATH):
            self.show_error("Ошибка", f"Файл данных не найден:\n{GM_DATA_PATH}")
            return None

        try:
            with open(GM_DATA_PATH, "r", encoding="utf-8") as f:
                gm_data = json.load(f)
        except json.JSONDecodeError as e:
            self.show_error("Ошибка", f"gm_data.json повреждён:\n{e}")
            return None
        except (IOError, OSError) as e:
            self.show_error("Ошибка", f"Не удалось прочитать gm_data.json:\n{e}")
            return None

        if not isinstance(gm_data, list):
            self.show_error("Ошибка", "gm_data.json должен содержать список магазинов.")
            return None

        valid_data = []
        for i, g in enumerate(gm_data):
            if not isinstance(g, dict):
                continue
            if not all(k in g for k in GM_REQUIRED_KEYS):
                log.warning(f"gm_data.json: запись #{i} не содержит обязательные ключи")
                continue
            valid_data.append(g)

        return valid_data

    # =========================================================
    # АВТОКОМПЛИТ
    # =========================================================
    def _attach_completer(self, gm_data):
        if not gm_data:
            return

        items = []
        for g in gm_data:
            code = g.get("Код", "")
            name = g.get("Название", "")
            items.append(f"{code} — {name}")

        model = QStringListModel(items, self.entry_gm)
        completer = QCompleter(model, self.entry_gm)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(15)

        self.entry_gm.setCompleter(completer)

        def _on_activated(text):
            self.entry_gm.setText(text)
            self.search()

        completer.activated.connect(_on_activated)

    # =========================================================
    # ПОИСК
    # =========================================================
    def search(self):
        query = self.entry_gm.text().strip().lower()

        self._clear_results()
        self.selected_gm = None
        self.selected_gm_row = None
        self.btn_create_shortcut.setEnabled(False)

        if not query:
            self.show_status("Введите запрос для поиска",
                             self.COLORS.get('text_dim', '#A0A0A0'))
            return

        gm_data = self._load_gm_data()
        if gm_data is None:
            return

        self._attach_completer(gm_data)

        results = [
            g for g in gm_data
            if query in g["Код"].lower() or query in g["Название"].lower()
        ]

        if not results:
            self.show_status("Ничего не найдено",
                             self.COLORS.get('error', '#FF5252'))
            return

        self.show_status(f"Найдено: {len(results)}",
                         self.COLORS.get('success', '#4CAF50'))

        self._save_last_query(query)

        for g in results:
            self._create_result_row(g)

        self.results_layout.addStretch()

    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _create_result_row(self, gm):
        row = QFrame(self.results_content)
        row.setObjectName("GmRow")
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setFixedHeight(44)
        row.setStyleSheet(f"""
            QFrame#GmRow {{
                background-color: {self.COLORS.get('card', '#222222')};
                border: 1px solid transparent;
                border-radius: 6px;
            }}
            QFrame#GmRow:hover {{
                background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
            }}
            QFrame#GmRow[selected="true"] {{
                background-color: {self.COLORS.get('hover', '#B71C1C')};
                border: 1px solid {self.COLORS.get('button', '#D42626')};
            }}
        """)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 6, 12, 6)
        row_layout.setSpacing(12)

        code_label = QLabel(gm.get("Код", ""), row)
        code_label.setFont(self.FONTS['small'])
        code_label.setFixedWidth(110)
        code_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        row_layout.addWidget(code_label)

        name_label = QLabel(gm.get("Название", ""), row)
        name_label.setFont(self.FONTS['label'])
        name_label.setStyleSheet(
            f"color: {self.COLORS.get('text', '#E0E0E0')};"
        )
        row_layout.addWidget(name_label, 1)

        row.mousePressEvent = lambda e, c=gm["Код"], r=row: self._select(c, r)

        def _on_double_click(e, c=gm["Код"], r=row):
            self._select(c, r)
            self.create_shortcut()

        row.mouseDoubleClickEvent = _on_double_click

        self.results_layout.addWidget(row)

    def _select(self, code, row):
        if self.selected_gm_row is not None:
            try:
                self.selected_gm_row.setProperty("selected", "false")
                self.selected_gm_row.style().unpolish(self.selected_gm_row)
                self.selected_gm_row.style().polish(self.selected_gm_row)
            except Exception:
                pass

        self.selected_gm = code
        self.selected_gm_row = row

        row.setProperty("selected", "true")
        row.style().unpolish(row)
        row.style().polish(row)

        self.btn_create_shortcut.setEnabled(True)

    # =========================================================
    # ПОСЛЕДНИЙ ЗАПРОС
    # =========================================================
    def _restore_last_query(self):
        try:
            last = self._settings.value("gm_last_query", "")
            if last:
                self.entry_gm.setText(last)
        except Exception:
            pass

    def _save_last_query(self, query):
        try:
            self._settings.setValue("gm_last_query", query)
        except Exception:
            pass

    # =========================================================
    # СОЗДАНИЕ ЯРЛЫКА И ПАПКИ ПИ
    # =========================================================
    def _find_desktop(self):
        userprofile = os.environ.get('USERPROFILE', os.path.expanduser('~'))
        candidates = [
            os.path.join(userprofile, 'Desktop'),
            os.path.join(userprofile, 'OneDrive', 'Desktop'),
            os.path.join(userprofile, 'Рабочий стол'),
            os.path.join(userprofile, 'OneDrive', 'Рабочий стол'),
        ]
        for p in candidates:
            if os.path.isdir(p):
                return p
        fallback = os.path.join(userprofile, 'Desktop')
        try:
            os.makedirs(fallback, exist_ok=True)
        except OSError:
            pass
        return fallback

    def _create_pi_folder(self, gm_item):
        base_folder = gm_item.get("Папка", "").strip()
        gm_name = gm_item.get("Название", "").strip()

        if not base_folder:
            return False, "У ГМ не указана сетевая папка"
        if not gm_name:
            return False, "У ГМ не указано название"

        if not os.path.isdir(base_folder):
            return False, (
                f"Сетевая папка недоступна:\n{base_folder}\n\n"
                "Проверьте подключение к сети / доступ к папке."
            )

        date_str = datetime.now().strftime("%d.%m.%Y")
        pi_name = f"ПИ ГМ {gm_name} {date_str}"
        pi_path = os.path.join(base_folder, pi_name)

        if os.path.isdir(pi_path):
            log.info(f"Папка ПИ уже существует: {pi_path}")
            return True, pi_path

        try:
            os.makedirs(pi_path, exist_ok=True)
            log.info(f"Создана папка ПИ: {pi_path}")
        except (OSError, PermissionError) as e:
            return False, f"Не удалось создать папку ПИ:\n{e}"

        for sub in PI_SUBFOLDERS:
            sub_path = os.path.join(pi_path, sub)
            try:
                os.makedirs(sub_path, exist_ok=True)
            except (OSError, PermissionError) as e:
                log.warning(f"Не удалось создать подпапку {sub_path}: {e}")

        return True, pi_path

    def _create_shortcut_win32(self, shortcut_path, target_path):
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = target_path
            shortcut.Save()
            return True
        except Exception as e:
            log.debug(f"win32com shortcut failed: {e}")
            return False

    def _create_shortcut_powershell(self, shortcut_path, target_path):
        ps_shortcut = shortcut_path.replace("'", "''")
        ps_target = target_path.replace("'", "''")

        ps_script = (
            "$WshShell = New-Object -ComObject WScript.Shell; "
            f"$Shortcut = $WshShell.CreateShortcut('{ps_shortcut}'); "
            f"$Shortcut.TargetPath = '{ps_target}'; "
            "$Shortcut.Save(); "
            "Write-Output 'DONE'"
        )

        try:
            result_ps = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True, text=True, encoding="cp866", timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            if result_ps.returncode == 0 and "DONE" in result_ps.stdout:
                return True, ""
            err = result_ps.stderr.strip() or result_ps.stdout.strip() or "Неизвестная ошибка"
            return False, err
        except subprocess.TimeoutExpired:
            return False, "PowerShell не ответил за 15 секунд."
        except (OSError, subprocess.SubprocessError) as e:
            return False, str(e)

    def create_shortcut(self):
        if not self.selected_gm:
            self.show_warning("Сетевые папки", "Сначала выбери ГМ из списка!")
            return

        gm_data = self._load_gm_data()
        if gm_data is None:
            return

        target_gm = None
        for g in gm_data:
            if g["Код"] == self.selected_gm:
                target_gm = g
                break

        if not target_gm:
            self.show_error("Ошибка", "Выбранный ГМ не найден в данных.")
            return

        ok, result = self._create_pi_folder(target_gm)
        if not ok:
            self.show_error("Ошибка создания папки ПИ", result)
            return

        pi_path = result
        user_desktop = self._find_desktop()

        safe_name = target_gm["Название"]
        for char in ['/', '\\', ':', '"', '<', '>', '|', '?', '*']:
            safe_name = safe_name.replace(char, '_')
        if len(safe_name) > MAX_SHORTCUT_NAME_LEN:
            safe_name = safe_name[:MAX_SHORTCUT_NAME_LEN]

        shortcut_path = os.path.join(user_desktop, f"{safe_name}.lnk")
        target = target_gm["Папка"]

        success = self._create_shortcut_win32(shortcut_path, target)
        error_msg = ""

        if not success:
            success, error_msg = self._create_shortcut_powershell(shortcut_path, target)

        if success:
            pi_folder_name = os.path.basename(pi_path)
            self.show_success(
                "Сетевые папки",
                f"Ярлык создан:\n{safe_name}.lnk\n\n"
                f"Папка ПИ: {pi_folder_name}\n"
                f"   (внутри: 1 сутки, 2 сутки, 3 сутки, 4 сутки, Итоговые)\n\n"
                f"Папка на рабочем столе: {user_desktop}"
            )
            log.info(f"Ярлык создан: {shortcut_path}")
            log.info(f"Папка ПИ: {pi_path}")

            try:
                self.app.data_manager.add_action(
                    "Папка ПИ",
                    f"ГМ {target_gm['Код']} — {target_gm['Название']}",
                    "📁"
                )
            except Exception:
                pass
        else:
            self.show_error(
                "Ошибка ярлыка",
                f"Папка ПИ создана, но ярлык не удалось создать:\n\n{error_msg}"
            )
            log.error(f"Shortcut creation failed: {error_msg}")

    # =========================================================
    # СТАТУС
    # =========================================================
    def show_status(self, text, color=None):
        self.status_label.setText(text)
        if color:
            self.status_label.setStyleSheet(f"color: {color};")