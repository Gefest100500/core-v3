# utils/data_migration.py
"""
Одноразовая миграция data/ из корня проекта в %LOCALAPPDATA%/Core_V3_0/data.

Правила:
- Копируем, НЕ перемещаем. Оригинал остаётся на месте.
- Существующие файлы в целевой папке НЕ перезаписываем — только докопируем.
- Флаг .migrated в корне данных сигнализирует, что миграция выполнена.
- Если корневой data/ отсутствует — создаём пустую целевую папку и ставим флаг.
- Ошибки не роняют приложение: логируем и продолжаем.

Вызывается из main.py один раз при старте (до создания AuditApp).
"""
import os
import shutil

from utils.file_utils import get_base_dir, get_app_data_root, get_data_dir
from utils.logger import log


MIGRATION_FLAG = ".migrated"


def _flag_path() -> str:
    return os.path.join(get_app_data_root(), MIGRATION_FLAG)


def is_migrated() -> bool:
    """Проверяет, выполнена ли миграция."""
    return os.path.exists(_flag_path())


def _set_migrated() -> None:
    """Ставит флаг миграции (пустой файл)."""
    try:
        root = get_app_data_root()
        os.makedirs(root, exist_ok=True)
        with open(_flag_path(), "w", encoding="utf-8") as f:
            f.write("migrated\n")
    except (OSError, PermissionError) as e:
        log.warning(f"data_migration: не удалось поставить флаг .migrated: {e}")


def _copy_missing(src_dir: str, dst_dir: str) -> tuple[int, int, int]:
    """Копирует отсутствующие файлы из src_dir в dst_dir (рекурсивно).

    Возвращает (copied, skipped, failed).
    - copied  — сколько файлов скопировано
    - skipped — сколько уже было (не перезаписывали)
    - failed  — сколько не удалось скопировать
    """
    copied = 0
    skipped = 0
    failed = 0

    for root, _dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target_root = dst_dir if rel == "." else os.path.join(dst_dir, rel)

        try:
            os.makedirs(target_root, exist_ok=True)
        except (OSError, PermissionError) as e:
            log.warning(f"data_migration: не удалось создать {target_root}: {e}")
            failed += len(files)
            continue

        for name in files:
            src_file = os.path.join(root, name)
            dst_file = os.path.join(target_root, name)

            if os.path.exists(dst_file):
                skipped += 1
                continue

            try:
                shutil.copy2(src_file, dst_file)
                copied += 1
            except (OSError, PermissionError) as e:
                failed += 1
                log.warning(f"data_migration: не удалось скопировать {src_file}: {e}")

    return copied, skipped, failed


def migrate_data_if_needed() -> bool:
    """Выполняет миграцию data/, если она ещё не выполнена.

    Возвращает True, если миграция была выполнена сейчас,
    False — если уже была выполнена раньше или не потребовалась.
    """
    if is_migrated():
        log.debug("data_migration: миграция уже выполнена ранее")
        return False

    src_dir = os.path.join(get_base_dir(), "data")
    dst_dir = get_data_dir()  # создаёт папку при необходимости

    if not os.path.isdir(src_dir):
        log.info(
            "data_migration: корневой data/ отсутствует — "
            f"создана пустая папка данных: {dst_dir}"
        )
        _set_migrated()
        return True

    log.info(f"data_migration: начало миграции {src_dir} → {dst_dir}")
    copied, skipped, failed = _copy_missing(src_dir, dst_dir)

    log.info(
        f"data_migration: завершено — скопировано {copied}, "
        f"пропущено {skipped}, ошибок {failed}"
    )

    # Флаг ставим, даже если были ошибки: иначе при каждом запуске
    # будем пытаться снова. Ошибки залогированы — их можно разобрать.
    _set_migrated()
    return True