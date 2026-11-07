# prepare_build.py
import os
import shutil
import json
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Список файлов, которые НЕЛЬЗЯ удалять (справочники)
KEEP_FILES = {
    "gm_data.json",
    "gm_ip.json",
    "standard_comments.json",
    "inventory_plans.json",
    "kv_rules.json",
    "kv_reason_schema.json",
    "unwanted.json",
    "timesheet.json",
}

# Список папок/файлов, которые нужно удалить (личные данные)
REMOVE_ITEMS = [
    "actions_history.json",
    "active_inventory.json",
    "inventory_archive.json",
    "emails.json",
    "gm_notes.json",
    "gm_cities_cache.json",
    "ml",         # база данных Shadow Engine
    "webengine",  # кэш браузера
    "emails",     # папка с письмами
]

def clean_data():
    print(f"Очистка папки: {DATA_DIR}")
    
    if not os.path.exists(DATA_DIR):
        print("Папка data не найдена!")
        return

    for item in REMOVE_ITEMS:
        path = os.path.join(DATA_DIR, item)
        if os.path.exists(path):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                print(f"  Удалено: {item}")
            except Exception as e:
                print(f"  Ошибка удаления {item}: {e}")
        else:
            print(f"  Пропущено (нет): {item}")

    # Проверяем, что все справочники на месте
    for f in KEEP_FILES:
        path = os.path.join(DATA_DIR, f)
        if not os.path.exists(path):
            print(f"  ВНИМАНИЕ: справочник {f} отсутствует!")

    print("Очистка data завершена.")

def clean_registry():
    """Удаляет ключ QSettings из реестра Windows, чтобы сбросить настройки."""
    print("\nОчистка настроек в реестре (QSettings)...")
    key_path = r"HKCU\Software\SilchenkoAleksey\CoreV3"
    try:
        # Используем reg delete через subprocess
        result = subprocess.run(
            ["reg", "delete", key_path, "/f"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
        if result.returncode == 0:
            print("  Ключ реестра успешно удалён.")
        else:
            print(f"  Ключ реестра не найден или ошибка: {result.stderr.strip()}")
    except Exception as e:
        print(f"  Ошибка при работе с реестром: {e}")

def clean_localappdata():
    """Удаляет личные данные из %LOCALAPPDATA% (для теста чистой установки)."""
    localappdata = os.environ.get("LOCALAPPDATA")
    if not localappdata:
        return
    
    app_dir = os.path.join(localappdata, "Core_V3_0")
    if os.path.exists(app_dir):
        # Спрашиваем только если папка реально есть
        answer = input(f"\nУдалить {app_dir} для теста чистой установки? (y/n): ")
        if answer.lower() == 'y':
            try:
                shutil.rmtree(app_dir)
                print(f"Удалено: {app_dir}")
            except Exception as e:
                print(f"Ошибка: {e}")
    else:
        print(f"\nПапка {app_dir} не найдена (это нормально).")

if __name__ == "__main__":
    clean_data()
    clean_registry()
    clean_localappdata()
    
    print("\nВсё очищено. Программа готова к тесту 'чистой установки'.")