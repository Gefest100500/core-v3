# ui/components/wizard_dialog.py
"""
Мастер первого запуска Core V3.0.
Пошаговый интерфейс для первоначальной настройки.
"""
import os
from PyQt6.QtCore import Qt, QSettings, QPoint
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QFileDialog, QStackedWidget, QWidget
)

from ui.icons import get_icon_simple
from ui.components.widgets import PrimaryButton, SecondaryButton, StyledCombo
from utils.logger import log
from core.terminal_helper import xor_encrypt, get_password_key


class WizardDialog(QDialog):
    def __init__(self, parent, colors, fonts):
        super().__init__(parent)
        self.colors = colors
        self.fonts = fonts
        self._settings = QSettings("SilchenkoAleksey", "CoreV3")
        
        # Безрамочное окно
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(600, 450)
        self.setModal(True)
        
        self._drag_pos = None
        self._setup_ui()

    def _setup_ui(self):
        # Основной контейнер
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("WizardFrame")
        self.main_frame.setStyleSheet(f"""
            QFrame#WizardFrame {{
                background-color: {self.colors.get('bg', '#1B1B1B')};
                border: 1px solid {self.colors.get('border', '#333333')};
                border-radius: 12px;
            }}
        """)
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.main_frame)

        layout = QVBoxLayout(self.main_frame)
        layout.setContentsMargins(0, 0, 0, 20)
        layout.setSpacing(0)

        # --- КАСТОМНАЯ ШАПКА ---
        header = QFrame()
        header.setFixedHeight(40)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors.get('card', '#222222')};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid {self.colors.get('border', '#333333')};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 0, 10, 0)
        
        title = QLabel("МАСТЕР НАСТРОЙКИ")
        title.setFont(self.fonts['subtitle'])
        title.setStyleSheet(f"color: {self.colors.get('text', '#E0E0E0')}; border: none;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        btn_close_x = QPushButton("✕")
        btn_close_x.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close_x.setFixedSize(24, 24)
        btn_close_x.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {self.colors.get('text_dim', '#A0A0A0')};
                border: none;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {self.colors.get('error', '#FF5252')};
            }}
        """)
        btn_close_x.clicked.connect(self.reject)
        header_layout.addWidget(btn_close_x)
        
        layout.addWidget(header)
        
        # --- КОНТЕНТ (Стек страниц) ---
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        layout.addWidget(self.stack, 1)

        self._build_page_welcome()
        self._build_page_email()
        self._build_page_folder()
        self._build_page_days()
        self._build_page_terminal()
        self._build_page_finish()

        # --- НИЖНЯЯ ПАНЕЛЬ С КНОПКАМИ ---
        footer = QFrame()
        footer.setStyleSheet("background: transparent; border: none;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 0)
        
        self.btn_back = SecondaryButton("Назад", on_click=self._go_back, parent=footer)
        self.btn_back.setFixedWidth(120)
        self.btn_back.setMinimumHeight(40)
        self.btn_back.hide()
        footer_layout.addWidget(self.btn_back)
        
        footer_layout.addStretch()
        
        self.btn_next = PrimaryButton("Далее", on_click=self._go_next, parent=footer)
        self.btn_next.setFixedWidth(120)
        self.btn_next.setMinimumHeight(40)
        footer_layout.addWidget(self.btn_next)
        
        layout.addWidget(footer)

        # Текущая страница
        self.current_page = 0
        self._update_buttons()

    # --- СТРАНИЦЫ ---
    def _build_page_welcome(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(15)
        
        icon_lbl = QLabel()
        icon = get_icon_simple("info", color=self.colors.get('button', '#D42626'), size=64)
        if not icon.isNull():
            icon_lbl.setPixmap(icon.pixmap(64, 64))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)
        
        title = QLabel("Добро пожаловать в Core V3.0!")
        title.setFont(self.fonts['title'])
        title.setStyleSheet(f"color: {self.colors.get('text', '#E0E0E0')};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        desc = QLabel("Давайте быстро настроим программу для вашей работы.\nЭто займёт не больше минуты.")
        desc.setFont(self.fonts['label'])
        desc.setStyleSheet(f"color: {self.colors.get('text_dim', '#A0A0A0')};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        
        self.stack.addWidget(page)

    def _build_page_email(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        title = QLabel("Корпоративная почта")
        title.setFont(self.fonts['subtitle'])
        title.setStyleSheet(f"color: {self.colors.get('text', '#E0E0E0')};")
        layout.addWidget(title)
        
        desc = QLabel("Укажите ваш адрес корпоративной почты. На него будут приходить отчёты, а оттуда — логи программы.")
        desc.setFont(self.fonts['small'])
        desc.setStyleSheet(f"color: {self.colors.get('text_dim', '#A0A0A0')};")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        self.input_email = QLineEdit()
        self.input_email.setPlaceholderText("example@magnit.ru")
        self.input_email.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.colors.get('card', '#222222')};
                color: {self.colors.get('text', '#E0E0E0')};
                border: 1px solid {self.colors.get('border', '#333333')};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors.get('button', '#D42626')};
            }}
        """)
        layout.addWidget(self.input_email)
        
        layout.addStretch()
        self.stack.addWidget(page)

    def _build_page_folder(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        title = QLabel("Папка для данных")
        title.setFont(self.fonts['subtitle'])
        title.setStyleSheet(f"color: {self.colors.get('text', '#E0E0E0')};")
        layout.addWidget(title)
        
        desc = QLabel("Где программа будет хранить отчёты, архив и кэш?\nПо умолчанию используется папка рядом с программой.")
        desc.setFont(self.fonts['small'])
        desc.setStyleSheet(f"color: {self.colors.get('text_dim', '#A0A0A0')};")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        row = QHBoxLayout()
        self.input_folder = QLineEdit()
        self.input_folder.setText(os.path.join(os.getcwd(), "data"))
        self.input_folder.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.colors.get('card', '#222222')};
                color: {self.colors.get('text', '#E0E0E0')};
                border: 1px solid {self.colors.get('border', '#333333')};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }}
        """)
        row.addWidget(self.input_folder, 1)
        
        btn_browse = SecondaryButton("Обзор...", on_click=self._browse_folder, parent=page)
        btn_browse.setFixedWidth(100)
        row.addWidget(btn_browse)
        
        layout.addLayout(row)
        layout.addStretch()
        self.stack.addWidget(page)

    def _build_page_days(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        title = QLabel("Глубина поиска почты")
        title.setFont(self.fonts['subtitle'])
        title.setStyleSheet(f"color: {self.colors.get('text', '#E0E0E0')};")
        layout.addWidget(title)
        
        desc = QLabel("За какой период программа должна загружать письма из Outlook при запуске?\nЭто влияет на скорость запуска.")
        desc.setFont(self.fonts['small'])
        desc.setStyleSheet(f"color: {self.colors.get('text_dim', '#A0A0A0')};")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        self.combo_days = StyledCombo(
            items=["7 дней", "14 дней", "30 дней", "Вся почта"],
            parent=page
        )
        self.combo_days.setFixedWidth(250)
        layout.addWidget(self.combo_days)
        
        layout.addStretch()
        self.stack.addWidget(page)

    def _build_page_terminal(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        title = QLabel("Пароль для терминала")
        title.setFont(self.fonts['subtitle'])
        title.setStyleSheet(f"color: {self.colors.get('text', '#E0E0E0')};")
        layout.addWidget(title)
        
        desc = QLabel("Укажите пароль для подключения к удалённым рабочим столам (mstsc).\nОн сохранится в зашифрованном виде.")
        desc.setFont(self.fonts['small'])
        desc.setStyleSheet(f"color: {self.colors.get('text_dim', '#A0A0A0')};")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_password.setPlaceholderText("Введите пароль...")
        self.input_password.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.colors.get('card', '#222222')};
                color: {self.colors.get('text', '#E0E0E0')};
                border: 1px solid {self.colors.get('border', '#333333')};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors.get('button', '#D42626')};
            }}
        """)
        layout.addWidget(self.input_password)
        
        layout.addStretch()
        self.stack.addWidget(page)

    def _build_page_finish(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(15)
        
        icon_lbl = QLabel()
        icon = get_icon_simple("check", color=self.colors.get('success', '#4CAF50'), size=64)
        if not icon.isNull():
            icon_lbl.setPixmap(icon.pixmap(64, 64))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)
        
        title = QLabel("Всё готово!")
        title.setFont(self.fonts['title'])
        title.setStyleSheet(f"color: {self.colors.get('text', '#E0E0E0')};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        desc = QLabel("Настройки сохранены. Программа готова к работе.")
        desc.setFont(self.fonts['label'])
        desc.setStyleSheet(f"color: {self.colors.get('text_dim', '#A0A0A0')};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        
        self.stack.addWidget(page)

    # --- ЛОГИКА ---
    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для данных")
        if folder:
            self.input_folder.setText(folder)

    def _go_next(self):
        if self.current_page == 5: # Последняя страница (теперь их 6, индексы 0..5)
            self._save_settings()
            self.accept()
            return
            
        self.current_page += 1
        self.stack.setCurrentIndex(self.current_page)
        self._update_buttons()

    def _go_back(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.stack.setCurrentIndex(self.current_page)
            self._update_buttons()

    def _update_buttons(self):
        if self.current_page == 0:
            self.btn_back.hide()
        else:
            self.btn_back.show()
            
        if self.current_page == 5:
            self.btn_next.setText("Завершить")
        else:
            self.btn_next.setText("Далее")

    def _save_settings(self):
        email = self.input_email.text().strip()
        folder = self.input_folder.text().strip()
        days_text = self.combo_days.currentText()
        password = self.input_password.text()
        
        if days_text == "7 дней": days_val = "7"
        elif days_text == "14 дней": days_val = "14"
        elif days_text == "30 дней": days_val = "30"
        else: days_val = "all"

        self._settings.setValue("user_email", email)
        self._settings.setValue("data_folder", folder)
        self._settings.setValue("email_days_back", days_val)
        
        # Сохраняем пароль для терминала (в зашифрованном виде)
        if password:
            key = get_password_key()
            token = xor_encrypt(password, key)
            self._settings.setValue("terminal_password", token)
        
        # Ставим флаг, что мастер пройден
        self._settings.setValue("wizard_completed", "true")
        
        log.info(f"Мастер настройки завершен: email={email}, folder={folder}, days={days_val}, password={'да' if password else 'нет'}")

    # --- Перетаскивание ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        event.accept()