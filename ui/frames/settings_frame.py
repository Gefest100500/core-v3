# ui/frames/settings_frame.py
"""
Вкладка настроек.
"""
import os
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox, QWidget,
    QFileDialog, QPushButton, QLineEdit
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton, StyledCombo
)
from ui.icons import get_icon_simple
from ui.components.test_dialog import TestDialog
from utils.logger import log
from core.terminal_helper import xor_encrypt, xor_decrypt, get_password_key


class SettingsFrame(BaseFrame):
    TITLE = "Настройки"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)
        self._settings = QSettings("SilchenkoAleksey", "CoreV3")
        self._password_key = get_password_key()
        self._setup_ui()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        # Заголовок
        title = QLabel("НАСТРОЙКИ", self)
        title.setFont(self.FONTS['title'])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # --- Карточка 1: Почта (Outlook) ---
        card_mail = create_card(self)
        card_mail.layout().addWidget(self._make_label("Почта (Outlook)"))
        
        # Корпоративная почта
        row_email = QHBoxLayout()
        row_email.setSpacing(10)
        row_email.addWidget(self._make_label("Корпоративная почта:"))
        
        self.input_email = QLineEdit()
        self.input_email.setPlaceholderText("example@magnit.ru")
        self.input_email.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.COLORS.get('card', '#222222')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.COLORS.get('button', '#D42626')};
            }}
        """)
        self.input_email.setFixedWidth(300)
        saved_email = self._settings.value("user_email", "")
        self.input_email.setText(str(saved_email))
        
        row_email.addWidget(self.input_email)
        row_email.addStretch()
        card_mail.layout().addLayout(row_email)

        # Глубина поиска
        row_days = QHBoxLayout()
        row_days.setSpacing(10)
        row_days.addWidget(self._make_label("Глубина поиска писем:"))
        
        self.combo_days = StyledCombo(
            items=["7 дней", "14 дней", "30 дней", "Вся почта"],
            parent=card_mail
        )
        self.combo_days.setFixedWidth(200)
        
        val = self._settings.value("email_days_back", "7")
        if val == "7": self.combo_days.setCurrentText("7 дней")
        elif val == "14": self.combo_days.setCurrentText("14 дней")
        elif val == "30": self.combo_days.setCurrentText("30 дней")
        else: self.combo_days.setCurrentText("Вся почта")
        
        row_days.addWidget(self.combo_days)
        row_days.addStretch()
        card_mail.layout().addLayout(row_days)

        hint = QLabel(
            "При запуске программа будет загружать письма только за указанный период.",
            card_mail
        )
        hint.setFont(self.FONTS['small'])
        hint.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        hint.setWordWrap(True)
        card_mail.layout().addWidget(hint)

        root_layout.addWidget(card_mail)

        # --- Карточка 2: Папки и Терминал ---
        card_folders = create_card(self)
        card_folders.layout().addWidget(self._make_label("Папки"))
        
        # Путь для отчетов
        row_reports = QHBoxLayout()
        row_reports.setSpacing(10)
        row_reports.addWidget(self._make_label("Папка для отчётов:"))
        
        self.lbl_reports_path = QLabel("Не выбрана", card_folders)
        self.lbl_reports_path.setFont(self.FONTS['small'])
        self.lbl_reports_path.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        self.lbl_reports_path.setWordWrap(True)
        row_reports.addWidget(self.lbl_reports_path, 1)
        
        btn_browse = SecondaryButton("Выбрать...", on_click=self._choose_reports_folder, parent=card_folders)
        btn_browse.setFixedWidth(120)
        row_reports.addWidget(btn_browse)
        
        card_folders.layout().addLayout(row_reports)
        reports_path = self._settings.value("reports_folder", "")
        if reports_path and os.path.isdir(reports_path):
            self.lbl_reports_path.setText(reports_path)
        
        # Пароль терминала
        card_folders.layout().addSpacing(10)
        card_folders.layout().addWidget(self._make_label("Пароль терминала (mstsc)"))
        row_pass = QHBoxLayout()
        row_pass.setSpacing(10)
        
        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_password.setPlaceholderText("Введите новый пароль (оставьте пустым, чтобы не менять)")
        self.input_password.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.COLORS.get('card', '#222222')};
                color: {self.COLORS.get('text', '#E0E0E0')};
                border: 1px solid {self.COLORS.get('border', '#333333')};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.COLORS.get('button', '#D42626')};
            }}
        """)
        self.input_password.setFixedWidth(300)
        row_pass.addWidget(self.input_password)
        row_pass.addStretch()
        card_folders.layout().addLayout(row_pass)
        
        root_layout.addWidget(card_folders)

        # --- Карточка 3: Диагностика ---
        card_diag = create_card(self)
        card_diag.layout().addWidget(self._make_label("Диагностика"))
        
        hint_diag = QLabel(
            "Проверка подключений к Outlook, папкам и почте.",
            card_diag
        )
        hint_diag.setFont(self.FONTS['small'])
        hint_diag.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        hint_diag.setWordWrap(True)
        card_diag.layout().addWidget(hint_diag)
        
        btn_row_diag = QHBoxLayout()
        btn_row_diag.setSpacing(10)
        
        btn_test = PrimaryButton("Тест подключений", on_click=self._run_test, parent=card_diag)
        btn_test.setFixedWidth(200)
        btn_test.setMinimumHeight(40)
        btn_row_diag.addWidget(btn_test)
        
        btn_send_log = SecondaryButton("Отправить лог", on_click=self._send_log, parent=card_diag)
        btn_send_log.setFixedWidth(200)
        btn_send_log.setMinimumHeight(40)
        btn_row_diag.addWidget(btn_send_log)
        
        btn_row_diag.addStretch()
        card_diag.layout().addLayout(btn_row_diag)
        
        root_layout.addWidget(card_diag)

        # --- Кнопка "Сохранить" (общая) ---
        btn_save = PrimaryButton(
            "Сохранить настройки",
            on_click=self._save_settings,
            parent=self
        )
        btn_save.setFixedWidth(250)
        btn_save.setMinimumHeight(45)
        
        btn_row_save = QHBoxLayout()
        btn_row_save.addStretch()
        btn_row_save.addWidget(btn_save)
        btn_row_save.addStretch()
        root_layout.addLayout(btn_row_save)

        root_layout.addStretch()

    def _make_label(self, text):
        lbl = QLabel(text, self)
        lbl.setFont(self.FONTS['subtitle'])
        return lbl

    def _choose_reports_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для отчётов")
        if folder:
            self.lbl_reports_path.setText(folder)
            self._settings.setValue("reports_folder", folder)
            log.info(f"Папка для отчетов изменена: {folder}")

    def _run_test(self):
        results = []
        
        outlook_app = None
        try:
            import win32com.client
            outlook_app = win32com.client.Dispatch("Outlook.Application")
            results.append({"title": "Outlook", "status": "success", "message": "Подключение установлено"})
        except Exception as e:
            results.append({"title": "Outlook", "status": "error", "message": f"Ошибка: {str(e)[:50]}"})

        reports_path = self._settings.value("reports_folder", "")
        if reports_path and os.path.isdir(reports_path):
            results.append({"title": "Папка отчётов", "status": "success", "message": reports_path})
        else:
            results.append({"title": "Папка отчётов", "status": "error", "message": "Путь не задан или папка не существует"})

        try:
            from config import get_config
            folders = get_config().init_folders()
            missing = [key for key, path in folders.items() if not os.path.isdir(path)]
            if missing:
                results.append({"title": "Системные папки", "status": "error", "message": f"Не найдены: {', '.join(missing)}"})
            else:
                results.append({"title": "Системные папки", "status": "success", "message": "Все папки на месте"})
        except Exception as e:
            results.append({"title": "Системные папки", "status": "info", "message": f"Ошибка проверки: {e}"})

        if outlook_app is not None:
            try:
                namespace = outlook_app.GetNamespace("MAPI")
                inbox = namespace.GetDefaultFolder(6)
                item_count = inbox.Items.Count
                results.append({"title": "Корпоративная почта", "status": "success", "message": f"Доступ к ящику есть (писем: {item_count})"})
            except Exception as e:
                results.append({"title": "Корпоративная почта", "status": "error", "message": f"Нет доступа к ящику: {str(e)[:50]}"})
        else:
            results.append({"title": "Корпоративная почта", "status": "info", "message": "Пропущено (Outlook не запущен)"})

        dialog = TestDialog(self, self.COLORS, self.FONTS, results)
        dialog.exec()

    def _send_log(self):
        self.show_success("Лог", "Отправка лога будет реализована в ближайшее время.")

    def _save_settings(self):
        # Сохраняем почту
        email = self.input_email.text().strip()
        self._settings.setValue("user_email", email)

        # Сохраняем глубину поиска
        text = self.combo_days.currentText()
        if text == "7 дней": val = "7"
        elif text == "14 дней": val = "14"
        elif text == "30 дней": val = "30"
        else: val = "all"
        self._settings.setValue("email_days_back", val)

        # Сохраняем пароль терминала (если введен)
        new_pass = self.input_password.text()
        if new_pass:
            token = xor_encrypt(new_pass, self._password_key)
            self._settings.setValue("terminal_password", token)
            self.input_password.clear() # Очищаем поле после сохранения

        self.show_success("Настройки", "Настройки сохранены. Изменения вступят в силу при следующем запуске.")

    def refresh(self):
        saved_email = self._settings.value("user_email", "")
        self.input_email.setText(str(saved_email))