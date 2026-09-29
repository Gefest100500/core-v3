# ui/icons.py
"""
Загрузчик SVG-иконок для Core.

Читает SVG из ui/icons/, красит в нужный цвет, возвращает QIcon.
Поддерживает состояния:
- Normal (обычное) — серый
- Active (hover) — светлый
- Selected (активное) — белый

PyQt сам выбирает состояние в зависимости от контекста.
"""
import os

from PyQt6.QtCore import QSize, Qt, QByteArray
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer

from utils.logger import log


ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


# Цвета состояний
COLOR_NORMAL = "#A0A0A0"
COLOR_HOVER = "#E0E0E0"
COLOR_ACTIVE = "#FFFFFF"

# Кэш: (name, size) → QIcon
_icon_cache = {}


def _render_svg(name: str, color: str, size: int) -> QPixmap:
    """Рендерит SVG в QPixmap указанного цвета и размера."""
    svg_path = os.path.join(ICONS_DIR, f"{name}.svg")
    if not os.path.isfile(svg_path):
        log.warning(f"Иконка не найдена: {svg_path}")
        return QPixmap()

    try:
        with open(svg_path, "r", encoding="utf-8") as f:
            svg_data = f.read()
    except IOError as e:
        log.error(f"Не удалось прочитать {svg_path}: {e}")
        return QPixmap()

    svg_data = svg_data.replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return pixmap


def get_icon(name: str, size: int = 24) -> QIcon:
    """Возвращает QIcon с 3 состояниями (Normal/Active/Selected).

    Args:
        name: имя файла без .svg (например 'home')
        size: размер стороны иконки в пикселях

    Returns:
        QIcon с состояниями или пустой QIcon (если файл не найден)
    """
    cache_key = (name, size)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    icon = QIcon()
    icon.addPixmap(_render_svg(name, COLOR_NORMAL, size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_render_svg(name, COLOR_HOVER, size), QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(_render_svg(name, COLOR_ACTIVE, size), QIcon.Mode.Selected, QIcon.State.Off)

    _icon_cache[cache_key] = icon
    return icon


def get_icon_simple(name: str, color: str = COLOR_NORMAL, size: int = 24) -> QIcon:
    """Возвращает QIcon в одном цвете (для нестандартных случаев)."""
    pixmap = _render_svg(name, color, size)
    return QIcon(pixmap)


def clear_cache():
    """Очищает кэш иконок."""
    _icon_cache.clear()