# ui/splash.py
"""
Заставка (SplashScreen) для Core V3.0.

- Тёмный фон, логотип «CORE», тонкий прогресс-бар, статус.
- Полноэкранная.
- Серая цветовая гамма (не красная).
- Плавное исчезновение (fade-out) при закрытии.
"""
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QFrame, QGraphicsOpacityEffect
)

from ui.icons import get_icon_simple


class SplashScreen(QWidget):
    """Заставка при старте приложения (во весь экран)."""

    def __init__(self, colors, fonts):
        super().__init__()
        self._colors = colors
        self._fonts = fonts

        # Полноэкранный режим, без рамки
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Эффект прозрачности для плавного исчезновения
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._setup_ui()
        self.showFullScreen()

    # =========================================================
    # UI
    # =========================================================
    def _setup_ui(self):
        bg = self._colors.get("bg", "#1B1B1B")
        text = self._colors.get("text", "#E0E0E0")
        text_dim = self._colors.get("text_dim", "#A0A0A0")

        # СЕРЫЙ цвет вместо красного
        accent = "#666666"
        accent_light = "#888888"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg};
            }}
            QFrame#SplashBorder {{
                background-color: {bg};
                border: none;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        frame = QFrame(self)
        frame.setObjectName("SplashBorder")
        outer.addWidget(frame)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(80, 80, 80, 80)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Логотип (иконка)
        logo_icon = get_icon_simple(
            "home", color=accent_light, size=96
        )
        logo_label = QLabel(frame)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not logo_icon.isNull():
            logo_label.setPixmap(logo_icon.pixmap(96, 96))
        layout.addWidget(logo_label)

        # Логотип (текст) — серый
        title = QLabel("CORE", frame)
        title.setFont(QFont("Segoe UI", 48, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {accent_light};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Корпоративный аудит", frame)
        subtitle.setFont(QFont("Segoe UI", 16))
        subtitle.setStyleSheet(f"color: {text_dim};")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(40)

        # Статус
        self.status_label = QLabel("Инициализация...", frame)
        self.status_label.setFont(QFont("Segoe UI", 13))
        self.status_label.setStyleSheet(f"color: {text};")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Прогресс-бар (тонкий, по центру)
        progress_container = QVBoxLayout()
        progress_container.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress = QProgressBar(frame)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setFixedWidth(400)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #2A2A2A;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {accent_light};
                border-radius: 2px;
            }}
        """)
        progress_container.addWidget(self.progress)
        layout.addLayout(progress_container)

    # =========================================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # =========================================================
    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_progress(self, value: int):
        self.progress.setValue(max(0, min(100, value)))

    def fade_out_and_close(self, on_finished=None):
        """Плавно скрывает заставку и закрывает её.

        Args:
            on_finished: callable, вызывается после завершения анимации.
        """
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(400)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _done():
            self.close()
            self.deleteLater()
            if on_finished:
                on_finished()

        self._anim.finished.connect(_done)
        self._anim.start()