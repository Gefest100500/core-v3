# ml/config.py
"""
Конфигурация ML-модуля.

Единая точка правды для путей и порогов.
"""
import os

from utils.file_utils import get_base_dir


BASE_DIR = get_base_dir()

# Пути
ML_DATA_DIR = os.path.join(BASE_DIR, "data", "ml")
SHADOW_DB_PATH = os.path.join(ML_DATA_DIR, "shadow.sqlite")
EXPORTS_DIR = os.path.join(ML_DATA_DIR, "exports")
MODELS_DIR = os.path.join(ML_DATA_DIR, "models")

LOGS_DIR = os.path.join(BASE_DIR, "Logs")
SHADOW_REPORT_PATH = os.path.join(LOGS_DIR, "shadow_report.jsonl")

# Пороги
DEFAULT_CONFIDENCE_THRESHOLD = 0.6

# Минимум размеченных строк для переобучения
MIN_FEEDBACK_FOR_TRAINING = 500


def ensure_dirs():
    """Создаёт все папки ML-модуля."""
    for d in (ML_DATA_DIR, EXPORTS_DIR, MODELS_DIR, LOGS_DIR):
        os.makedirs(d, exist_ok=True)