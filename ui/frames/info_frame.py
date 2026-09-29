# ui/frames/info_frame.py
"""
Информация.

- Инструкция по работе с программой
- Сведения о программе и разработчике
- Кнопка создания дашборда (если модуль доступен)

Улучшения по сравнению с CTk-версией:
- QTabWidget вместо CTkTabview
- QTextEdit вместо CTkTextbox
- Кнопка "Копировать инструкцию"
- Дашборд: если модуль недоступен — кнопка отключена
- run_on_ui вместо after(0, ...)

Правки стиля:
- Убраны все эмодзи
- Кнопки — SVG-иконки
"""
import os

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTabWidget, QTextEdit, QPushButton, QApplication
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton, style_tabview
)
from ui.icons import get_icon_simple
from utils.logger import log


APP_VERSION = "Core v3.0"


INSTRUCTION_TEXT = (
    "ПОДГОТОВКА ФАЙЛОВ ДЛЯ АВТОМАТИЧЕСКОГО АНАЛИЗА КВАНТОВ\n\n"
    "1. Скачайте шаблон по квантам из АСУС и переименуйте его в «Кванты».\n"
    "   Удалять позиции не требуется — программа автоматически исключит строки с суммой менее 1000 руб.\n"
    "   Затем нажмите кнопку «Выбрать Кванты».\n\n"
    "2. Для подготовки файла с кодами товаров нажмите кнопку «Подготовить файл ТП».\n"
    "   Программа сформирует текстовый файл с кодами товаров.\n"
    "   Найти его можно через кнопку «Открыть папку с результатом».\n\n"
    "3. Выгрузите отчёт «Реестр товарных позиций» из Тандер Склада.\n"
    "   Для этого в ТС перейдите: Отчёты → Отчётность → Реестр товарных позиций.\n"
    "   В операциях выберите все приходы и инвентаризации — должно получиться 44 пункта.\n"
    "   Отметьте товары из файла ТП, созданного в пункте 2.\n\n"
    "4. Дождитесь завершения формирования отчёта, экспортируйте его в Excel и назовите файл «РТП».\n"
    "   После этого нажмите кнопку «Выбрать РТП».\n\n"
    "5. Нажмите «Запустить анализ».\n"
    "   По завершении будут сформированы два файла для ревизоров.\n\n\n"
    "ПОДГОТОВКА ФАЙЛОВ ДЛЯ СБОРКИ «ПРОВЕРКА 10% ПАЛЛЕТЫ»\n\n"
    "1. Экспортируйте все посчитанные паллеты в Excel.\n"
    "   Назовите файлы: 1, 2, 3, 4 и так далее.\n"
    "   В программе укажите путь к папке с этими файлами.\n\n"
    "2. Нажмите «Собрать Паллеты». Готово.\n\n\n"
    "ПОДГОТОВКА ФАЙЛОВ ДЛЯ ОС И МБП\n\n"
    "1. Извлеките архив с описями.\n\n"
    "2. Нажмите кнопку «Выбрать файлы ОС» и отметьте ведомости из папок:\n"
    "   «Более 100 тыс» и «Менее 100 тыс».\n\n"
    "3. Нажмите кнопку «Выбрать файлы МБП» и отметьте ведомости из папок:\n"
    "   «Забаланс» и «МБП».\n\n"
    "4. При включённом тумблере «Убрать лишнее» из готовых ведомостей будут удалены строки,\n"
    "   содержащие спецодежду, средства индивидуальной защиты и другие вспомогательные позиции.\n\n"
    "5. Кнопка «Открыть папку с результатом» открывает папку с готовыми файлами.\n\n\n"
    "РАЗДЕЛ «СЕТЕВЫЕ ПАПКИ»\n\n"
    "Позволяет быстро создать ярлык на сетевую папку выбранного ГМ.\n"
    "Поиск осуществляется по коду ГМ или названию.\n"
    "Ярлык создаётся на рабочем столе пользователя.\n\n\n"
    "РАЗДЕЛ «СТАНДАРТНЫЕ КОММЕНТАРИИ»\n\n"
    "Готовые шаблоны комментариев для отчётов.\n"
    "Заполните поля — текст автоматически соберётся и его можно скопировать.\n"
    "Название ГМ подставляется из активной инвентаризации.\n\n\n"
    "РАЗДЕЛ «РАССТОЯНИЕ МЕЖДУ ГМ»\n\n"
    "Расчёт расстояния между двумя магазинами.\n"
    "Можно вводить название ГМ или адрес.\n"
    "Показывает расстояние по прямой и оценку по дорогам."
)


ABOUT_TEXT = (
    f"{APP_VERSION}\n"
    "Корпоративный аудит\n\n"
    "Разработчик: Silchenko Aleksey\n\n"
    "Модули:\n"
    "• Кванты — автоматический анализ квантов\n"
    "• Паллеты — анализ паллет\n"
    "• ОС и МБП — сборка свода основных средств и МБП\n"
    "• Брак/Утиль — проверка актов списания\n"
    "• Нарушения — работа с шаблоном нарушений\n"
    "• Принтеры — управление принтерами\n"
    "• Сетевые папки — поиск и создание ярлыков ГМ\n"
    "• Комментарии — готовые шаблоны текстов\n"
    "• Расстояние — расчёт расстояний между ГМ"
)


class InfoFrame(BaseFrame):

    TITLE = "Информация"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self._dashboard_available = self._check_dashboard_available()
        self._setup_ui()

    # =========================================================
    # ПРОВЕРКА МОДУЛЯ ДАШБОРДА
    # =========================================================
    def _check_dashboard_available(self):
        try:
            import importlib
            importlib.import_module("core.dashboard_builder")
            return True
        except ImportError:
            log.info("Модуль core.dashboard_builder недоступен — кнопка дашборда отключена")
            return False

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(10)

        # Заголовок (без эмодзи)
        title = QLabel("ИНФОРМАЦИЯ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # Вкладки
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

        self._build_instruction_tab()
        self._build_about_tab()

    # =========================================================
    # ВКЛАДКА «ИНСТРУКЦИЯ»
    # =========================================================
    def _build_instruction_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.instr_text = QTextEdit(tab)
        self.instr_text.setReadOnly(True)
        self.instr_text.setFont(self.FONTS['label'])
        self.instr_text.setPlainText(INSTRUCTION_TEXT)
        self.instr_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.COLORS.get('card', '#222222')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 2px solid {self.COLORS.get('border', '#333333')};
                border-radius: 12px;
                padding: 15px;
                selection-background-color: {self.COLORS.get('button', '#D42626')};
                selection-color: white;
            }}
        """)
        layout.addWidget(self.instr_text, 1)

        # Кнопка «Копировать инструкцию» с SVG
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_copy = SecondaryButton(
            "Копировать инструкцию",
            on_click=self._copy_instruction,
            parent=tab
        )
        btn_copy.setMinimumWidth(260)
        btn_copy.setMinimumHeight(38)
        copy_icon = get_icon_simple("copy", color=self.COLORS.get('text', '#E0E0E0'), size=16)
        if not copy_icon.isNull():
            btn_copy.setIcon(copy_icon)
            btn_copy.setIconSize(QSize(16, 16))
        btn_row.addWidget(btn_copy)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tabs.addTab(tab, "Инструкция")

    def _copy_instruction(self):
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(INSTRUCTION_TEXT)

            if clipboard.text() == INSTRUCTION_TEXT:
                self.show_success(
                    "Скопировано",
                    "Инструкция скопирована в буфер обмена.\n\n"
                    "Можно вставить в письмо или сообщение."
                )
            else:
                raise RuntimeError("Буфер не принял текст")
        except Exception as e:
            log.error(f"Ошибка копирования инструкции: {e}")
            self.show_error("Ошибка", f"Не удалось скопировать:\n{e}")

    # =========================================================
    # ВКЛАДКА «О ПРОГРАММЕ»
    # =========================================================
    def _build_about_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        about_card = create_card(tab)
        about_card.setMaximumWidth(700)

        version_label = QLabel(APP_VERSION, about_card)
        version_label.setFont(self.FONTS['title'])
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_card.layout().addWidget(version_label)

        subtitle = QLabel("Корпоративный аудит", about_card)
        subtitle.setFont(self.FONTS['subtitle'])
        subtitle.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_card.layout().addWidget(subtitle)

        dev_label = QLabel("Разработчик: Silchenko Aleksey", about_card)
        dev_label.setFont(self.FONTS['label'])
        dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_card.layout().addWidget(dev_label)

        modules_label = QLabel(ABOUT_TEXT, about_card)
        modules_label.setFont(self.FONTS['label'])
        modules_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        modules_label.setWordWrap(True)
        about_card.layout().addWidget(modules_label)

        layout.addWidget(about_card)

        # Кнопка «Создать дашборд» с SVG
        self.btn_dashboard = PrimaryButton(
            "Создать дашборд",
            on_click=self.start_dashboard,
            parent=tab
        )
        self.btn_dashboard.setMinimumWidth(300)
        self.btn_dashboard.setMinimumHeight(45)
        dashboard_icon = get_icon_simple("kv", color="#FFFFFF", size=18)
        if not dashboard_icon.isNull():
            self.btn_dashboard.setIcon(dashboard_icon)
            self.btn_dashboard.setIconSize(QSize(18, 18))

        if not self._dashboard_available:
            self.btn_dashboard.setEnabled(False)
            self.btn_dashboard.setToolTip(
                "Модуль core.dashboard_builder не установлен"
            )

        layout.addWidget(
            self.btn_dashboard,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        layout.addStretch()

        self.tabs.addTab(tab, "О программе")

    # =========================================================
    # ДАШБОРД
    # =========================================================
    def start_dashboard(self):
        if not self._dashboard_available:
            self.show_warning(
                "Недоступно",
                "Модуль core.dashboard_builder не установлен.\n\n"
                "Обратитесь к разработчику."
            )
            return

        self.btn_dashboard.setEnabled(False)

        if hasattr(self.app, "start_progress"):
            self.app.start_progress("Создание дашборда...")

        self.run_in_thread(self._run_dashboard)

    def _run_dashboard(self):
        try:
            from core.dashboard_builder import DashboardBuilder
            from config import FOLDERS

            builder = DashboardBuilder(FOLDERS["info"])
            result = builder.build_dashboard()

            self.run_on_ui(self._on_dashboard_finish, result)

        except ImportError as e:
            log.error(f"Модуль дашборда недоступен: {e}")
            self.run_on_ui(
                self.show_error,
                "Ошибка",
                f"Модуль дашборда недоступен:\n{e}"
            )
            self.run_on_ui(self._reset_dashboard_button)

        except (FileNotFoundError, PermissionError) as e:
            log.error(f"Файловая ошибка дашборда: {e}")
            self.run_on_ui(self.show_error, "Файловая ошибка", str(e))
            self.run_on_ui(self._reset_dashboard_button)

        except Exception as e:
            log.exception("Непредвиденная ошибка создания дашборда.")
            self.run_on_ui(self.show_error, "Ошибка", str(e))
            self.run_on_ui(self._reset_dashboard_button)

    def _reset_dashboard_button(self):
        self.btn_dashboard.setEnabled(True)

    def _on_dashboard_finish(self, res):
        self.btn_dashboard.setEnabled(True)

        if hasattr(self.app, "finish_progress"):
            self.app.finish_progress(True, "Дашборд создан")

        if res and res.get("success"):
            self.show_success("Успех", "Дашборд создан!")
            self.open_folder("info")
        else:
            self.show_error("Ошибка", "Не удалось создать дашборд.")