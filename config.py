# config.py
"""
Конфигурация Core V3.0.

Цвета, шрифты, папки, пороги.

ВАЖНО:
- Никаких side-effect при импорте. Просто `import config` ничего
  не создаёт, не читает и не пишет.
- Всё — через класс Config. Экземпляр создаётся лениво через get_config().
- Шрифты создаются через QFont — вызывать get_fonts() ТОЛЬКО после QApplication.
- Обратная совместимость: FOLDERS, COLORS, BRAK_UTIL_TOLERANCE и др.
  доступны как module-level атрибуты через __getattr__.

ИЗМЕНЕНИЯ:
- Убрано поле email_folders. Поиск писем теперь всегда идёт
  во всех папках Входящих рекурсивно — без настройки имён папок.
- DATA_DIR теперь берётся из get_data_dir() (%LOCALAPPDATA%/Core_V3_0/data).
"""
import json
import os
from typing import Any, Dict, Optional

from PyQt6.QtGui import QFont

from utils.file_utils import get_base_dir, get_data_dir


# =========================================================
# ДЕФОЛТНЫЙ КОНФИГ
# =========================================================
DEFAULT_CONFIG: Dict[str, Any] = {
    "colors": {
        "bg": "#1B1B1B",
        "sidebar": "#2A2A2A",
        "card": "#222222",
        "text": "#E0E0E0",
        "text_dim": "#A0A0A0",
        "button": "#D42626",
        "hover": "#B71C1C",
        "success": "#4CAF50",
        "error": "#FF5252",
        "border": "#333333",
    },
    "fonts": {
        "title": ["Segoe UI", 20, "bold"],
        "subtitle": ["Segoe UI", 15, "bold"],
        "label": ["Segoe UI", 13, "normal"],
        "small": ["Segoe UI", 11, "normal"],
        "status": ["Consolas", 12, "bold"],
    },
    "loss_threshold": 1000,
    "box_deviation_pct": 50,
    "mirror_deviation_pct": 25,
    "brak_util": {
        "tolerance": 1.0,
    },
    "external": {
        "asus_url": "https://rao.corp.tander.ru/",
        "asus_home": "https://rao.corp.tander.ru/",
        "trip_url": "https://magnittravel.ru/Start",
        "trip_home": "https://magnittravel.ru/Start",
        "help_url": "https://help.corp.tander.ru/dwp/app/#/catalog",
        "help_home": "https://help.corp.tander.ru/dwp/app/#/catalog",
    },
}


# =========================================================
# КЛАСС CONFIG
# =========================================================
class Config:
    """Конфигурация приложения.

    Ленивая инициализация:
    - Папки создаются только при первом обращении к FOLDERS
      или при явном init_folders().
    - config.json читается при создании экземпляра.
    - Шрифты создаются только при вызове get_fonts().
    """

    def __init__(self, config_path: Optional[str] = None):
        # --- Пути (не создают папки) ---
        self.BASE_DIR = get_base_dir()
        self.DATA_DIR = get_data_dir()
        self.LOG_DIR = os.path.join(self.BASE_DIR, "Logs")
        self.INPUT_FOLDER = os.path.join(self.BASE_DIR, "Файлы")
        self.OUTPUT_FOLDER = os.path.join(self.BASE_DIR, "Готовые")
        self.TEMP_DIR = os.path.join(self.BASE_DIR, "temp")

        # --- config.json ---
        self.CONFIG_PATH = config_path or os.path.join(
            self.BASE_DIR, "config.json"
        )
        self.CONFIG_AUTO_CREATED = False

        self.CONFIG = self._load_config()

        # --- Извлечённые значения ---
        self.COLORS = self.CONFIG.get("colors", DEFAULT_CONFIG["colors"])
        self.FONTS_CFG = self.CONFIG.get("fonts", DEFAULT_CONFIG["fonts"])
        self.EXTERNAL = self.CONFIG.get("external", DEFAULT_CONFIG["external"])

        self.LOSS_THRESHOLD = self.CONFIG.get(
            "loss_threshold", DEFAULT_CONFIG["loss_threshold"]
        )
        self.BOX_DEVIATION_PCT = self.CONFIG.get(
            "box_deviation_pct", DEFAULT_CONFIG["box_deviation_pct"]
        )
        self.MIRROR_DEVIATION_PCT = self.CONFIG.get(
            "mirror_deviation_pct", DEFAULT_CONFIG["mirror_deviation_pct"]
        )
        self.BRAK_UTIL_TOLERANCE = self.CONFIG.get("brak_util", {}).get(
            "tolerance", DEFAULT_CONFIG["brak_util"]["tolerance"]
        )

        # --- FOLDERS: ленивый ---
        self._folders: Optional[Dict[str, str]] = None

    # =========================================================
    # ВНУТРЕННИЕ
    # =========================================================
    def _load_config(self) -> Dict[str, Any]:
        """Читает config.json. Создаёт дефолтный, если файла нет."""
        if not os.path.exists(self.CONFIG_PATH):
            self.CONFIG_AUTO_CREATED = True
            try:
                parent = os.path.dirname(self.CONFIG_PATH)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
            except (IOError, OSError):
                return dict(DEFAULT_CONFIG)

        try:
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, OSError):
            self.CONFIG_AUTO_CREATED = True
            return dict(DEFAULT_CONFIG)

    # =========================================================
    # FOLDERS — ЛЕНИВОЕ СОЗДАНИЕ
    # =========================================================
    @property
    def FOLDERS(self) -> Dict[str, str]:
        """Словарь путей результатов. Создаёт папки при первом обращении."""
        if self._folders is None:
            self._folders = self._init_folders()
        return self._folders

    def _init_folders(self) -> Dict[str, str]:
        """Создаёт все папки результатов и возвращает словарь путей."""
        folders = {
            "kv": os.path.join(self.OUTPUT_FOLDER, "Кванты"),
            "pal": os.path.join(self.OUTPUT_FOLDER, "Паллеты"),
            "os_mbp": os.path.join(self.OUTPUT_FOLDER, "ОС_МБП"),
            "brak_util": os.path.join(self.OUTPUT_FOLDER, "Брак_утиль"),
            "violations": os.path.join(self.OUTPUT_FOLDER, "Нарушения"),
            "pivot": os.path.join(self.OUTPUT_FOLDER, "Сводные"),
            "info": self.OUTPUT_FOLDER,
            "temp": self.TEMP_DIR,
        }
        for path in folders.values():
            try:
                os.makedirs(path, exist_ok=True)
            except (IOError, OSError):
                pass
        return folders

    def init_folders(self) -> Dict[str, str]:
        """Явно создаёт папки. Возвращает словарь путей."""
        self._folders = self._init_folders()
        return self._folders

    # =========================================================
    # ШРИФТЫ
    # =========================================================
    def get_fonts(self) -> Dict[str, QFont]:
        """Создаёт QFont из спецификаций. Вызывать ТОЛЬКО после QApplication."""
        return {
            "title": self._make_font(self.FONTS_CFG["title"]),
            "subtitle": self._make_font(self.FONTS_CFG["subtitle"]),
            "label": self._make_font(self.FONTS_CFG["label"]),
            "small": self._make_font(self.FONTS_CFG["small"]),
            "status": self._make_font(self.FONTS_CFG["status"]),
        }

    @staticmethod
    def _make_font(spec) -> QFont:
        family = spec[0]
        size = spec[1]
        weight_str = spec[2] if len(spec) > 2 else "normal"

        font = QFont(family, size)
        if weight_str == "bold":
            font.setWeight(QFont.Weight.Bold)
        else:
            font.setWeight(QFont.Weight.Normal)
        return font


# =========================================================
# ЛЕНИВЫЙ SINGLETON
# =========================================================
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """Возвращает единственный экземпляр Config. Создаёт при первом вызове."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reset_config():
    """Сбрасывает singleton. Для тестов."""
    global _config_instance
    _config_instance = None


# =========================================================
# ОБРАТНАЯ СОВМЕСТИМОСТЬ — ЛЕНИВЫЕ ПРОКСИ
# =========================================================
_ATTR_MAPPING = {
    "BASE_DIR": "BASE_DIR",
    "DATA_DIR": "DATA_DIR",
    "LOG_DIR": "LOG_DIR",
    "INPUT_FOLDER": "INPUT_FOLDER",
    "OUTPUT_FOLDER": "OUTPUT_FOLDER",
    "TEMP_DIR": "TEMP_DIR",
    "CONFIG_PATH": "CONFIG_PATH",
    "CONFIG_AUTO_CREATED": "CONFIG_AUTO_CREATED",
    "CONFIG": "CONFIG",
    "COLORS": "COLORS",
    "FONTS_CFG": "FONTS_CFG",
    "EXTERNAL": "EXTERNAL",
    "LOSS_THRESHOLD": "LOSS_THRESHOLD",
    "BOX_DEVIATION_PCT": "BOX_DEVIATION_PCT",
    "MIRROR_DEVIATION_PCT": "MIRROR_DEVIATION_PCT",
    "BRAK_UTIL_TOLERANCE": "BRAK_UTIL_TOLERANCE",
    "FOLDERS": "FOLDERS",
}


def __getattr__(name: str) -> Any:
    """Ленивый доступ к атрибутам Config через module-level."""
    if name in _ATTR_MAPPING:
        cfg = get_config()
        return getattr(cfg, _ATTR_MAPPING[name])

    raise AttributeError(f"module 'config' has no attribute '{name}'")


# =========================================================
# ФУНКЦИИ ОБРАТНОЙ СОВМЕСТИМОСТИ
# =========================================================
def get_fonts() -> Dict[str, QFont]:
    """Обратная совместимость. Делегирует в Config.get_fonts()."""
    return get_config().get_fonts()


def init_folders() -> Dict[str, str]:
    """Обратная совместимость. Делегирует в Config.init_folders()."""
    return get_config().init_folders()