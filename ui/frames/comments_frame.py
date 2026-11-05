# ui/frames/comments_frame.py
"""
Стандартные комментарии.

ИЗМЕНЕНИЯ:
- Подсказка (hint_label) теперь всегда нейтральная (серая),
  без красного акцента.
- Добавлен setObjectName("StatusNeutral") для подсказки.
- COMMENTS_PATH теперь берётся из utils.data_manager (единая точка правды),
  читается из %LOCALAPPDATA%/Core_V3_0/data.
- В _attach_gm_completer добавлена очистка кода товара из поля ГМ:
  при выборе из выпадающего списка остаётся только название.
"""
import os
import json

from PyQt6.QtCore import Qt, QStringListModel, QTimer, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QCompleter, QApplication
)

from utils.file_utils import get_base_dir
from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, StyledEntry, PrimaryButton, SecondaryButton,
    style_popup, AnimatedPlaceholderEntry,
)
from ui.icons import get_icon_simple
from utils.logger import log
from core.comments_builder import build_comment_text

from utils.data_manager import GM_DATA_PATH, STANDARD_COMMENTS_PATH


BASE_DIR = get_base_dir()

COMMENTS_PATH = STANDARD_COMMENTS_PATH

EMOJI_TO_ICON = {
    "🏭": "production",
    "🧩": "pal",
    "📦": "os_mbp",
    "📊": "kv",
    "🛢": "brak_util",
    "⚠️": "violations",
    "📝": "comments",
    "📏": "distance",
    "📁": "gm",
    "🏪": "inventory",
    "📋": "copy",
}


class CommentsFrame(BaseFrame):

    TITLE = "Стандартные комментарии"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self.comments = []
        self.gm_data = []

        self.var_entries = {}
        self.preview_labels = {}
        self._saved_values = {}

        self.current_gm_name = self._get_current_gm_name()
        self.hint_label = None

        self._setup_ui()
        self._load_gm_data()
        self._load_comments()
        self._render_comments()

    # =========================================================
    # ОБНОВЛЕНИЕ
    # =========================================================
    def refresh(self):
        self._save_current_values()
        self.current_gm_name = self._get_current_gm_name()
        self._update_hint()
        self._load_gm_data()
        self._load_comments()
        self._render_comments()

    def _save_current_values(self):
        self._saved_values = {}
        for cid, vars_dict in self.var_entries.items():
            self._saved_values[cid] = {
                k: e.text().strip() for k, e in vars_dict.items()
            }

    # =========================================================
    # ГМ ИЗ АКТИВНОЙ ИНВЕНТАРИЗАЦИИ
    # =========================================================
    def _get_current_gm_name(self):
        try:
            dm = self.app.data_manager
            active = dm.get_active_inventory()
            if not active:
                return ""
            return active.get("gm_name", "").strip()
        except Exception as e:
            log.warning(f"Не удалось получить активную инвентаризацию: {e}")
            return ""

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)

        btn_back = SecondaryButton(
            "Назад в утилиты",
            on_click=lambda: self.app.show_tab("utils"),
            parent=self
        )
        btn_back.setMinimumWidth(180)
        top.addWidget(btn_back)
        top.addStretch()

        root_layout.addLayout(top)

        title = QLabel("СТАНДАРТНЫЕ КОММЕНТАРИИ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        hint_text, hint_color = self._get_hint_text_and_color()
        self.hint_label = QLabel(hint_text, self)
        self.hint_label.setObjectName("StatusNeutral")
        self.hint_label.setFont(self.FONTS['small'])
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(self.hint_label)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(12)

        self.scroll.setWidget(self.scroll_content)
        root_layout.addWidget(self.scroll, 1)

    def _get_hint_text_and_color(self):
        if self.current_gm_name:
            return (
                f"Активная инвентаризация: {self.current_gm_name}",
                self.COLORS.get("text_dim", "#A0A0A0")
            )
        return (
            "Заполните поля и нажмите «Скопировать» — текст попадёт в буфер обмена",
            self.COLORS.get("text_dim", "#A0A0A0")
        )

    def _update_hint(self):
        if self.hint_label is None:
            return
        try:
            text, color = self._get_hint_text_and_color()
            self.hint_label.setText(text)
            self.hint_label.setStyleSheet(f"color: {color};")
        except Exception:
            pass

    # =========================================================
    # ЗАГРУЗКА ДАННЫХ
    # =========================================================
    def _load_gm_data(self):
        if not os.path.isfile(GM_DATA_PATH):
            log.warning(f"gm_data.json не найден: {GM_DATA_PATH}")
            self.gm_data = []
            return
        try:
            with open(GM_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.gm_data = data
        except (json.JSONDecodeError, IOError) as e:
            log.error(f"Ошибка загрузки gm_data.json: {e}")
            self.gm_data = []

    def _load_comments(self):
        if not os.path.isfile(COMMENTS_PATH):
            log.warning(f"Файл стандартных комментариев не найден: {COMMENTS_PATH}")
            self.comments = []
            return
        try:
            with open(COMMENTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.comments = data.get("comments", [])
            log.info(f"Загружено комментариев: {len(self.comments)}")
        except (json.JSONDecodeError, IOError) as e:
            log.error(f"Ошибка загрузки стандартных комментариев: {e}")
            self.comments = []

    # =========================================================
    # РЕНДЕР
    # =========================================================
    def _render_comments(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self.var_entries = {}
        self.preview_labels = {}

        if not self.comments:
            empty = QLabel(
                "Нет доступных комментариев.\n\n"
                "Проверьте файл data/standard_comments.json",
                self.scroll_content
            )
            empty.setFont(self.FONTS['label'])
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
            self.scroll_layout.addWidget(empty)
            self.scroll_layout.addStretch()
            return

        for item in self.comments:
            card = self._create_comment_card(item)
            self.scroll_layout.addWidget(card)

        self.scroll_layout.addStretch()

    def _create_comment_card(self, item):
        comment_id = item.get("id", "")
        icon_emoji = item.get("icon", "")
        title = item.get("title", "Без названия")
        template = item.get("template", "")
        variables = item.get("variables", [])

        card = create_card(self.scroll_content)

        header = QHBoxLayout()
        header.setSpacing(8)

        icon_name = EMOJI_TO_ICON.get(icon_emoji)
        if icon_name:
            icon = get_icon_simple(
                icon_name,
                color=self.COLORS.get('button', '#D42626'),
                size=20
            )
            if not icon.isNull():
                icon_label = QLabel(card)
                icon_label.setPixmap(icon.pixmap(20, 20))
                header.addWidget(icon_label)

        title_label = QLabel(title, card)
        title_label.setFont(self.FONTS['subtitle'])
        header.addWidget(title_label)

        header.addStretch()
        card.layout().addLayout(header)

        vars_dict = {}
        saved = self._saved_values.get(comment_id, {})

        for var in variables:
            key = var.get("key", "")
            label = var.get("label", key)
            default = var.get("default", "")
            vtype = var.get("type", "text")

            if key in saved and saved[key]:
                value = saved[key]
            elif vtype == "gm_autocomplete" and self.current_gm_name:
                value = self.current_gm_name
            else:
                value = default

            row = QHBoxLayout()
            row.setSpacing(10)

            lbl = QLabel(f"{label}:", card)
            lbl.setFont(self.FONTS['label'])
            lbl.setFixedWidth(260)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl)

            if vtype == "gm_autocomplete":
                entry = AnimatedPlaceholderEntry(
                    placeholder="Начните вводить название ГМ",
                    parent=card
                )
            else:
                entry = StyledEntry(
                    placeholder="",
                    parent=card
                )

            entry.setText(value)
            entry.setMinimumWidth(400)

            if vtype == "gm_autocomplete":
                self._attach_gm_completer(entry)

            entry.textChanged.connect(
                lambda text, cid=comment_id: self._update_preview(cid)
            )

            entry.returnPressed.connect(
                lambda cid=comment_id: self._copy_comment(cid)
            )

            row.addWidget(entry)
            row.addStretch()

            card.layout().addLayout(row)

            vars_dict[key] = entry

        self.var_entries[comment_id] = vars_dict

        preview_box = QFrame(card)
        preview_box.setStyleSheet(f"""
            QFrame {{
                background-color: {self.COLORS.get('sidebar', '#2A2A2A')};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(12, 12, 12, 12)

        preview_label = QLabel(template, preview_box)
        preview_label.setFont(self.FONTS['label'])
        preview_label.setWordWrap(True)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        preview_layout.addWidget(preview_label)

        card.layout().addWidget(preview_box)

        self.preview_labels[comment_id] = preview_label

        btn_copy = PrimaryButton(
            "Скопировать готовый текст",
            on_click=lambda cid=comment_id: self._copy_comment(cid),
            parent=card
        )
        btn_copy.setMinimumWidth(300)
        copy_icon = get_icon_simple("copy", color="#FFFFFF", size=18)
        if not copy_icon.isNull():
            btn_copy.setIcon(copy_icon)
            btn_copy.setIconSize(QSize(18, 18))

        btn_wrapper = QHBoxLayout()
        btn_wrapper.addWidget(btn_copy)
        btn_wrapper.addStretch()
        card.layout().addLayout(btn_wrapper)

        QTimer.singleShot(0, lambda cid=comment_id: self._update_preview(cid))

        return card

    # =========================================================
    # АВТОКОМПЛИТ ГМ
    # =========================================================
    def _attach_gm_completer(self, entry):
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

        style_popup(completer)

        entry.setCompleter(completer)

        # Флаг, чтобы не зациклиться при программной замене текста
        state = {"updating": False}

        def _strip_code(text):
            """Убирает код из строки 'код — название', оставляя название."""
            if " — " in text:
                return text.split(" — ", 1)[1]
            return text

        def _on_activated(text):
            name_only = _strip_code(text)
            state["updating"] = True
            try:
                entry.setText(name_only)
            finally:
                state["updating"] = False

        completer.activated.connect(_on_activated)

        def _on_text_edited_for_completer(text):
            if not text:
                completer.popup().hide()
                return
            completer.setCompletionPrefix(text)
            if completer.completionCount() > 0:
                completer.complete()
            else:
                completer.popup().hide()

        entry.textEdited.connect(_on_text_edited_for_completer)

        # Гарантированная очистка кода: если в поле оказался "код — название"
        # (например, QCompleter вставил его сам, не вызвав activated),
        # оставляем только название.
        def _on_text_changed_strip_code(text):
            if state["updating"]:
                return
            if " — " not in text:
                return
            name_only = _strip_code(text)
            if name_only == text:
                return
            state["updating"] = True
            try:
                entry.setText(name_only)
            finally:
                state["updating"] = False

        entry.textChanged.connect(_on_text_changed_strip_code)

    # =========================================================
    # ПРЕДПРОСМОТР
    # =========================================================
    def _collect_values(self, comment_id):
        vars_dict = self.var_entries.get(comment_id, {})
        return {k: e.text().strip() for k, e in vars_dict.items()}

    def _update_preview(self, comment_id):
        item = self._get_item(comment_id)
        if not item:
            return
        values = self._collect_values(comment_id)
        result = build_comment_text(item, values, for_copy=False)
        label = self.preview_labels.get(comment_id)
        if label is not None:
            label.setText(result)

    # =========================================================
    # КОПИРОВАНИЕ
    # =========================================================
    def _copy_comment(self, comment_id):
        item = self._get_item(comment_id)
        if not item:
            return

        variables = item.get("variables", [])
        vars_dict = self.var_entries.get(comment_id, {})
        empty = []
        for var in variables:
            key = var.get("key", "")
            label = var.get("label", key)
            entry = vars_dict.get(key)
            if entry is not None and not entry.text().strip():
                empty.append(label)

        if empty:
            self.show_warning(
                "Не все поля заполнены",
                "Заполните поля, прежде чем копировать:\n\n• " + "\n• ".join(empty)
            )
            return

        values = self._collect_values(comment_id)
        result = build_comment_text(item, values, for_copy=True)

        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(result)

            if clipboard.text() != result:
                raise RuntimeError("Буфер обмена не принял текст")

            log.info(f"Скопирован комментарий: {item.get('title', '')}")
            self.show_success(
                "Скопировано",
                "Готовый текст в буфере обмена.\n\n"
                "Вставьте в отчёт через Ctrl+V."
            )
        except Exception as e:
            log.error(f"Ошибка копирования: {e}")
            self.show_error("Ошибка", f"Не удалось скопировать:\n{e}")

    # =========================================================
    # УТИЛИТЫ
    # =========================================================
    def _get_item(self, comment_id):
        for item in self.comments:
            if item.get("id", "") == comment_id:
                return item
        return None