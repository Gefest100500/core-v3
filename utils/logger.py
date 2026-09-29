# utils/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler

from utils.file_utils import get_logs_dir


LOG_DIR = get_logs_dir()
LOG_FILE = os.path.join(LOG_DIR, "core.log")


class FlushRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler, который сбрасывает буфер после каждой записи."""

    def emit(self, record):
        super().emit(record)
        try:
            self.flush()
        except Exception:
            pass


logger = logging.getLogger("Core")
logger.setLevel(logging.DEBUG)

# Чтобы не было дублирования handler'ов при повторном импорте
if not logger.handlers:
    handler = FlushRotatingFileHandler(
        LOG_FILE,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
        delay=False,
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(handler)

    # Дублируем в консоль
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console)

    # Не пробрасывать в корневой логгер
    logger.propagate = False


log = logger