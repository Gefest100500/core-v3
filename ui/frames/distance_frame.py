# ui/frames/distance_frame.py
"""
Расстояние между ГМ.

- Два поля с автокомплитом ГМ (QCompleter)
- Расчёт по прямой (haversine) + оценка по дорогам
- Список магазинов в каждом городе
- Копирование результата в буфер

Улучшения по сравнению с CTk-версией:
- QCompleter вместо самодельного окна с подсказками
- Убран _on_global_click
- Исправлен баг с импортом add_action из home_frame
- Запоминаются последние ГМ (QSettings)
- Кнопка "Поменять местами"

Правки стиля:
- Убраны все эмодзи
- Кнопки — SVG-иконки
"""
import os

from PyQt6.QtCore import Qt, QStringListModel, QSettings, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QCompleter, QTextEdit, QLineEdit, QApplication, QPushButton
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, StyledEntry, PrimaryButton, SecondaryButton
)
from ui.icons import get_icon_simple
from core.gm_map import (
    load_gm_data, get_city_coords, get_stores_by_city,
    find_store_by_text, _extract_city
)
from utils.geo_utils import calculate_distance
from utils.logger import log


class DistanceFrame(BaseFrame):

    TITLE = "Расстояние между ГМ"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.stores_data = []
        self.city_coords = {}
        self.stores_by_city = {}

        self._settings = QSettings("SilchenkoAleksey", "CoreV3")

        self._setup_ui()
        self._load_data()
        self._restore_last_gms()

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
        title = QLabel("РАССТОЯНИЕ МЕЖДУ ГМ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # --- Карточка с полями ---
        card = create_card(self)

        # --- ГМ №1 ---
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        lbl1 = QLabel("ГМ №1:", card)
        lbl1.setFont(self.FONTS['label'])
        lbl1.setFixedWidth(100)
        row1.addWidget(lbl1)

        self.entry_gm1 = StyledEntry(
            placeholder="Введите название ГМ или адрес",
            parent=card
        )
        self.entry_gm1.setMinimumWidth(500)
        self.entry_gm1.returnPressed.connect(self.calculate)
        row1.addWidget(self.entry_gm1, 1)

        card.layout().addLayout(row1)

        # --- ГМ №2 ---
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        lbl2 = QLabel("ГМ №2:", card)
        lbl2.setFont(self.FONTS['label'])
        lbl2.setFixedWidth(100)
        row2.addWidget(lbl2)

        self.entry_gm2 = StyledEntry(
            placeholder="Введите название ГМ или адрес",
            parent=card
        )
        self.entry_gm2.setMinimumWidth(500)
        self.entry_gm2.returnPressed.connect(self.calculate)
        row2.addWidget(self.entry_gm2, 1)

        card.layout().addLayout(row2)

        root_layout.addWidget(card)

        # --- Кнопки ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        # 🆕 РАССЧИТАТЬ с SVG-иконкой
        self.btn_calc = PrimaryButton(
            "РАССЧИТАТЬ",
            on_click=self.calculate,
            parent=self
        )
        self.btn_calc.setMinimumWidth(280)
        self.btn_calc.setMinimumHeight(50)
        distance_icon = get_icon_simple("distance", color="#FFFFFF", size=18)
        if not distance_icon.isNull():
            self.btn_calc.setIcon(distance_icon)
            self.btn_calc.setIconSize(QSize(18, 18))
        btn_row.addWidget(self.btn_calc)

        # 🆕 Поменять с SVG-иконкой
        btn_swap = SecondaryButton(
            "Поменять",
            on_click=self._swap_gms,
            parent=self
        )
        btn_swap.setMinimumWidth(160)
        btn_swap.setMinimumHeight(50)
        swap_icon = get_icon_simple("swap", color=self.COLORS.get('text', '#E0E0E0'), size=16)
        if not swap_icon.isNull():
            btn_swap.setIcon(swap_icon)
            btn_swap.setIconSize(QSize(16, 16))
        btn_row.addWidget(btn_swap)

        # 🆕 Очистить с SVG-иконкой
        btn_clear = SecondaryButton(
            "Очистить",
            on_click=self.clear,
            parent=self
        )
        btn_clear.setMinimumWidth(180)
        btn_clear.setMinimumHeight(50)
        trash_icon = get_icon_simple("trash", color=self.COLORS.get('error', '#FF5252'), size=16)
        if not trash_icon.isNull():
            btn_clear.setIcon(trash_icon)
            btn_clear.setIconSize(QSize(16, 16))
        btn_row.addWidget(btn_clear)

        btn_row.addStretch()
        root_layout.addLayout(btn_row)

        # --- Карточка результата ---
        self.result_card = create_card(self)
        root_layout.addWidget(self.result_card, 1)

        self.result_title = QLabel(
            "Введите два ГМ и нажмите «Рассчитать»",
            self.result_card
        )
        self.result_title.setFont(self.FONTS['subtitle'])
        self.result_title.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.result_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_card.layout().addWidget(self.result_title)

        self.result_text = QTextEdit(self.result_card)
        self.result_text.setReadOnly(True)
        self.result_text.setFont(self.FONTS['label'])
        self.result_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.COLORS.get('bg', '#1B1B1B')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: none;
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        self.result_card.layout().addWidget(self.result_text, 1)

        # 🆕 Кнопка "Скопировать" с SVG-иконкой
        self.btn_copy = PrimaryButton(
            "Скопировать результат",
            on_click=self.copy_to_clipboard,
            parent=self.result_card
        )
        self.btn_copy.setMinimumWidth(280)
        self.btn_copy.setEnabled(False)
        copy_icon = get_icon_simple("copy", color="#FFFFFF", size=16)
        if not copy_icon.isNull():
            self.btn_copy.setIcon(copy_icon)
            self.btn_copy.setIconSize(QSize(16, 16))

        copy_row = QHBoxLayout()
        copy_row.addStretch()
        copy_row.addWidget(self.btn_copy)
        copy_row.addStretch()
        self.result_card.layout().addLayout(copy_row)

    # =========================================================
    # ЗАГРУЗКА ДАННЫХ
    # =========================================================
    def _load_data(self):
        try:
            self.stores_data = load_gm_data()
            self.city_coords = get_city_coords()
            self.stores_by_city = get_stores_by_city(self.stores_data)

            self._attach_completer(self.entry_gm1)
            self._attach_completer(self.entry_gm2)

            log.info(
                f"DistanceFrame: загружено {len(self.stores_data)} магазинов, "
                f"{len(self.city_coords)} городов"
            )
        except Exception as e:
            log.exception("Ошибка загрузки данных для расчёта расстояний")
            self.show_error("Ошибка", f"Не удалось загрузить данные:\n{e}")

    # =========================================================
    # АВТОКОМПЛИТ
    # =========================================================
    def _attach_completer(self, entry: QLineEdit):
        if not self.stores_data:
            return

        items = []
        for store in self.stores_data:
            name = store.get("Название", "")
            address = store.get("Адрес", "")
            combined = f"{name} — {address}" if address else name
            items.append(combined)

        model = QStringListModel(items, entry)
        completer = QCompleter(model, entry)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(10)

        entry.setCompleter(completer)

    # =========================================================
    # СОХРАНЕНИЕ/ВОССТАНОВЛЕНИЕ
    # =========================================================
    def _restore_last_gms(self):
        try:
            last1 = self._settings.value("distance_gm1", "")
            last2 = self._settings.value("distance_gm2", "")
            if last1:
                self.entry_gm1.setText(last1)
            if last2:
                self.entry_gm2.setText(last2)
        except Exception:
            pass

    def _save_last_gms(self):
        try:
            self._settings.setValue("distance_gm1", self.entry_gm1.text().strip())
            self._settings.setValue("distance_gm2", self.entry_gm2.text().strip())
        except Exception:
            pass

    # =========================================================
    # ВСПОМОГАТЕЛЬНЫЕ
    # =========================================================
    def _swap_gms(self):
        t1 = self.entry_gm1.text()
        t2 = self.entry_gm2.text()
        self.entry_gm1.setText(t2)
        self.entry_gm2.setText(t1)

    # =========================================================
    # РАСЧЁТ
    # =========================================================
    def _resolve_city(self, text):
        if not text:
            return None, None

        store = find_store_by_text(text, self.stores_data)
        if store:
            name = store.get("Название", "")
            city = _extract_city(name)
            return city, store

        text_lower = text.strip().lower()
        for city in self.city_coords.keys():
            if city.lower() == text_lower:
                return city, None

        for city in self.city_coords.keys():
            if text_lower in city.lower():
                return city, None

        return None, None

    def calculate(self):
        text1 = self.entry_gm1.text().strip()
        text2 = self.entry_gm2.text().strip()

        if not text1 or not text2:
            self._set_error("Введите оба ГМ")
            return

        city1, store1 = self._resolve_city(text1)
        city2, store2 = self._resolve_city(text2)

        if not city1 or not city2:
            bad = text1 if not city1 else text2
            self._set_error(f"Не найден: {bad}")
            return

        if city1 not in self.city_coords or city2 not in self.city_coords:
            missing = city1 if city1 not in self.city_coords else city2
            self._set_error(f"Нет координат для города: {missing}")
            self.result_text.setPlainText(
                "Проверьте кэш городов в data/gm_cities_cache.json."
            )
            return

        result = calculate_distance(
            self.city_coords[city1],
            self.city_coords[city2]
        )
        if not result:
            self._set_error("Ошибка расчёта")
            return

        # Заголовок без 📍
        self.result_title.setText(f"{city1} → {city2}")
        self.result_title.setStyleSheet(
            f"color: {self.COLORS.get('success', '#4CAF50')};"
        )

        stores1 = self.stores_by_city.get(city1, [])
        stores2 = self.stores_by_city.get(city2, [])

        lines = []
        lines.append(f"По прямой: {result['direct_km']} км")
        lines.append(f"По дорогам: ~{result['road_km']} км (оценка)")
        lines.append(f"Примерно: {result['duration_str']}")
        lines.append("")

        lines.append(f"{city1}: {len(stores1)} магазинов")
        for s in stores1[:10]:
            lines.append(f"  • {s.get('Название', '?')}")
        if len(stores1) > 10:
            lines.append(f"  ... и ещё {len(stores1) - 10}")

        lines.append("")
        lines.append(f"{city2}: {len(stores2)} магазинов")
        for s in stores2[:10]:
            lines.append(f"  • {s.get('Название', '?')}")
        if len(stores2) > 10:
            lines.append(f"  ... и ещё {len(stores2) - 10}")

        self.result_text.setPlainText("\n".join(lines))
        self.btn_copy.setEnabled(True)

        log.info(f"Расчёт: {city1} → {city2} = {result['direct_km']} км")

        self._save_last_gms()

        try:
            self.app.data_manager.add_action(
                "Расчёт расстояния",
                f"{city1} → {city2} = {result['direct_km']} км",
                "📏"
            )
        except Exception:
            pass

    def _set_error(self, message):
        self.result_title.setText(message)
        self.result_title.setStyleSheet(
            f"color: {self.COLORS.get('error', '#FF5252')};"
        )
        self.result_text.setPlainText("")
        self.btn_copy.setEnabled(False)

    # =========================================================
    # КОПИРОВАНИЕ
    # =========================================================
    def copy_to_clipboard(self):
        text = self.result_text.toPlainText().strip()
        if not text:
            return
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.show_success("Скопировано", "Результат скопирован в буфер обмена.")
        except Exception as e:
            log.error(f"Ошибка копирования: {e}")
            self.show_error("Ошибка", f"Не удалось скопировать:\n{e}")

    # =========================================================
    # ОЧИСТКА
    # =========================================================
    def clear(self):
        self.entry_gm1.clear()
        self.entry_gm2.clear()
        self.result_title.setText("Введите два ГМ и нажмите «Рассчитать»")
        self.result_title.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.result_text.setPlainText("")
        self.btn_copy.setEnabled(False)

        try:
            self._settings.remove("distance_gm1")
            self._settings.remove("distance_gm2")
        except Exception:
            pass