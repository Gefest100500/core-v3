# ui/frames/tsd_frame.py
import io
import json
import os
import re
import qrcode

from PyQt6.QtCore import Qt, QSize, QStringListModel
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QCompleter

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton,
    AnimatedPlaceholderEntry, style_popup,
)
from ui.icons import get_icon_simple
from utils.file_utils import get_data_dir
from utils.logger import log


class TsdFrame(BaseFrame):
    TITLE = "ТСД"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)
        self._gm_ip = self._load_gm_ip()
        self._gm_data = self._load_gm_data()
        self._completer = None
        self._completer_activated = None
        self._setup_ui()

    # =========================================================
    # ЗАГРУЗКА ДАННЫХ
    # =========================================================
    def _load_gm_ip(self) -> dict:
        path = os.path.join(get_data_dir(), "gm_ip.json")
        if not os.path.exists(path):
            log.warning(f"TsdFrame: gm_ip.json не найден: {path}")
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            log.info(f"TsdFrame: загружено {len(data)} IP-адресов ГМ")
            return data
        except Exception as e:
            log.exception(f"TsdFrame: ошибка чтения gm_ip.json: {e}")
            return {}

    def _load_gm_data(self) -> list:
        path = os.path.join(get_data_dir(), "gm_data.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        # --- Кнопка «Назад в утилиты» ---
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

        title = QLabel("Генератор QR-кодов для ТСД", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        info = QLabel(
            "Введите код ГМ и номер ТСД — и отсканируйте QR-код терминалом.",
            self
        )
        info.setFont(self.FONTS['small'])
        info.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(info)

        card = create_card(self)

        # --- Код ГМ ---
        row_gm = QHBoxLayout()
        lbl_gm = QLabel("Код ГМ:", card)
        lbl_gm.setFont(self.FONTS['label'])
        lbl_gm.setFixedWidth(120)
        row_gm.addWidget(lbl_gm)

        self.entry_gm = AnimatedPlaceholderEntry(
            placeholder="например: 996411", parent=card
        )
        self.entry_gm.setMinimumHeight(40)
        self.entry_gm.textChanged.connect(self._on_gm_changed)
        row_gm.addWidget(self.entry_gm, 1)
        card.layout().addLayout(row_gm)

        # --- Название ГМ ---
        self.lbl_gm_name = QLabel("", card)
        self.lbl_gm_name.setFont(self.FONTS['small'])
        self.lbl_gm_name.setStyleSheet(
            f"color: {self.COLORS.get('text_dim', '#A0A0A0')};"
        )
        self.lbl_gm_name.setMinimumHeight(20)
        card.layout().addWidget(self.lbl_gm_name)

        # --- Номер ТСД ---
        row_tsd = QHBoxLayout()
        lbl_tsd = QLabel("Номер ТСД:", card)
        lbl_tsd.setFont(self.FONTS['label'])
        lbl_tsd.setFixedWidth(120)
        row_tsd.addWidget(lbl_tsd)

        self.entry_tsd = AnimatedPlaceholderEntry(
            placeholder="например: 50", parent=card
        )
        self.entry_tsd.setMinimumHeight(40)
        self.entry_tsd.returnPressed.connect(self._generate_qr)
        row_tsd.addWidget(self.entry_tsd, 1)
        card.layout().addLayout(row_tsd)

        # --- Кнопка ---
        self.btn_generate = PrimaryButton(
            "Сгенерировать QR", on_click=self._generate_qr, parent=card
        )
        self.btn_generate.setMinimumHeight(46)

        icon = get_icon_simple("tsd", color="#FFFFFF", size=20)
        if not icon.isNull():
            self.btn_generate.setIcon(icon)
            self.btn_generate.setIconSize(QSize(20, 20))

        card.layout().addWidget(self.btn_generate)

        # --- QR ---
        self.qr_label = QLabel(card)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumHeight(320)
        self.qr_label.setStyleSheet(
            "background-color: #1B1B1B; border-radius: 8px;"
        )
        card.layout().addWidget(self.qr_label)

        root_layout.addWidget(card)
        root_layout.addStretch()

        self._attach_completer()

    # =========================================================
    # АВТОДОПОЛНЕНИЕ
    # =========================================================
    def _attach_completer(self):
        if not self._gm_data:
            return

        items = []
        for gm in self._gm_data:
            code = str(gm.get("Код", "")).strip()
            name = gm.get("Название", "")
            if code:
                items.append(f"{code} — {name}")
        if not items:
            return

        try:
            if self._completer is not None:
                try:
                    self._completer.activated.disconnect(self._completer_activated)
                except (TypeError, RuntimeError):
                    pass
                self.entry_gm.setCompleter(None)
        except RuntimeError:
            pass

        self._completer = None
        self._completer_activated = None

        model = QStringListModel(items, self.entry_gm)
        completer = QCompleter(model, self.entry_gm)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(15)

        style_popup(completer)
        self.entry_gm.setCompleter(completer)
        self._completer = completer

        def _on_activated(text):
            match = re.search(r'\b(\d{6})\b', text)
            self.entry_gm.setText(match.group(1) if match else text)

        self._completer_activated = _on_activated
        completer.activated.connect(_on_activated)

        def _on_text_edited(text):
            try:
                if self._completer is None:
                    return
                if not text:
                    self._completer.popup().hide()
                    return
                self._completer.setCompletionPrefix(text)
                if self._completer.completionCount() > 0:
                    self._completer.complete()
                else:
                    self._completer.popup().hide()
            except RuntimeError:
                pass

        self.entry_gm.textEdited.connect(_on_text_edited)

    # =========================================================
    # ОБНОВЛЕНИЕ НАЗВАНИЯ
    # =========================================================
    def _on_gm_changed(self, text):
        match = re.search(r"\b(\d{6})\b", text)
        if not match:
            self.lbl_gm_name.setText("")
            return
        code = match.group(1)
        ip = self._gm_ip.get(code, "")
        name = self._find_gm_name(code)

        if ip:
            server_ip = self._build_server_ip(ip)
            display = name or code
            self.lbl_gm_name.setText(f"✓ {display} (сервер: {server_ip})")
            self.lbl_gm_name.setStyleSheet(
                f"color: {self.COLORS.get('text', '#E0E0E0')};"
            )
        else:
            self.lbl_gm_name.setText("✗ Код ГМ не найден в справочнике IP")
            self.lbl_gm_name.setStyleSheet(
                f"color: {self.COLORS.get('error', '#FF5252')};"
            )

    def _find_gm_name(self, code: str) -> str:
        for gm in self._gm_data:
            if str(gm.get("Код", "")).strip() == code:
                return gm.get("Название", "")
        return ""

    @staticmethod
    def _build_server_ip(gm_ip: str) -> str:
        parts = gm_ip.split(".")
        if len(parts) != 4:
            return gm_ip
        parts[-1] = "5"
        return ".".join(parts)

    # =========================================================
    # ГЕНЕРАЦИЯ QR
    # =========================================================
    def _generate_qr(self):
        raw_gm = self.entry_gm.text().strip()
        tsd_num = self.entry_tsd.text().strip()

        match = re.search(r"\b(\d{6})\b", raw_gm)
        if not match:
            self.qr_label.setText("Введите код ГМ (6 цифр)")
            return

        gm_code = match.group(1)
        if not tsd_num:
            self.qr_label.setText("Введите номер ТСД")
            return

        gm_ip = self._gm_ip.get(gm_code)
        if not gm_ip:
            self.qr_label.setText(f"Код ГМ {gm_code} не найден в справочнике IP")
            return

        server_ip = self._build_server_ip(gm_ip)
        base_url = f"http://{server_ip}:8081/hms/iface/login"

        payload = (
            f"M0difWHYConf1g$???server_address==={base_url}"
            f"&&&terminal_number==={tsd_num}"
            f"&&&is_dc===true&&&is_alt_scan===true"
        )

        try:
            qr = qrcode.QRCode(
                box_size=10,
                border=4,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
            )
            qr.add_data(payload)
            qr.make(fit=True)

            img = qr.make_image(
                fill_color="#000000",
                back_color="#FFFFFF",
            )

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            qimage = QImage()
            qimage.loadFromData(buffer.getvalue())
            pixmap = QPixmap.fromImage(qimage)
            pixmap = pixmap.scaled(
                300, 300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self.qr_label.setPixmap(pixmap)
            self.qr_label.setStyleSheet("background-color: transparent;")

            log.info(f"TsdFrame: QR для ГМ {gm_code}, ТСД {tsd_num}")

        except Exception as e:
            self.qr_label.setText(f"Ошибка: {e}")
            log.exception(f"TsdFrame: ошибка генерации QR: {e}")