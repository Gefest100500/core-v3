# ui/frames/settings_frame.py
"""
Вкладка настроек.
"""
import os
from datetime import datetime
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox, QWidget,
    QFileDialog, QPushButton, QCheckBox
)

from ui.frames.base_frame import BaseFrame
from ui.components.widgets import (
    create_card, PrimaryButton, SecondaryButton, StyledCombo
)
from ui.icons import get_icon_simple
from ui.components.test_dialog import TestDialog
from utils.logger import log


class SettingsFrame(BaseFrame):
    TITLE = "Настройки"

    def __init__(self, parent, name=None):
        super().__init__(parent, name)
        self._settings = QSettings("SilchenkoAleksey", "CoreV3")
        self._setup_ui()
        self._check_auto_log()

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
        
        # Глубина поиска
        row_days = QHBoxLayout()
        row_days.setSpacing(10)
        row_days.addWidget(self._make_label("Глубина поиска писем:"))
        
        self.combo_days = StyledCombo(
            items=["7 дней", "14 дней", "30 дней", "Вся почта"],
            parent=card_mail
        )
        self.combo_days.setFixedWidth(200)
        
        # Загружаем сохраненное значение
        val = self._settings.value("email_days_back", "7")
        if val == "7": self.combo_days.setCurrentText("7 дней")
        elif val == "14": self.combo_days.setCurrentText("14 дней")
        elif val == "30": self.combo_days.setCurrentText("30 дней")
        else: self.combo_days.setCurrentText("Вся почта")
        
        row_days.addWidget(self.combo_days)
        row_days.addStretch()
        card_mail.layout().addLayout(row_days)

        hint = QLabel(
            "При запуске программа будет загружать письма только за указанный период. "
            "Это ускоряет запуск на машинах с большой почтой.",
            card_mail
        )
        hint.setFont(self.FONTS['small'])
        hint.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        hint.setWordWrap(True)
        card_mail.layout().addWidget(hint)

        root_layout.addWidget(card_mail)

        # --- Карточка 2: Папки ---
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
        
        # Загружаем сохраненный путь
        reports_path = self._settings.value("reports_folder", "")
        if reports_path and os.path.isdir(reports_path):
            self.lbl_reports_path.setText(reports_path)
        
        root_layout.addWidget(card_folders)

        # --- Карточка 3: Диагностика ---
        card_diag = create_card(self)
        card_diag.layout().addWidget(self._make_label("Диагностика"))
        
        hint_diag = QLabel(
            "Проверка подключений к Outlook, папкам и почте. "
            "Отправка лога помогает разработчику понять причину ошибки.",
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
        
        btn_send_log = SecondaryButton("Отправить лог", on_click=self._send_log_manual, parent=card_diag)
        btn_send_log.setFixedWidth(200)
        btn_send_log.setMinimumHeight(40)
        btn_row_diag.addWidget(btn_send_log)
        
        btn_row_diag.addStretch()
        card_diag.layout().addLayout(btn_row_diag)
        
        # Чекбокс автоотправки
        self.chk_auto_log = QCheckBox("Автоотправка лога раз в неделю")
        self.chk_auto_log.setFont(self.FONTS['small'])
        self.chk_auto_log.setStyleSheet(f"color: {self.COLORS.get('text', '#E0E0E0')};")
        
        # Загружаем настройку (по умолчанию включено)
        auto_val = self._settings.value("auto_log_enabled", "true")
        self.chk_auto_log.setChecked(auto_val == "true")
        self.chk_auto_log.stateChanged.connect(self._save_auto_log_setting)
        
        card_diag.layout().addWidget(self.chk_auto_log)
        
        root_layout.addWidget(card_diag)

        # --- Карточка 4: Другие настройки ---
        card_other = create_card(self)
        card_other.layout().addWidget(self._make_label("Другие настройки"))
        other_hint = QLabel("Здесь появятся настройки принтеров и т.д.", card_other)
        other_hint.setFont(self.FONTS['small'])
        other_hint.setStyleSheet(f"color: {self.COLORS.get('text_dim', '#A0A0A0')};")
        card_other.layout().addWidget(other_hint)
        root_layout.addWidget(card_other)

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

    def _save_auto_log_setting(self, state):
        val = "true" if state == 2 else "false" # 2 = Checked в PyQt6
        self._settings.setValue("auto_log_enabled", val)

    def _run_test(self):
        """Запускает комплексную проверку и показывает диалог."""
        results = []
        
        # 1. Проверка Outlook
        outlook_app = None
        try:
            import win32com.client
            outlook_app = win32com.client.Dispatch("Outlook.Application")
            results.append({"title": "Outlook", "status": "success", "message": "Подключение установлено"})
        except Exception as e:
            results.append({"title": "Outlook", "status": "error", "message": f"Ошибка: {str(e)[:50]}"})

        # 2. Проверка папки отчетов
        reports_path = self._settings.value("reports_folder", "")
        if reports_path and os.path.isdir(reports_path):
            results.append({"title": "Папка отчётов", "status": "success", "message": reports_path})
        else:
            results.append({"title": "Папка отчётов", "status": "error", "message": "Путь не задан или папка не существует"})

        # 3. Проверка доступных путей (из конфига)
        try:
            from config import get_config
            folders = get_config().init_folders()
            missing = []
            for key, path in folders.items():
                if not os.path.isdir(path):
                    missing.append(key)
            if missing:
                results.append({"title": "Системные папки", "status": "error", "message": f"Не найдены: {', '.join(missing)}"})
            else:
                results.append({"title": "Системные папки", "status": "success", "message": "Все папки на месте"})
        except Exception as e:
            results.append({"title": "Системные папки", "status": "info", "message": f"Ошибка проверки: {e}"})

        # 4. Проверка корпоративной почты (через Outlook)
        if outlook_app is not None:
            try:
                namespace = outlook_app.GetNamespace("MAPI")
                inbox = namespace.GetDefaultFolder(6)
                item_count = inbox.Items.Count
                results.append({
                    "title": "Корпоративная почта", 
                    "status": "success", 
                    "message": f"Доступ к ящику есть (писем: {item_count})"
                })
            except Exception as e:
                results.append({
                    "title": "Корпоративная почта", 
                    "status": "error", 
                    "message": f"Нет доступа к ящику: {str(e)[:50]}"
                })
        else:
            results.append({"title": "Корпоративная почта", "status": "info", "message": "Пропущено (Outlook не запущен)"})

        dialog = TestDialog(self, self.COLORS, self.FONTS, results)
        dialog.exec()

    def _send_log_manual(self):
        """Ручная отправка лога."""
        from core.log_sender import send_log_to_dev
        res = send_log_to_dev("Ручная отправка из настроек")
        if res.get("success"):
            self.show_success("Лог", f"Лог успешно отправлен!\nФайл: {os.path.basename(res['file'])}")
            # Обновляем дату последней отправки
            self._settings.setValue("last_log_sent", datetime.now().isoformat())
        else:
            self.show_error("Ошибка отправки", res.get("error", "Неизвестная ошибка"))

    def _check_auto_log(self):
        """Проверяет, нужно ли отправить лог автоматически."""
        auto_enabled = self._settings.value("auto_log_enabled", "true") == "true"
        if not auto_enabled:
            return
            
        last_sent = self._settings.value("last_log_sent", "")
        
        from core.log_sender import should_auto_send, send_log_to_dev
        if should_auto_send(last_sent):
            log.info("settings_frame: запуск автоотправки лога")
            # Делаем это с задержкой, чтобы не вешать UI при старте
            QTimer.singleShot(5000, self._do_auto_send)

    def _do_auto_send(self):
        from core.log_sender import send_log_to_dev
        res = send_log_to_dev("Автоматическая отправка (раз в неделю)")
        if res.get("success"):
            log.info("settings_frame: автоотправка лога успешна")
            self._settings.setValue("last_log_sent", datetime.now().isoformat())
        else:
            log.warning(f"settings_frame: автоотправка лога не удалась: {res.get('error')}")

    def _save_settings(self):
        text = self.combo_days.currentText()
        if text == "7 дней": val = "7"
        elif text == "14 дней": val = "14"
        elif text == "30 дней": val = "30"
        else: val = "all"
        
        self._settings.setValue("email_days_back", val)
        self.show_success("Настройки", "Настройки сохранены. Изменения вступят в силу при следующем запуске.")

    def refresh(self):
        pass