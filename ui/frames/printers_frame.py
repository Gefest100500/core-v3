# ui/frames/printers_frame.py
"""
Управление принтерами.

- Вкладка «Установленные»: список + фильтр + переименование
- Вкладка «Установить по IP»: нормализация + пинг + установка

Улучшения по сравнению с CTk-версией:
- QTabWidget вместо CTkTabview
- QListWidget вместо ручного скролла со строками
- QInputDialog.getText вместо CTkInputDialog
- run_on_ui вместо after(0, ...)
- Убран <<Paste>> — Qt принимает Ctrl+V из коробки
- Двойной клик — переименовать
- Контекстное меню — переименовать / по умолчанию
- Enter в поле IP — сразу установить
- Запоминание последнего IP (QSettings)

Правки стиля (v3):
- Сканирование синхронно, CoInitialize в потоках
- Мягкая подсветка выбранной строки
- Убраны все эмодзи, кнопки — SVG-иконки
"""
import os

from PyQt6.QtCore import Qt, QSettings, QSize
from PyQt6.QtGui import QAction, QColor, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTabWidget, QListWidget, QListWidgetItem, QInputDialog,
    QMenu
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, StyledEntry, PrimaryButton, SecondaryButton, style_tabview
)
from ui.components.dialogs import ask_confirm
from ui.icons import get_icon_simple
from utils.logger import log
from utils.network_utils import normalize_ip, is_valid_ip


def _com_initialize():
    """Инициализирует COM в текущем потоке."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
        return True
    except ImportError:
        log.debug("pythoncom недоступен — работаем без CoInitialize")
        return False
    except Exception as e:
        log.debug(f"CoInitialize failed: {e}")
        return False


def _com_uninitialize(initialized):
    """Освобождает COM в текущем потоке."""
    if not initialized:
        return
    try:
        import pythoncom
        pythoncom.CoUninitialize()
    except Exception:
        pass


class PrintersFrame(BaseFrame):

    TITLE = "Управление принтерами"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.selected_printer = None
        self.last_installed_name = None
        self.all_installed = []

        # Менеджер создаём в главном потоке — COM уже инициализирован QApplication
        self.manager = None
        try:
            from core.printer_manager import PrinterManager
            self.manager = PrinterManager()
            log.info("PrintersFrame: PrinterManager создан")
        except Exception as e:
            log.exception("PrintersFrame: не удалось создать PrinterManager")
            self.manager = None

        self._settings = QSettings("SilchenkoAleksey", "CoreV3")

        self._setup_ui()
        self._restore_last_ip()

        # Первое сканирование сразу при открытии вкладки
        self._do_scan()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(10)

        # --- Заголовок (без эмодзи) ---
        title = QLabel("УПРАВЛЕНИЕ ПРИНТЕРАМИ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # --- Верхняя панель: поиск + обновить ---
        top_panel = QHBoxLayout()
        top_panel.setSpacing(10)

        search_lbl = QLabel("Поиск:", self)
        search_lbl.setFont(self.FONTS['small'])
        search_lbl.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        top_panel.addWidget(search_lbl)

        self.entry_search = StyledEntry(
            placeholder="имя принтера или порт",
            parent=self
        )
        self.entry_search.setMinimumWidth(300)
        self.entry_search.textChanged.connect(self._apply_filter)
        top_panel.addWidget(self.entry_search, 1)

        # 🆕 Кнопка "Обновить" с SVG-иконкой
        btn_refresh = PrimaryButton(
            "Обновить список",
            on_click=self._do_scan,
            parent=self
        )
        btn_refresh.setFixedWidth(200)
        btn_refresh.setMinimumHeight(36)
        refresh_icon = get_icon_simple("refresh", color="#FFFFFF", size=16)
        if not refresh_icon.isNull():
            btn_refresh.setIcon(refresh_icon)
            btn_refresh.setIconSize(QSize(16, 16))
        top_panel.addWidget(btn_refresh)

        root_layout.addLayout(top_panel)

        # --- Вкладки ---
        self.tabs = QTabWidget(self)
        style_tabview(
            self.tabs,
            card=self.COLORS.get('card', '#222222'),
            sidebar=self.COLORS.get('sidebar', '#2A2A2A'),
            button=self.COLORS.get('button', '#D42626'),
            hover=self.COLORS.get('hover', '#B71C1C'),
            text=self.COLORS.get('text', '#E0E0E0'),
            text_dim=self.COLORS.get('text_dim', '#A0A0A0'),
        )
        root_layout.addWidget(self.tabs, 1)

        self._build_installed_tab()
        self._build_ip_tab()

    def _build_installed_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.list_installed = QListWidget(tab)
        self.list_installed.setFont(self.FONTS['label'])
        self.list_installed.setStyleSheet(f"""
            QListWidget {{
                background-color: {self.COLORS.get('card', '#222222')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
                padding: 6px;
                font-size: 14px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px 12px;
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
            QListWidget::item:selected:!active {{
                background-color: #333333;
                color: #FFFFFF;
            }}
        """)
        self.list_installed.itemSelectionChanged.connect(self._on_installed_selected)
        self.list_installed.itemDoubleClicked.connect(
            lambda item: self.rename_printer()
        )
        self.list_installed.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_installed.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.list_installed, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        # 🆕 Переименовать — с SVG-иконкой
        btn_rename = SecondaryButton(
            "Переименовать",
            on_click=self.rename_printer,
            parent=tab
        )
        btn_rename.setMinimumWidth(220)
        btn_rename.setMinimumHeight(40)
        pencil_icon = get_icon_simple("pencil", color=self.COLORS.get('text', '#E0E0E0'), size=16)
        if not pencil_icon.isNull():
            btn_rename.setIcon(pencil_icon)
            btn_rename.setIconSize(QSize(16, 16))
        btn_row.addWidget(btn_rename)

        # 🆕 По умолчанию — с SVG-иконкой
        btn_set_default = SecondaryButton(
            "Сделать по умолчанию",
            on_click=self._set_as_default,
            parent=tab
        )
        btn_set_default.setMinimumWidth(220)
        btn_set_default.setMinimumHeight(40)
        star_icon = get_icon_simple("star", color=self.COLORS.get('text', '#E0E0E0'), size=16)
        if not star_icon.isNull():
            btn_set_default.setIcon(star_icon)
            btn_set_default.setIconSize(QSize(16, 16))
        btn_row.addWidget(btn_set_default)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tabs.addTab(tab, "Установленные")

    def _build_ip_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        card = create_card(tab)

        card_title = QLabel("Установить принтер по IP-адресу", card)
        card_title.setFont(self.FONTS['subtitle'])
        card.layout().addWidget(card_title)

        card_hint = QLabel(
            "Введите IP-адрес принтера и нажмите «Установить».",
            card
        )
        card_hint.setFont(self.FONTS['small'])
        card_hint.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        card.layout().addWidget(card_hint)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        ip_lbl = QLabel("IP-адрес:", card)
        ip_lbl.setFont(self.FONTS['label'])
        ip_lbl.setFixedWidth(120)
        input_row.addWidget(ip_lbl)

        self.entry_ip = StyledEntry(
            placeholder="10.3.2.94",
            parent=card
        )
        self.entry_ip.setMinimumWidth(400)
        self.entry_ip.setMinimumHeight(40)
        self.entry_ip.returnPressed.connect(self.add_printer_by_ip)
        self.entry_ip.editingFinished.connect(self._normalize_entry_ip)
        input_row.addWidget(self.entry_ip, 1)

        card.layout().addLayout(input_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # 🆕 Установить — с SVG-иконкой
        btn_install = PrimaryButton(
            "Установить принтер",
            on_click=self.add_printer_by_ip,
            parent=card
        )
        btn_install.setMinimumWidth(280)
        btn_install.setMinimumHeight(46)
        download_icon = get_icon_simple("download", color="#FFFFFF", size=18)
        if not download_icon.isNull():
            btn_install.setIcon(download_icon)
            btn_install.setIconSize(QSize(18, 18))
        btn_row.addWidget(btn_install)

        btn_ping = SecondaryButton(
            "Проверить доступность",
            on_click=self.ping_ip,
            parent=card
        )
        btn_ping.setMinimumWidth(220)
        btn_ping.setMinimumHeight(46)
        btn_row.addWidget(btn_ping)

        btn_row.addStretch()
        card.layout().addLayout(btn_row)

        self.ip_status = QLabel("", card)
        self.ip_status.setFont(self.FONTS['label'])
        self.ip_status.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.ip_status.setWordWrap(True)
        card.layout().addWidget(self.ip_status)

        layout.addWidget(card)
        layout.addStretch()

        self.tabs.addTab(tab, "Установить по IP")

    # =========================================================
    # РАБОТА С IP
    # =========================================================
    def _restore_last_ip(self):
        try:
            last = self._settings.value("printers_last_ip", "")
            if last:
                self.entry_ip.setText(last)
        except Exception:
            pass

    def _save_last_ip(self, ip):
        try:
            self._settings.setValue("printers_last_ip", ip)
        except Exception:
            pass

    def _normalize_entry_ip(self):
        text = self.entry_ip.text().strip()
        if not text:
            return

        normalized = normalize_ip(text)
        if normalized and normalized != text:
            self.entry_ip.setText(normalized)

    # =========================================================
    # ФИЛЬТРАЦИЯ
    # =========================================================
    def _apply_filter(self):
        if not self.all_installed:
            self._render_installed([], filter_active=False)
            return

        query = self.entry_search.text().strip().lower()
        if not query:
            filtered = self.all_installed
        else:
            filtered = [
                p for p in self.all_installed
                if query in p.get("name", "").lower()
                or query in p.get("port", "").lower()
            ]

        self._render_installed(filtered, filter_active=bool(query))

    # =========================================================
    # СКАНИРОВАНИЕ — СИНХРОННОЕ
    # =========================================================
    def _do_scan(self):
        log.info("PrintersFrame: сканирование...")
        self.set_status("Поиск установленных принтеров...")

        if self.manager is None:
            log.error("PrintersFrame: manager == None")
            self.show_error("Ошибка", "PrinterManager не инициализирован.")
            self.set_status("Ошибка")
            return

        try:
            data = self.manager.get_installed_printers()
            log.info(f"PrintersFrame: получено {len(data) if isinstance(data, list) else '?'} принтеров")
            self._populate_installed(data)
            self.set_status("Готов")
        except Exception as e:
            log.exception("PrintersFrame: ошибка сканирования")
            self.show_error("Ошибка", str(e))
            self.set_status("Ошибка")

    def _populate_installed(self, data):
        log.info(f"PrintersFrame: _populate_installed, type={type(data).__name__}")

        if isinstance(data, dict) and data.get("error"):
            self.show_error("Ошибка сканирования", data["error"])
            return

        if not isinstance(data, list):
            self.show_error("Ошибка", "Некорректный формат данных.")
            return

        self.all_installed = data
        self._apply_filter()

    def _render_installed(self, data, filter_active=False):
        self.list_installed.clear()
        self.selected_printer = None

        if not data:
            item = QListWidgetItem(
                "Ничего не найдено по фильтру."
                if filter_active
                else "Принтеры не найдены."
            )
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setForeground(QColor(self.COLORS.get('text_dim', '#A0A0A0')))
            self.list_installed.addItem(item)
            return

        if self.last_installed_name:
            data = sorted(data, key=lambda x: (
                0 if x.get("name") == self.last_installed_name else 1,
                x.get("name", "").lower()
            ))
        else:
            data = sorted(data, key=lambda x: x.get("name", "").lower())

        header = f"Всего: {len(data)}" if not filter_active else f"Найдено: {len(data)}"
        header_item = QListWidgetItem(header)
        header_item.setFlags(Qt.ItemFlag.NoItemFlags)
        header_item.setForeground(QColor(self.COLORS.get('text_dim', '#A0A0A0')))
        self.list_installed.addItem(header_item)

        if self.last_installed_name and not filter_active:
            found = any(p.get("name") == self.last_installed_name for p in data)
            if found:
                info_item = QListWidgetItem(
                    f"Только что установлен:  {self.last_installed_name}"
                )
                info_item.setFlags(Qt.ItemFlag.NoItemFlags)
                info_item.setForeground(QColor(self.COLORS.get('success', '#4CAF50')))
                self.list_installed.addItem(info_item)

        for p in data:
            if not isinstance(p, dict) or "name" not in p:
                continue

            name = p.get("name", "?")
            port = p.get("port", "—")
            status = p.get("status", "—")

            is_last = (self.last_installed_name == name)
            status_ok = (status == "Готов")

            text = f"{name}   •   {port}   •   {status}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, name)

            if is_last:
                item.setForeground(QColor(self.COLORS.get('success', '#4CAF50')))
            elif not status_ok:
                item.setForeground(QColor(self.COLORS.get('error', '#FF5252')))

            self.list_installed.addItem(item)

    # =========================================================
    # ВЫБОР ПРИНТЕРА
    # =========================================================
    def _on_installed_selected(self):
        items = self.list_installed.selectedItems()
        if not items:
            self.selected_printer = None
            return

        name = items[0].data(Qt.ItemDataRole.UserRole)
        self.selected_printer = name

    def _show_context_menu(self, pos):
        item = self.list_installed.itemAt(pos)
        if not item:
            return

        name = item.data(Qt.ItemDataRole.UserRole)
        if not name:
            return

        self.selected_printer = name

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {self.COLORS.get('card', '#222222')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {self.COLORS.get('button', '#D42626')};
                color: white;
            }}
        """)

        act_rename = QAction("Переименовать", self)
        act_rename.triggered.connect(self.rename_printer)
        menu.addAction(act_rename)

        act_default = QAction("Сделать по умолчанию", self)
        act_default.triggered.connect(self._set_as_default)
        menu.addAction(act_default)

        menu.exec(self.list_installed.mapToGlobal(pos))

    # =========================================================
    # УСТАНОВКА ПО IP
    # =========================================================
    def add_printer_by_ip(self):
        self._normalize_entry_ip()

        ip_text = self.entry_ip.text().strip()

        if not ip_text:
            self._set_ip_status("Введите IP-адрес", self.COLORS.get('error', '#FF5252'))
            return

        normalized = normalize_ip(ip_text)

        if not normalized or not is_valid_ip(normalized):
            self._set_ip_status(
                f"Не найден IP-адрес в тексте:\n{ip_text[:100]}",
                self.COLORS.get('error', '#FF5252')
            )
            return

        self._save_last_ip(normalized)

        self._set_ip_status(
            f"Установка принтера по адресу {normalized}...\n"
            f"Это может занять 10-30 секунд.",
            "#FFD700"
        )
        self.set_status(f"Установка по {normalized}...")

        def do_add():
            com_initialized = _com_initialize()
            try:
                log.info(f"PrintersFrame: установка по IP {normalized}...")
                from core.printer_manager import PrinterManager
                success, result = PrinterManager().add_printer_by_ip(normalized, "")
                log.info(f"PrintersFrame: установка завершена, success={success}")
                self.run_on_ui(self._on_ip_add_done, success, result, normalized)
            except Exception as e:
                log.exception("Ошибка установки по IP")
                self.run_on_ui(self.show_error, "Ошибка", str(e))
                self.run_on_ui(self.set_status, "Ошибка установки")
            finally:
                _com_uninitialize(com_initialized)

        self.run_in_thread(do_add)

    def _on_ip_add_done(self, success, result, ip):
        if success and isinstance(result, dict):
            real_name = result.get("name", "")
            self.last_installed_name = real_name

            already = result.get("already_existed", False)

            if already:
                msg = f"Принтер уже был установлен:\n{real_name}"
                status_text = f"Уже установлен: {real_name}"
                status_color = "#FFD700"
            else:
                msg = f"Принтер установлен:\n{real_name}"
                status_text = f"Установлен: {real_name}"
                status_color = self.COLORS.get('success', '#4CAF50')

            self._set_ip_status(
                f"{status_text}\n\nОтмечен в списке установленных.",
                status_color
            )
            self.set_status(status_text)

            self._do_scan()
            self.tabs.setCurrentIndex(0)

            self.show_success(
                "Готово",
                f"{msg}\n\nНайдите его вверху списка «Установленные»."
            )
        else:
            err = result if isinstance(result, str) else "Неизвестная ошибка"
            self._set_ip_status(
                f"Ошибка установки:\n{err}",
                self.COLORS.get('error', '#FF5252')
            )
            self.show_error("Ошибка установки", err)
            self.set_status("Ошибка установки")

    def ping_ip(self):
        self._normalize_entry_ip()

        ip_text = self.entry_ip.text().strip()
        if not ip_text:
            self._set_ip_status("Введите IP-адрес", self.COLORS.get('error', '#FF5252'))
            return

        normalized = normalize_ip(ip_text)
        if not normalized or not is_valid_ip(normalized):
            self._set_ip_status(
                f"Не найден IP-адрес: {ip_text[:100]}",
                self.COLORS.get('error', '#FF5252')
            )
            return

        self._save_last_ip(normalized)
        self._set_ip_status(
            f"Проверка доступности {normalized}...",
            "#FFD700"
        )

        def do_ping():
            com_initialized = _com_initialize()
            try:
                log.info(f"PrintersFrame: пинг {normalized}...")
                from core.printer_manager import PrinterManager
                ok, info = PrinterManager().ping_host(normalized)
                log.info(f"PrintersFrame: пинг завершён, ok={ok}")
                self.run_on_ui(self._on_ping_done, ok, info, normalized)
            except Exception as e:
                log.exception("Ошибка пинга")
                err = str(e)
                self.run_on_ui(
                    self._set_ip_status,
                    f"Ошибка: {err}",
                    self.COLORS.get('error', '#FF5252')
                )
            finally:
                _com_uninitialize(com_initialized)

        self.run_in_thread(do_ping)

    def _on_ping_done(self, ok, info, ip):
        if ok:
            self._set_ip_status(
                f"{ip} доступен — {info}\n\nМожно устанавливать принтер.",
                self.COLORS.get('success', '#4CAF50')
            )
        else:
            self._set_ip_status(
                f"{ip} недоступен: {info}\n\n"
                "Проверьте IP, включён ли принтер, подключён ли к сети.",
                self.COLORS.get('error', '#FF5252')
            )

    def _set_ip_status(self, text, color=None):
        self.ip_status.setText(text)
        if color:
            self.ip_status.setStyleSheet(f"color: {color};")

    # =========================================================
    # ПЕРЕИМЕНОВАНИЕ
    # =========================================================
    def rename_printer(self):
        if not self.selected_printer:
            self.show_warning("Принтеры", "Выберите принтер из вкладки «Установленные»!")
            return

        new_name, ok = QInputDialog.getText(
            self,
            "Переименовать",
            f"Введите новое имя для:\n\n    {self.selected_printer}"
        )
        if not ok or not new_name:
            return

        new_name = new_name.strip()
        if not new_name or new_name == self.selected_printer:
            return

        if len(new_name) > 100:
            self.show_error("Ошибка", "Имя принтера не может быть длиннее 100 символов.")
            return

        old_name = self.selected_printer

        def do_rename():
            com_initialized = _com_initialize()
            try:
                log.info(f"PrintersFrame: переименование {old_name} → {new_name}...")
                from core.printer_manager import PrinterManager
                success = PrinterManager().rename_printer(old_name, new_name)
                log.info(f"PrintersFrame: переименование завершено, success={success}")
                self.run_on_ui(self._on_manual_rename_done, success, new_name, old_name)
            except Exception as e:
                log.exception("Ошибка переименования")
                self.run_on_ui(self.show_error, "Ошибка", str(e))
            finally:
                _com_uninitialize(com_initialized)

        self.run_in_thread(do_rename)

    def _on_manual_rename_done(self, success, new_name, old_name):
        if success:
            if old_name == self.last_installed_name:
                self.last_installed_name = new_name

            self.show_success("Успех", f"Переименован в: {new_name}")
            self._do_scan()
        else:
            self.show_error(
                "Ошибка",
                f"Не удалось переименовать.\n\n"
                f"Возможно, нет прав администратора.\n\n"
                f"Попробуйте:\n"
                f"• Запустить программу от имени администратора\n"
                f"• Или переименовать вручную:\n"
                f"   Rename-Printer -Name \"...\" -NewName \"{new_name}\""
            )

    # =========================================================
    # ПО УМОЛЧАНИЮ
    # =========================================================
    def _set_as_default(self):
        if not self.selected_printer:
            self.show_warning("Принтеры", "Выберите принтер из списка!")
            return

        selected = self.selected_printer

        def do_set():
            com_initialized = _com_initialize()
            try:
                log.info(f"PrintersFrame: установка по умолчанию {selected}...")
                from core.printer_manager import PrinterManager
                ok = PrinterManager().set_default(selected)
                log.info(f"PrintersFrame: установка по умолчанию завершена, ok={ok}")
                self.run_on_ui(self._on_set_default_done, ok, selected)
            except Exception as e:
                log.exception("Ошибка установки по умолчанию")
                self.run_on_ui(self.show_error, "Ошибка", str(e))
            finally:
                _com_uninitialize(com_initialized)

        self.run_in_thread(do_set)

    def _on_set_default_done(self, ok, selected):
        if ok:
            self.show_success(
                "Успех",
                f"Принтер по умолчанию:\n{selected}"
            )
            self._do_scan()
        else:
            self.show_error(
                "Ошибка",
                "Не удалось установить принтер по умолчанию.\n\n"
                "Возможно, нет прав администратора."
            )

    # =========================================================
    # REFRESH
    # =========================================================
    def refresh(self):
        if not self.all_installed:
            self._do_scan()