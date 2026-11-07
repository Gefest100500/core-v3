# ui/components/test_dialog.py
"""
Диалоговое окно для отображения результатов комплексного теста подключений.
Показывает чек-лист с иконками статусов.
"""
from PyQt6.QtCore import Qt, QSize, QPoint
from PyQt6.QtGui import QFont, QMouseEvent
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QWidget, QSizePolicy
)

from ui.icons import get_icon_simple
from ui.components.widgets import PrimaryButton


class TestDialog(QDialog):
    def __init__(self, parent, colors, fonts, results):
        """
        :param results: Список словарей вида:
            [
                {"title": "Outlook", "status": "success", "message": "Подключено"},
                {"title": "Папка данных", "status": "error", "message": "Не найдена"},
                {"title": "Тест почты", "status": "info", "message": "Пропущено"},
            ]
        """
        super().__init__(parent)
        self.colors = colors
        self.fonts = fonts
        self.results = results
        
        # Убираем стандартную рамку окна
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.resize(500, 450)
        self.setModal(True)
        self._setup_ui()
        
        self._drag_pos = None

    def _setup_ui(self):
        # Основной контейнер (фон)
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("DialogFrame")
        self.main_frame.setStyleSheet(f"""
            QFrame#DialogFrame {{
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
        
        title = QLabel("РЕЗУЛЬТАТЫ ПРОВЕРКИ")
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
        
        # --- КОНТЕНТ ---
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 15, 20, 0)
        
        # Скролл для списка (если проверок будет много)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        # Скрываем некрасивый скроллбар
        scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_content_layout = QVBoxLayout(scroll_content)
        scroll_content_layout.setContentsMargins(0, 0, 0, 0)
        scroll_content_layout.setSpacing(8)

        # Рисуем каждый пункт
        for item in self.results:
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background-color: {self.colors.get('card', '#222222')};
                    border-radius: 6px;
                    border: 1px solid {self.colors.get('border', '#333333')};
                }}
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(12)

            # Иконка статуса
            icon_lbl = QLabel()
            icon_lbl.setFixedSize(24, 24)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            status = item.get("status", "info")
            if status == "success":
                icon = get_icon_simple("check", color=self.colors.get('success', '#4CAF50'), size=20)
            elif status == "error":
                icon = get_icon_simple("close", color=self.colors.get('error', '#FF5252'), size=20)
            else:
                icon = get_icon_simple("info", color=self.colors.get('text_dim', '#A0A0A0'), size=20)
                
            if not icon.isNull():
                icon_lbl.setPixmap(icon.pixmap(20, 20))
            row_layout.addWidget(icon_lbl)

            # Текст (Название + сообщение)
            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)
            
            title_lbl = QLabel(item.get("title", "Проверка"))
            title_lbl.setFont(self.fonts['label'])
            title_lbl.setStyleSheet(f"color: {self.colors.get('text', '#E0E0E0')}; border: none;")
            text_layout.addWidget(title_lbl)

            msg_lbl = QLabel(item.get("message", ""))
            msg_lbl.setFont(self.fonts['small'])
            msg_lbl.setStyleSheet(f"color: {self.colors.get('text_dim', '#A0A0A0')}; border: none;")
            msg_lbl.setWordWrap(True)
            text_layout.addWidget(msg_lbl)

            row_layout.addLayout(text_layout, 1)
            scroll_content_layout.addWidget(row)

        scroll_content_layout.addStretch()
        scroll.setWidget(scroll_content)
        content_layout.addWidget(scroll, 1)

        # Кнопка "Закрыть" внизу
        btn_row = QHBoxLayout()
        btn_close = PrimaryButton("Закрыть", on_click=self.accept, parent=self.main_frame)
        btn_close.setFixedWidth(150)
        btn_close.setMinimumHeight(40)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        content_layout.addLayout(btn_row)
        
        layout.addLayout(content_layout)

    # --- Перетаскивание окна за шапку ---
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