# config.py
"""
Конфигурация Core V3.0.
Цвета, шрифты, папки, пороги.

Загружает настройки из config.json (или создаёт его с дефолтами).
Шрифты создаются через QFont — вызывать get_fonts() ТОЛЬКО после QApplication.
"""
import json
import os

from PyQt6.QtGui import QFont

from utils.file_utils import (
    get_base_dir, get_data_dir, get_logs_dir, get_input_dir,
    get_output_dir, get_temp_dir
)

BASE_DIR = get_base_dir()
DATA_DIR = get_data_dir()
LOG_DIR = get_logs_dir()
INPUT_FOLDER = get_input_dir()
OUTPUT_FOLDER = get_output_dir()
TEMP_DIR = get_temp_dir()

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# --- Дефолтный конфиг на случай отсутствия файла ---
DEFAULT_CONFIG = {
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
        "border": "#333333"
    },
    "fonts": {
        "title": ["Segoe UI", 20, "bold"],
        "subtitle": ["Segoe UI", 15, "bold"],
        "label": ["Segoe UI", 13, "normal"],
        "small": ["Segoe UI", 11, "normal"],
        "status": ["Consolas", 12, "bold"]
    },
    "loss_threshold": 5.0,
    "box_deviation_pct": 2.0,
    "mirror_deviation_pct": 1.5,
    "brak_util": {
        "tolerance": 1.0
    },
    "external": {
        "asus_url": "https://rao.corp.tander.ru/",
        "asus_home": "https://rao.corp.tander.ru/"
    }
}

CONFIG_AUTO_CREATED = False

if not os.path.exists(CONFIG_PATH):
    CONFIG_AUTO_CREATED = True
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except (json.JSONDecodeError, IOError):
    CONFIG = DEFAULT_CONFIG
    CONFIG_AUTO_CREATED = True

COLORS = CONFIG.get("colors", DEFAULT_CONFIG["colors"])
FONTS_CFG = CONFIG.get("fonts", DEFAULT_CONFIG["fonts"])
EXTERNAL = CONFIG.get("external", DEFAULT_CONFIG["external"])

LOSS_THRESHOLD = CONFIG.get("loss_threshold", 5.0)
BOX_DEVIATION_PCT = CONFIG.get("box_deviation_pct", 2.0)
MIRROR_DEVIATION_PCT = CONFIG.get("mirror_deviation_pct", 1.5)

BRAK_UTIL_TOLERANCE = CONFIG.get("brak_util", {}).get("tolerance", 1.0)


def _make_font(spec):
    family = spec[0]
    size = spec[1]
    weight_str = spec[2] if len(spec) > 2 else "normal"

    font = QFont(family, size)
    if weight_str == "bold":
        font.setWeight(QFont.Weight.Bold)
    else:
        font.setWeight(QFont.Weight.Normal)
    return font


def get_fonts():
    return {
        'title': _make_font(FONTS_CFG['title']),
        'subtitle': _make_font(FONTS_CFG['subtitle']),
        'label': _make_font(FONTS_CFG['label']),
        'small': _make_font(FONTS_CFG['small']),
        'status': _make_font(FONTS_CFG['status']),
    }


def init_folders():
    folders = {
        "kv": os.path.join(OUTPUT_FOLDER, "Кванты"),
        "pal": os.path.join(OUTPUT_FOLDER, "Паллеты"),
        "os_mbp": os.path.join(OUTPUT_FOLDER, "ОС_МБП"),
        "brak_util": os.path.join(OUTPUT_FOLDER, "Брак_утиль"),
        "violations": os.path.join(OUTPUT_FOLDER, "Нарушения"),
        "pivot": os.path.join(OUTPUT_FOLDER, "Сводные"),
        "info": OUTPUT_FOLDER,
        "temp": TEMP_DIR,
    }
    for path in folders.values():
        os.makedirs(path, exist_ok=True)
    return folders


FOLDERS = init_folders()