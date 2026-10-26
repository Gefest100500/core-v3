# Core V3.0 — структура проекта

Карта файлов и модулей. Показывает архитектуру, разделение слоёв
и точки расширения.

## Общая схема

    C:\Core_V3_0\
    │
    ├── main.py                     Точка входа, тёмный title bar, заставка
    ├── config.py                   Конфигурация: цвета, шрифты, папки, пороги
    ├── config.json                 Внешний конфиг (правится без кода)
    ├── pyproject.toml              Сборка и зависимости (основной путь установки)
    ├── README.md                   Описание проекта
    ├── PROJECT_STRUCTURE.md        Этот файл
    ├── .gitignore                  Игнор для git
    ├── .github/workflows/          GitHub Actions (CI/CD)
    │   └── tests.yml               Автозапуск тестов при push
    │
    ├── ui/                         Интерфейс (PyQt6)
    │   ├── app.py                  Главное окно, сайдбар, навигация
    │   ├── splash.py               Полноэкранная заставка (fade-out/fade-in)
    │   ├── styles.py               QSS-шаблон тёмной темы
    │   ├── icons.py                Загрузчик SVG-иконок
    │   ├── icons/                  SVG-иконки (стиль Lucide)
    │   │
    │   ├── components/             Общие виджеты и диалоги
    │   │   ├── widgets.py          create_card, PrimaryButton, StyledEntry,
    │   │   │                       AnimatedPlaceholderEntry, style_popup
    │   │   ├── dialogs.py          CustomMessageBox, ask_confirm
    │   │   ├── calculator_dialog.py Мини-калькулятор (тёмная шапка)
    │   │   └── notepad_dialog.py   Блокнот (сохранение в %LOCALAPPDATA%/Core_V3_0/notes/,
    │   │                           кнопки «Новая», «Удалить», кастомное подтверждение)
    │   │
    │   └── frames/                 Вкладки (по одной на модуль)
    │       ├── base_frame.py       Базовый класс: run_in_thread, run_on_ui,
    │       │                       on_hide, on_close
    │       ├── home_frame.py       Главная
    │       ├── kv_frame.py         Кванты
    │       ├── os_mbp_frame.py     ОС и МБП
    │       ├── brak_util_frame.py  Брак/Утиль
    │       ├── pal_frame.py        Паллеты
    │       ├── inventory_frame.py  Инвентаризация
    │       ├── timesheet_frame.py  Табель
    │       ├── comments_frame.py   Стандартные комментарии
    │       ├── printers_frame.py   Принтеры
    │       ├── gm_frame.py         Сетевые папки
    │       ├── distance_frame.py   Расстояние между ГМ
    │       ├── terminal_frame.py   Терминал (mstsc)
    │       ├── tsd_frame.py        ТСД (QR-коды)
    │       ├── web_frame.py        Web (pywv2 / WebView2, вкладка АСУС)
    │       ├── dashboard_frame.py  Дашборд отчётов из Outlook
    │       ├── archive_frame.py    Архив инвентаризаций
    │       ├── ai_frame.py         AI — «Стажёр» (разметка Shadow Engine)
    │       ├── violations_frame.py Нарушения (Трассировщик)
    │       ├── info_frame.py       Информация
    │       └── utils_frame.py      Меню утилит
    │
    ├── core/                       Бизнес-логика (без PyQt)
    │   ├── kv_analyzer.py          Анализ квантов
    │   ├── os_mbp_analyzer.py      Парсер инвентаризационных описей
    │   ├── brak_util_analyzer.py   Сверка Брак/Утиль
    │   ├── pal_analyzer.py         Сборка паллет
    │   ├── violations_analyzer.py  Нарушения (Трассировщик)
    │   ├── comments_builder.py     Логика шаблонов комментариев
    │   ├── printer_manager.py      Управление принтерами
    │   ├── gm_map.py               Координаты ГМ, геокодинг
    │   ├── inventory_helper.py     Помощник инвентаризации
    │   ├── timesheet.py            Логика табеля (load/save, формат АСУЗ)
    │   ├── dashboard_builder.py    Сбор данных для дашборда «Общий пересчёт»
    │   ├── terminal_helper.py      Хелпер для Терминала (mstsc)
    │   ├── email_parser.py         Парсер писем Outlook
    │   ├── email_storage.py        Хранилище писем (через DataManager)
    │   ├── email_analytics.py      Аналитика по письмам
    │   ├── email_service.py        Оркестрация: Outlook → парсер → хранилище
    │   └── outlook_connector.py    Сбор писем из Outlook (win32com)
    │
    ├── ml/                         Shadow Engine (без PyQt)
    │   ├── shadow.py               Генерация гипотез по правилам
    │   ├── features.py             Признаки строки для ML
    │   ├── feedback.py             Разметка «Согласен / Не согласен»
    │   ├── storage.py              SQLite-хранилище (гипотезы, feedback)
    │   ├── config.py               Настройки ML (пути, параметры)
    │   └── README.md               Документация по ML
    │
    ├── utils/                      Утилиты (без PyQt)
    │   ├── logger.py               Логирование с ротацией
    │   ├── file_utils.py           Пути (get_data_dir и др.), clear_folder
    │   ├── data_migration.py       Одноразовая миграция data/ в %LOCALAPPDATA%
    │   ├── data_manager.py         JSON-хранилище с кэшем и очередью записи
    │   ├── parsing.py              Парсинг чисел, номеров, поиск столбцов
    │   ├── formatting.py           Форматирование сумм и процентов
    │   ├── excel_utils.py          autofit_columns, safe_filename
    │   ├── network_utils.py        IP, ping, порты принтеров
    │   ├── geo_utils.py            Расчёт расстояний (haversine)
    │   └── machine_info.py         Информация о машине
    │
    ├── tests/                      Тесты (pytest, 730+ passed)
    │   ├── conftest.py             Общие фикстуры
    │   ├── test_parsing.py
    │   ├── test_formatting.py
    │   ├── test_data_manager.py
    │   ├── test_data_manager_extra.py
    │   ├── test_data_manager_run.py
    │   ├── test_data_dir.py
    │   ├── test_data_migration.py
    │   ├── test_file_utils_run.py
    │   ├── test_comments_builder.py
    │   ├── test_kv_analyzer.py
    │   ├── test_kv_analyzer_run.py
    │   ├── test_brak_util_analyzer.py
    │   ├── test_brak_util_analyzer_run.py
    │   ├── test_excel_utils.py
    │   ├── test_email_parser.py
    │   ├── test_email_analytics.py
    │   ├── test_email_storage_run.py
    │   ├── test_os_mbp_analyzer.py
    │   ├── test_pal_analyzer.py
    │   ├── test_violations_analyzer.py
    │   ├── test_timesheet.py
    │   ├── test_terminal_helper.py
    │   ├── test_inventory_helper.py
    │   ├── test_geo_utils.py
    │   ├── test_gm_map.py
    │   ├── test_network_utils.py
    │   ├── test_ml_shadow.py
    │   ├── test_ml_feedback.py
    │   ├── test_ml_storage.py
    │   └── test_ml_integration.py
    │
    ├── Готовые/                    Результаты (создаётся автоматически)
    ├── Logs/                       Логи (создаётся автоматически)
    └── temp/                       Временные файлы (создаётся автоматически)

## Данные (%LOCALAPPDATA%)

Данные ревизора **не** лежат в корне проекта. Они живут в:

    %LOCALAPPDATA%\Core_V3_0\data\

Это нужно, чтобы программа работала из Program Files и не теряла
данные при обновлении. Миграция старой `data/` из корня проекта
выполняется один раз при первом запуске (`utils/data_migration.py`,
флаг `.migrated`).

Содержимое `%LOCALAPPDATA%\Core_V3_0\data\`:

    data/
    ├── .migrated                   Флаг: миграция выполнена
    ├── gm_data.json                Справочник магазинов
    ├── gm_ip.json                  IP-адреса ГМ
    ├── gm_cities_cache.json        Кэш координат городов
    ├── inventory_plans.json        Планы инвентаризаций (варианты А–Ж)
    ├── inventory_archive.json      Архив завершённых инвентаризаций
    ├── active_inventory.json       Активная инвентаризация
    ├── checklists.json             Чек-листы инвентаризации
    ├── checklists_state.json       Состояние чек-листов
    ├── timesheet.json              Табель ревизора
    ├── standard_comments.json      Шаблоны комментариев
    ├── kv_rules.json               Правила анализа квантов
    ├── kv_reason_schema.json       Строгая маска причин
    ├── steal_codes.json            Коды возможных хищений
    ├── unwanted.json               Фильтр мусорных позиций
    ├── actions_history.json        История действий
    ├── distance_history.json       История расчётов расстояний
    ├── user_settings.json          Локальные настройки пользователя
    ├── example_email.txt           Пример письма
    ├── notes/                      Блокнот (заметки пользователя)
    ├── emails/
    │   └── emails.json             Письма инвентаризации
    ├── ml/
    │   ├── shadow.sqlite           SQLite: гипотезы и feedback
    │   ├── exports/                Экспорт feedback (JSONL)
    │   └── models/                 Модели ML
    └── webengine/
        └── asus/                   Профиль WebView2 (pywv2): АСУС

> Каталоги `webengine/help/` и `webengine/trip/` в текущей версии
> **не используются**: вкладки «Командировка» и «Help» убраны из Web.
> Их URL остаются в `config.json` как зарезервированные — при
> необходимости вкладки можно вернуть тем же механизмом
> `ShowWindow`/`HideWindow`, что и АСУС.

## Слои приложения

- `ui/` — только пользовательский интерфейс. Бизнес-логики нет.
- `core/` — бизнес-логика. Не зависит от PyQt, тестируется отдельно.
- `ml/` — Shadow Engine. Не зависит от PyQt, тестируется отдельно.
- `utils/` — утилиты. Не зависит от PyQt, полностью тестируемо.
- `data/` — данные в JSON, в `%LOCALAPPDATA%`. Меняются без правки кода.

## Технологии

- Python 3.13
- PyQt6 (интерфейс)
- pywv2 (WebView2) — вкладка «АСУС»
- pandas, openpyxl (обработка Excel)
- qrcode[pil] (QR-коды, вкладка ТСД)
- Shadow Engine на SQLite (разметка, feedback)
- pytest (тестирование, 730+ тестов)
- GitHub Actions (CI/CD, автоматический запуск тестов при push)