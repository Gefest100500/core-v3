# ui/frames/info_frame.py
"""
Информация.

- Слева плоский список утилит (QListWidget) с иконками.
- Над списком — поиск.
- Справа — HTML-инструкция выбранной утилиты (крупный шрифт).
- Вкладка «О программе»: классическая карточка с текстом.

ИЗМЕНЕНИЯ:
- Исправлены все имена иконок (включая Web -> globe).
- Увеличен шрифт в правой части.
- Раздел «Web» заменён на «АСУС» (pywv2 / WebView2, только АСУС).
- В «О программе» добавлены калькулятор и блокнот.
"""
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTabWidget, QTextBrowser, QApplication,
    QListWidget, QListWidgetItem, QSplitter
)

from core import __version__
from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, SecondaryButton, style_tabview, StyledEntry
)
from ui.icons import get_icon, get_icon_simple
from utils.logger import log

APP_VERSION = f"Core v{__version__}"

# =========================================================
# ДАННЫЕ О МОДУЛЯХ И ИНСТРУКЦИИ
# =========================================================
INSTRUCTIONS = {
    "kv": {
        "name": "Кванты",
        "icon": "kv",
        "html": """
            <h2>Кванты</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Автоматический анализ квантов: находит позиции с потерями 
                ≥ 1000 руб., применяет жёсткие и мягкие правила, распределяет 
                позиции между двумя ревизорами.</p>
            </div>
            <div class="section">
                <h3>ПОДГОТОВКА ФАЙЛОВ</h3>
                <ol>
                    <li>Скачайте шаблон по квантам из АСУС и переименуйте его 
                    в «Кванты». Удалять позиции не требуется — программа сама 
                    исключит строки с суммой менее 1000 руб. Затем нажмите «Выбрать Кванты».</li>
                    <li>Нажмите «Подготовить файл ТП» — программа сформирует 
                    текстовый файл с кодами товаров. Найти его можно через 
                    кнопку «Открыть папку с результатом».</li>
                    <li>Выгрузите отчёт «Реестр товарных позиций» из Тандер Склада:
                    Отчёты → Отчётность → Реестр товарных позиций.
                    В операциях выберите все приходы и инвентаризации —
                    должно получиться 44 пункта. Отметьте товары из файла ТП.</li>
                    <li>Дождитесь формирования отчёта, экспортируйте в Excel
                    и назовите файл «РТП». Нажмите «Выбрать РТП».</li>
                    <li>Нажмите «Запустить анализ». По завершении будут
                    сформированы два файла для ревизоров.</li>
                </ol>
            </div>
        """
    },
    "pal": {
        "name": "Паллеты",
        "icon": "pal",
        "html": """
            <h2>Паллеты</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Собирает свод из посменных отчётов по паллетам, считает
                отклонения и сумму.</p>
            </div>
            <div class="section">
                <h3>ПОДГОТОВКА ФАЙЛОВ</h3>
                <ol>
                    <li>Экспортируйте все посчитанные паллеты в Excel.
                    Назовите файлы: 1, 2, 3, 4 и так далее.
                    В программе укажите путь к папке с этими файлами.</li>
                    <li>Нажмите «Собрать Паллеты». Готово.</li>
                </ol>
            </div>
        """
    },
    "os_mbp": {
        "name": "ОС и МБП",
        "icon": "os_mbp",
        "html": """
            <h2>ОС и МБП</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Парсит инвентаризационные описи (ИНВ-1), собирает свод
                основных средств и МБП. Опция «Убрать лишнее» фильтрует
                спецодежду, СИЗ и вспомогательные позиции.</p>
            </div>
            <div class="section">
                <h3>ПОДГОТОВКА ФАЙЛОВ</h3>
                <ol>
                    <li>Извлеките архив с описями.</li>
                    <li>Нажмите «Выбрать файлы ОС» и отметьте ведомости из папок:
                    «Более 100 тыс» и «Менее 100 тыс».</li>
                    <li>Нажмите «Выбрать файлы МБП» и отметьте ведомости из папок:
                    «Забаланс» и «МБП».</li>
                    <li>При включённом тумблере «Убрать лишнее» из готовых
                    ведомостей будут удалены строки со спецодеждой, СИЗ
                    и другими вспомогательными позициями.</li>
                    <li>Кнопка «Открыть папку с результатом» открывает папку
                    с готовыми файлами.</li>
                </ol>
            </div>
        """
    },
    "brak_util": {
        "name": "Брак/Утиль",
        "icon": "brak_util",
        "html": """
            <h2>Брак/Утиль</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Сверяет два файла по номеру документа, подсвечивает
                расхождения красным, архивирует результат в .zip.</p>
            </div>
            <div class="section">
                <h3>ПОДГОТОВКА ФАЙЛОВ</h3>
                <ol>
                    <li>Подготовьте файл «Выборочная проверка актов списания утиля».</li>
                    <li>Подготовьте файл «Операции списания».</li>
                    <li>Допуск по сумме настраивается в config.json
                    (BRAK_UTIL_TOLERANCE).</li>
                    <li>Выберите оба файла и запустите сверку.</li>
                </ol>
            </div>
        """
    },
    "violations": {
        "name": "Анализ Нарушений",
        "icon": "violations",
        "html": """
            <h2>Анализ Нарушений</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Анализ нарушений БП по РТП (Трассировщик).<br>
                Вход — файл с кодами + РТП (без Квантов).<br>
                Отключены: Пересорт, Хищение, Местный поставщик.<br>
                Оставлены: Зеркалка, Коробочный, Обычная приемка.<br>
                Вывод: Наименование, Группа, Знак, Причина + список
                инвентаризаций (Дата: Кол-во).</p>
            </div>
            <div class="section">
                <h3>ПОДГОТОВКА ФАЙЛОВ</h3>
                <p>Подробности будут дописаны позже.</p>
            </div>
        """
    },
    "inventory": {
        "name": "Инвентаризация",
        "icon": "inventory",
        "html": """
            <h2>Инвентаризация</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Ведёт чек-листы инвентаризации по дням и сменам.
                Старт: ГМ, вариант (А–Ж), дата начала. Дата окончания
                рассчитывается автоматически. Автосохранение при переключении
                вкладки и при закрытии. При завершении создаётся структура
                папок в Готовые/Инвентаризации/{gm_code}_{start_date}/.</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Нажмите «Новая инвентаризация».</li>
                    <li>Выберите ГМ, вариант и дату начала.</li>
                    <li>Отмечайте пункты чек-листа по дням и сменам.</li>
                    <li>По завершении — «Завершить с архивацией».</li>
                </ol>
            </div>
        """
    },
    "timesheet": {
        "name": "Табель",
        "icon": "timesheet",
        "html": """
            <h2>Табель</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Ввод рабочих часов ревизора: К (командировка), Д (дорога),
                Н (ночь). Календарь на месяц, воскресенье подсвечено красным.
                Автосохранение при вводе. Строка для АСУЗ + копирование.
                Сводка по 4 неделям (только К), итого К, Д, Н.</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Выберите день в календаре.</li>
                    <li>Введите К, Д, Н.</li>
                    <li>Скопируйте строку для АСУЗ кнопкой «Копировать».</li>
                </ol>
            </div>
        """
    },
    "dashboard": {
        "name": "Дашборд",
        "icon": "chart",
        "html": """
            <h2>Дашборд</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Аналитика по письмам инвентаризации из Outlook.
                Сводка, динамика (график), ТОП-3 зоны, аналитические зоны,
                прочие мероприятия, часы ревизоров.</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Нажмите «Забрать информацию» — сбор писем из Outlook.</li>
                    <li>Выберите ГМ (автокомплит).</li>
                    <li>«Сохранить как PNG» — экспорт дашборда.</li>
                </ol>
                <p><em>Встроенный режим: при открытии из Архива кнопка «Забрать
                информацию» скрыта.</em></p>
            </div>
        """
    },
    "archive": {
        "name": "Архив инвентаризаций",
        "icon": "archive",
        "html": """
            <h2>Архив инвентаризаций</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Список завершённых инвентаризаций. Карточка записи: ГМ,
                название, вариант, даты, итоговая сумма. Клик по карточке
                открывает встроенный дашборд по этому ГМ. Записи не удаляются.</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Откройте вкладку — список подгружается автоматически.</li>
                    <li>Клик по карточке — дашборд по ГМ.</li>
                    <li>«← Назад в архив» — возврат к списку.</li>
                </ol>
            </div>
        """
    },
    "comments": {
        "name": "Стандартные комментарии",
        "icon": "comments",
        "html": """
            <h2>Стандартные комментарии</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Готовые шаблоны комментариев для отчётов. Заполните поля —
                текст автоматически соберётся, его можно скопировать.
                Название ГМ подставляется из активной инвентаризации.</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Выберите ГМ (автокомплит по коду или названию).</li>
                    <li>Заполните поля (сумма, зона и т.д.).</li>
                    <li>Скопируйте готовый текст.</li>
                </ol>
            </div>
        """
    },
    "ai": {
        "name": "AI — «Стажёр»",
        "icon": "ai",
        "html": """
            <h2>AI — «Стажёр»</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Разметка объяснений решений правил от Shadow Engine:
                «Согласен» / «Не согласен». Пагинация по 100 записей,
                фильтры (только неразмеченные, порог уверенности, поиск),
                детали строки, массовая разметка, экспорт feedback,
                очистка базы с архивацией.</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Выберите запись в таблице — детали справа.</li>
                    <li>Нажмите «Согласен» или «Не согласен».</li>
                    <li>«Экспорт» — выгрузить feedback в JSONL.</li>
                </ol>
            </div>
        """
    },
    "printers": {
        "name": "Принтеры",
        "icon": "printers",
        "html": """
            <h2>Принтеры</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Список установленных принтеров, установка по IP,
                переименование, установка по умолчанию, проверка доступности.</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Список принтеров подгружается автоматически.</li>
                    <li>Для установки по IP введите адрес и нажмите «Установить».</li>
                    <li>Двойной клик по принтеру — переименовать.</li>
                    <li>Контекстное меню — дополнительные действия.</li>
                </ol>
            </div>
        """
    },
    "gm": {
        "name": "Сетевые папки ГМ",
        "icon": "gm",
        "html": """
            <h2>Сетевые папки ГМ</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Быстро создаёт ярлык на сетевую папку выбранного ГМ.
                Поиск по коду ГМ или названию. Ярлык создаётся на рабочем
                столе пользователя. Также создаёт папку ПИ ГМ с пятью
                подпапками (1–4 сутки, Итоговые).</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Найдите ГМ (автокомплит).</li>
                    <li>Двойной клик по ГМ — сразу создать ярлык.</li>
                    <li>Или нажмите «Создать папку ПИ».</li>
                </ol>
            </div>
        """
    },
    "distance": {
        "name": "Расстояние между ГМ",
        "icon": "distance",
        "html": """
            <h2>Расстояние между ГМ</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Расчёт расстояния между двумя магазинами.
                Показывает расстояние по прямой (haversine) и оценку
                по дорогам (×1.2), а также время в пути.</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Введите название ГМ или адрес.</li>
                    <li>Нажмите «Рассчитать».</li>
                    <li>Кнопка «Поменять местами» меняет точки.</li>
                </ol>
            </div>
        """
    },
    "terminal": {
        "name": "Терминал",
        "icon": "terminal",
        "html": """
            <h2>Терминал</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Подключение к удалённому ГМ через mstsc.exe.
                Автодополнение ГМ (по коду и названию).
                Сохранение пароля через cmdkey (учётные данные Windows).</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Выберите ГМ (автокомплит).</li>
                    <li>Нажмите «Подключиться».</li>
                    <li>RDP открывается отдельным окном (Qt не встраивает
                    не-Qt окна).</li>
                </ol>
            </div>
        """
    },
    "tsd": {
        "name": "ТСД (QR-коды)",
        "icon": "tsd",
        "html": """
            <h2>ТСД (QR-коды)</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Генерация QR-кодов (тёмный фон, красные модули) для прошивки
                терминалов. Ведёт на http://10.2.252.5:8080/hms/iface/login.</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Введите данные для QR-кода.</li>
                    <li>Нажмите «Сгенерировать».</li>
                    <li>Сохраните или покажите QR-код терминалу.</li>
                </ol>
            </div>
        """
    },
    "asus": {
        "name": "АСУС",
        "icon": "globe",
        "html": """
            <h2>АСУС</h2>
            <div class="section">
                <h3>ЧТО ДЕЛАЕТ</h3>
                <p>Встроенный браузер на WebView2 (pywv2) для работы с АСУС.
                Вкладки «Командировка» и «Help» убраны — остался только АСУС.
                Верхняя и нижняя панели отсутствуют, окно браузера занимает
                всё пространство вкладки. Cookies и localStorage сохраняются
                между сессиями.</p>
            </div>
            <div class="section">
                <h3>КАК ПОЛЬЗОВАТЬСЯ</h3>
                <ol>
                    <li>Откройте вкладку «АСУС» в сайдбаре.</li>
                    <li>Работайте с сайтом АСУС как в обычном браузере.</li>
                    <li>При переключении вкладок окно скрывается/показывается
                    без изменения размера — это нормально.</li>
                </ol>
            </div>
        """
    },
}

ABOUT_TEXT = (
    "Модули:\n"
    "• Кванты — автоматический анализ квантов\n"
    "• Паллеты — сборка свода по паллетам\n"
    "• ОС и МБП — свод инвентаризационных описей\n"
    "• Брак/Утиль — сверка актов списания\n"
    "• Нарушения — Трассировщик (Зеркалка, Коробочный, Обычная приемка)\n"
    "• Инвентаризация — чек-листы по дням и сменам\n"
    "• Табель — рабочее время ревизора (К/Д/Н)\n"
    "• Дашборд — аналитика по письмам инвентаризации\n"
    "• Архив — завершённые инвентаризации\n"
    "• AI («Стажёр») — разметка Shadow Engine\n"
    "• Комментарии — готовые шаблоны текстов\n"
    "• Расстояние — расчёт расстояний между ГМ\n"
    "• Принтеры — управление принтерами\n"
    "• Сетевые папки — ярлыки ГМ и папки ПИ\n"
    "• Терминал — подключение через mstsc\n"
    "• ТСД — QR-коды для прошивки терминалов\n"
    "• АСУС — встроенный браузер (WebView2)\n"
    "• Калькулятор и Блокнот — быстрые утилиты в нижней панели\n"
    "• Утилиты — меню вспомогательных инструментов\n"
    "• Информация — эта вкладка"
)

# Стили для HTML-текста (шрифт 18px, заголовки 30px)
HTML_STYLE = """
<style>
    body { color: #E0E0E0; font-family: 'Segoe UI', sans-serif; font-size: 18px; line-height: 1.6; }
    h2 { color: #FFFFFF; font-size: 30px; margin-bottom: 10px; margin-top: 0px; }
    h3 { color: #D42626; font-size: 17px; font-weight: bold; margin-top: 26px; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
    p { margin-top: 0px; margin-bottom: 16px; }
    ol { margin-top: 0px; margin-left: -15px; margin-bottom: 22px; }
    li { margin-bottom: 12px; }
    em { color: #A0A0A0; font-style: normal; }
    .section { border-left: 2px solid #333333; padding-left: 18px; margin-left: 5px; margin-bottom: 24px; }
</style>
"""


class InfoFrame(BaseFrame):
    TITLE = "Информация"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)
        self._current_key = None
        self._setup_ui()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(10)

        title = QLabel("ИНФОРМАЦИЯ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

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

    def _build_instruction_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal, tab)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{ background-color: {self.COLORS.get('border', '#333333')}; width: 2px; }}
        """)

        # --- ЛЕВАЯ ПАНЕЛЬ ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Поиск
        self.search_entry = StyledEntry("Поиск по утилитам...")
        self.search_entry.textChanged.connect(self._filter_list)
        left_layout.addWidget(self.search_entry)

        # Список (плоский, без категорий)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {self.COLORS.get('card', '#222222')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
                font-size: 14px;
                outline: none;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 10px 10px;
                border-radius: 4px;
                margin-bottom: 2px;
            }}
            QListWidget::item:selected {{
                background-color: {self.COLORS.get('button', '#D42626')};
                color: #FFFFFF;
            }}
            QListWidget::item:hover {{
                background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
            }}
        """)
        self.list_widget.currentItemChanged.connect(self._on_instruction_selected)
        left_layout.addWidget(self.list_widget, 1)
        
        splitter.addWidget(left_panel)

        # --- ПРАВАЯ ПАНЕЛЬ ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        # Шапка правой панели
        header_row = QHBoxLayout()
        self.instr_title = QLabel("")
        self.instr_title.setStyleSheet("color: #FFFFFF; font-size: 22px; font-weight: bold;")
        header_row.addWidget(self.instr_title)
        header_row.addStretch()
        
        self.btn_copy = SecondaryButton(
            "Копировать", on_click=self._copy_instruction, icon_name="copy"
        )
        self.btn_copy.setMinimumWidth(140)
        self.btn_copy.setMinimumHeight(32)
        header_row.addWidget(self.btn_copy)
        
        right_layout.addLayout(header_row)

        # Текст инструкции
        self.instr_text = QTextBrowser()
        self.instr_text.setOpenExternalLinks(False)
        self.instr_text.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {self.COLORS.get('card', '#222222')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 8px;
                padding: 20px;
                selection-background-color: {self.COLORS.get('button', '#D42626')};
                selection-color: white;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {self.COLORS.get('card', '#222222')};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.COLORS.get('border', '#333333')};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {self.COLORS.get('text_dim', '#A0A0A0')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        right_layout.addWidget(self.instr_text, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([280, 720])

        layout.addWidget(splitter, 1)
        self.tabs.addTab(tab, "Инструкция")

        self._populate_list()

    def _populate_list(self):
        self.list_widget.clear()
        for key, data in INSTRUCTIONS.items():
            item = QListWidgetItem(data["name"])
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setIcon(get_icon(data["icon"], size=20))
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _filter_list(self, text):
        text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text not in item.text().lower())

    def _on_instruction_selected(self, current, _previous):
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        self._current_key = key
        data = INSTRUCTIONS.get(key, {})
        self.instr_title.setText(data.get("name", ""))
        
        html = HTML_STYLE + data.get("html", "")
        self.instr_text.setHtml(html)

    def _copy_instruction(self):
        try:
            text = self.instr_text.toPlainText()
            if not text:
                return

            clipboard = QApplication.clipboard()
            clipboard.setText(text)

            if clipboard.text() == text:
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

    def _build_about_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )

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

        dev_label = QLabel("Разработчик: Сильченко Алексей", about_card)
        dev_label.setFont(self.FONTS['label'])
        dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_card.layout().addWidget(dev_label)

        modules_label = QLabel(ABOUT_TEXT, about_card)
        modules_label.setFont(self.FONTS['label'])
        modules_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        modules_label.setWordWrap(True)
        modules_label.setStyleSheet(f"color: {self.COLORS.get('text', '#E0E0E0')};")
        about_card.layout().addWidget(modules_label)

        layout.addWidget(about_card)
        layout.addStretch()

        self.tabs.addTab(tab, "О программе")