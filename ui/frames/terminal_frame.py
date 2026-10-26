# ui/frames/terminal_frame.py
"""
Терминал — подключение к удалённой машине ГМ через mstsc.

ИЗМЕНЕНИЯ:
- Плейсхолдер приведён к единому виду (с большой буквы).
- Стиль выпадающего списка (QCompleter) применяется через style_popup.
"""
import os
import json
import subprocess

from PyQt6.QtCore import Qt, QStringListModel, QSettings, QSize, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QCompleter, QPushButton
)

from utils.file_utils import get_base_dir
from utils.logger import log
from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton,
    style_popup, AnimatedPlaceholderEntry,
)
from ui.components.dialogs import ask_password
from ui.icons import get_icon_simple

from core.terminal_helper import (
    resolve_gm, build_target, get_gm_names,
    xor_encrypt, xor_decrypt, get_password_key,
)


GM_DATA_PATH = os.path.join(get_base_dir(), "data", "gm_data.json")


class AutoSelectEntry(AnimatedPlaceholderEntry):
    """Поле ввода, которое выделяет текст при получении фокуса."""

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


class TerminalFrame(BaseFrame):

    TITLE = "Терминал"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)

        self._settings = QSettings("SilchenkoAleksey", "CoreV3")
        self._gm_data = self._load_gm_data()
        self._password_key = get_password_key()

        self._gm_completer = None
        self._gm_model = None

        self._setup_ui()
        self._attach_completer(self._gm_data)

    # =========================================================
    # ЗАГРУЗКА GM_DATA
    # =========================================================
    def _load_gm_data(self):
        if not os.path.exists(GM_DATA_PATH):
            log.warning(f"TerminalFrame: gm_data.json не найден: {GM_DATA_PATH}")
            return []
        try:
            with open(GM_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                log.warning("TerminalFrame: gm_data.json должен быть списком")
                return []
            return data
        except Exception as e:
            log.exception(f"TerminalFrame: ошибка чтения gm_data.json: {e}")
            return []

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        title = QLabel("ТЕРМИНАЛ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        info = QLabel(
            "Введите название или код ГМ — и подключитесь к терминалу.",
            self
        )
        info.setFont(self.FONTS['small'])
        info.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(info)

        card = create_card(self)

        card_title = QLabel("Подключение к удалённому рабочему столу", card)
        card_title.setFont(self.FONTS['subtitle'])
        card.layout().addWidget(card_title)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        gm_lbl = QLabel("ГМ:", card)
        gm_lbl.setFont(self.FONTS['label'])
        gm_lbl.setFixedWidth(120)
        input_row.addWidget(gm_lbl)

        self.entry_gm = AutoSelectEntry(
            placeholder="Название или код (например: Балаково 3)",
            parent=card
        )
        self.entry_gm.setMinimumWidth(400)
        self.entry_gm.setMinimumHeight(40)
        self.entry_gm.returnPressed.connect(self._on_connect)
        input_row.addWidget(self.entry_gm, 1)

        card.layout().addLayout(input_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_connect = PrimaryButton(
            "Подключиться",
            on_click=self._on_connect,
            parent=card
        )
        self.btn_connect.setMinimumWidth(280)
        self.btn_connect.setMinimumHeight(46)
        plug_icon = get_icon_simple("terminal", color="#FFFFFF", size=18)
        if not plug_icon.isNull():
            self.btn_connect.setIcon(plug_icon)
            self.btn_connect.setIconSize(QSize(18, 18))
        btn_row.addWidget(self.btn_connect)

        self.btn_change_password = SecondaryButton(
            "Сменить пароль",
            on_click=self._on_change_password,
            parent=card
        )
        self.btn_change_password.setMinimumWidth(220)
        self.btn_change_password.setMinimumHeight(46)
        key_icon = get_icon_simple("pencil", color=self.COLORS.get('text', '#E0E0E0'), size=16)
        if not key_icon.isNull():
            self.btn_change_password.setIcon(key_icon)
            self.btn_change_password.setIconSize(QSize(16, 16))
        btn_row.addWidget(self.btn_change_password)

        btn_row.addStretch()
        card.layout().addLayout(btn_row)

        self.status_label = QLabel("", card)
        self.status_label.setFont(self.FONTS['label'])
        self.status_label.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.status_label.setWordWrap(True)
        card.layout().addWidget(self.status_label)

        root_layout.addWidget(card)
        root_layout.addStretch()

    # =========================================================
    # АВТОДОПОЛНЕНИЕ
    # =========================================================
    def _attach_completer(self, gm_data):
        if not gm_data:
            return

        try:
            if self._gm_completer is not None:
                self.entry_gm.setCompleter(None)
        except Exception:
            pass
        self._gm_completer = None
        self._gm_model = None

        names = get_gm_names(gm_data)
        if not names:
            return

        self._gm_model = QStringListModel(names, self.entry_gm)
        completer = QCompleter(self._gm_model, self.entry_gm)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(15)
        style_popup(completer)
        self.entry_gm.setCompleter(completer)
        self._gm_completer = completer

        def _on_activated(text):
            self.entry_gm.setText(text)

        completer.activated.connect(_on_activated)

        def _on_text_changed_for_completer(text):
            try:
                if self._gm_completer is None:
                    return
                if not text:
                    self._gm_completer.popup().hide()
                    return
                self._gm_completer.setCompletionPrefix(text)
                if self._gm_completer.completionCount() > 0:
                    self._gm_completer.complete()
                else:
                    self._gm_completer.popup().hide()
            except RuntimeError:
                pass

        self.entry_gm.textEdited.connect(_on_text_changed_for_completer)

    # =========================================================
    # ПОДКЛЮЧЕНИЕ
    # =========================================================
    def _on_connect(self):
        raw = self.entry_gm.text().strip()
        if not raw:
            self._set_status("Введите код, название или IP ГМ.", "#FF5252")
            return

        item = resolve_gm(raw, self._gm_data)
        if not item:
            self._set_status(f"Не удалось найти ГМ по запросу: «{raw}»", "#FF5252")
            return

        code = item.get("Код", "").strip()
        gm_name = item.get("Название", code)
        target = build_target(code)

        if not target:
            self._set_status("Не удалось сформировать цель подключения.", "#FF5252")
            return

        password = self._load_password()
        if not password:
            self._set_status(
                "Пароль не задан. Нажмите «Сменить пароль», чтобы указать его.",
                "#FFD700"
            )
            return

        self._set_status(f"Подключение к {target}...", "#FFD700")

        ok, err = self._save_credentials(target, password)
        if not ok:
            self._set_status(f"Ошибка сохранения учётных данных: {err}", "#FF5252")
            return

        ok, err = self._launch_mstsc(target)
        if not ok:
            self._set_status(f"Ошибка запуска mstsc: {err}", "#FF5252")
            return

        self._set_status(f"Терминал запущен для ГМ {gm_name}", "#4CAF50")

    def _save_credentials(self, target, password):
        user = os.environ.get("USERNAME", "")
        domain = os.environ.get("USERDOMAIN", "")

        if domain and domain.upper() not in ("WORKGROUP", "WORKGROUP."):
            full_user = f"{domain}\\{user}"
        else:
            full_user = user

        try:
            result = subprocess.run(
                [
                    "cmdkey",
                    f"/generic:TERMSRV/{target}",
                    f"/user:{full_user}",
                    f"/pass:{password}",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            if result.returncode != 0:
                return False, (result.stderr or result.stdout or "Неизвестная ошибка").strip()
            return True, ""
        except subprocess.TimeoutExpired:
            return False, "cmdkey не ответил за 15 секунд."
        except Exception as e:
            return False, str(e)

    def _launch_mstsc(self, target):
        try:
            subprocess.Popen(
                ["mstsc", f"/v:{target}"],
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            return True, ""
        except Exception as e:
            return False, str(e)

    # =========================================================
    # СМЕНА ПАРОЛЯ
    # =========================================================
    def _on_change_password(self):
        new_password = ask_password(self)
        if not new_password:
            return

        self._save_password(new_password)
        self._set_status("Пароль обновлён.", "#4CAF50")
        log.info("TerminalFrame: пароль обновлён")

    def _load_password(self):
        try:
            token = self._settings.value("terminal_password", "")
            if not token:
                return ""
            return xor_decrypt(token, self._password_key)
        except Exception as e:
            log.warning(f"TerminalFrame: ошибка загрузки пароля: {e}")
            return ""

    def _save_password(self, password):
        try:
            token = xor_encrypt(password, self._password_key)
            self._settings.setValue("terminal_password", token)
            log.info("TerminalFrame: пароль сохранён (зашифрован)")
        except Exception as e:
            log.exception(f"TerminalFrame: ошибка сохранения пароля: {e}")

    # =========================================================
    # СТАТУС И REFRESH
    # =========================================================
    def _set_status(self, text, color=None):
        self.status_label.setText(text)
        if color:
            self.status_label.setStyleSheet(f"color: {color};")

    def refresh(self):
        self._gm_data = self._load_gm_data()
        self._attach_completer(self._gm_data)