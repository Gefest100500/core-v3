# utils/data_manager.py
"""
Менеджер данных — JSON-хранилище с кэшем, очередью записи,
атомарной записью и асинхронным чтением.

Потокобезопасный. Singleton через get_data_manager().

ИЗМЕНЕНИЯ:
- read_json_async: убран QTimer.singleShot (не работает из фонового
  потока). Callback вызывается напрямую — фреймы сами оборачивают
  его в self.run_on_ui(...), который через pyqtSignal доставляет
  вызов в главный поток Qt.
"""
import concurrent.futures
import hashlib
import json
import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from utils.logger import log


def _get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
DATA_DIR = BASE_DIR / "data"

HISTORY_PATH = DATA_DIR / "actions_history.json"
INVENTORY_PATH = DATA_DIR / "active_inventory.json"
INVENTORY_ARCHIVE_PATH = DATA_DIR / "inventory_archive.json"
GM_DATA_PATH = DATA_DIR / "gm_data.json"
INVENTORY_PLANS_PATH = DATA_DIR / "inventory_plans.json"
GM_NOTES_PATH = DATA_DIR / "gm_notes.json"


class DataManager:
    def __init__(self):
        self._cache = {}
        self._locks = {}
        self._closing = False

        self._write_queue = queue.Queue()

        self._read_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="DataRead"
        )

        self._writer_thread = threading.Thread(
            target=self._writer_loop, daemon=True, name="DataWriter"
        )
        self._writer_thread.start()

        self._root = None

        log.info("DataManager инициализирован")

    def set_root(self, root):
        """Сохраняем ссылку на главное окно.

        Оставлено для совместимости с app.py. Сейчас не используется,
        но может пригодиться в будущем.
        """
        self._root = root

    # =========================================================
    # ВОРКЕР ЗАПИСИ
    # =========================================================
    def _writer_loop(self):
        while not self._closing:
            try:
                item = self._write_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if item is None:
                break

            name, path, data = item
            try:
                self._write_file(name, path, data)
            except Exception:
                log.exception(f"Ошибка записи {name}")
            finally:
                self._write_queue.task_done()

    # =========================================================
    # ВНУТРЕННИЕ
    # =========================================================
    def _get_lock(self, name):
        if name not in self._locks:
            self._locks[name] = threading.Lock()
        return self._locks[name]

    def _read_file(self, name, path, force=False):
        if self._closing:
            cached = self._cache.get(name)
            return cached[0] if cached else None

        try:
            mtime = os.path.getmtime(str(path))
        except OSError:
            mtime = None

        cached = self._cache.get(name)
        if cached is not None and not force:
            cached_data, cached_mtime = cached
            if cached_mtime == mtime:
                return cached_data

        if mtime is None:
            self._cache[name] = (None, None)
            return None

        lock = self._get_lock(name)
        with lock:
            cached = self._cache.get(name)
            if cached is not None and not force:
                cached_data, cached_mtime = cached
                if cached_mtime == mtime:
                    return cached_data

            try:
                with open(str(path), "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache[name] = (data, mtime)
                return data
            except json.JSONDecodeError as e:
                log.error(f"JSON повреждён ({name}): {e}")
                self._cache[name] = (None, mtime)
                return None
            except (IOError, OSError) as e:
                log.warning(f"Ошибка чтения {name}: {e}")
                cached = self._cache.get(name)
                return cached[0] if cached else None

    def _write_file(self, name, path, data):
        try:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)

            tmp_path = path.with_suffix(path.suffix + ".tmp")
            with open(str(tmp_path), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            os.replace(str(tmp_path), str(path))

            try:
                mtime = os.path.getmtime(str(path))
            except OSError:
                mtime = time.time()

            self._cache[name] = (data, mtime)
        except Exception:
            log.exception(f"Ошибка записи {name}")

    def _write_async(self, name, path, data):
        self._cache[name] = (data, None)
        try:
            self._write_queue.put_nowait((name, path, data))
        except queue.Full:
            log.warning(f"Очередь записи переполнена: {name}")

    # =========================================================
    # ИСТОРИЯ
    # =========================================================
    def get_history(self):
        return self._read_file("history", HISTORY_PATH) or []

    def set_history(self, history):
        lock = self._get_lock("history")
        with lock:
            new_history = list(history)[-100:]
            self._cache["history"] = (new_history, None)

        try:
            self._write_queue.put_nowait(("history", HISTORY_PATH, new_history))
        except queue.Full:
            log.warning("Очередь записи переполнена: history")

        log.info(f"История обновлена: {len(new_history)} записей")

    def add_action(self, action, details="", icon="•"):
        lock = self._get_lock("history")
        with lock:
            history = self._read_file("history", HISTORY_PATH) or []
            new_history = list(history)
            new_history.append({
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "details": details,
                "icon": icon,
            })
            new_history = new_history[-100:]
            self._cache["history"] = (new_history, None)

        try:
            self._write_queue.put_nowait(("history", HISTORY_PATH, new_history))
        except queue.Full:
            log.warning("Очередь записи переполнена: history")

        log.info(f"История: {action} — {details}")

    # =========================================================
    # АКТИВНАЯ ИНВЕНТАРИЗАЦИЯ
    # =========================================================
    def get_active_inventory(self):
        return self._read_file("active_inventory", INVENTORY_PATH)

    def set_active_inventory(self, data):
        if data is None:
            if INVENTORY_PATH.exists():
                try:
                    os.remove(str(INVENTORY_PATH))
                except OSError:
                    log.warning("Не удалось удалить active_inventory.json")
            self._cache["active_inventory"] = (None, None)
        else:
            self._write_async("active_inventory", INVENTORY_PATH, data)

    # =========================================================
    # АРХИВ
    # =========================================================
    def get_inventory_archive(self):
        return self._read_file("inventory_archive", INVENTORY_ARCHIVE_PATH) or []

    def set_inventory_archive(self, data):
        self._write_async("inventory_archive", INVENTORY_ARCHIVE_PATH, data)

    # =========================================================
    # ПЛАНЫ ИНВЕНТАРИЗАЦИЙ (А–Ж)
    # =========================================================
    def get_inventory_plans(self):
        """Возвращает словарь всех вариантов плана."""
        return self._read_file("inventory_plans", INVENTORY_PLANS_PATH) or {}

    # =========================================================
    # GM_DATA
    # =========================================================
    def get_gm_data(self):
        return self._read_file("gm_data", GM_DATA_PATH) or []

    # =========================================================
    # ЗАМЕТКИ
    # =========================================================
    def get_gm_notes(self):
        return self._read_file("gm_notes", GM_NOTES_PATH) or {}

    def set_gm_notes(self, data):
        self._write_async("gm_notes", GM_NOTES_PATH, data)

    # =========================================================
    # АСИНХРОННОЕ ЧТЕНИЕ
    # =========================================================
    def read_json_async(self, name, path, callback):
        """Читает JSON в фоне.

        ВАЖНО: callback вызывается НАПРЯМУЮ из фонового потока.
        Фрейм-получатель ОБЯЗАН обернуть работу с UI в self.run_on_ui().

        Раньше здесь был QTimer.singleShot(0, ...) — но он не работает
        из фонового потока без своего event loop. Теперь callback
        вызывается как есть, а доставку в главный поток обеспечивает
        pyqtSignal внутри BaseFrame.run_on_ui().
        """
        def _bg_read():
            try:
                if not Path(path).exists():
                    mtime = None
                    data = None
                else:
                    mtime = os.path.getmtime(str(path))
                    cached = self._cache.get(name)
                    if cached is not None:
                        cached_data, cached_mtime = cached
                        if cached_mtime == mtime:
                            data = cached_data
                        else:
                            with open(str(path), "r", encoding="utf-8") as f:
                                data = json.load(f)
                            self._cache[name] = (data, mtime)
                    else:
                        with open(str(path), "r", encoding="utf-8") as f:
                            data = json.load(f)
                        self._cache[name] = (data, mtime)

                # Вызываем callback напрямую. Фрейм сам решит,
                # как доставить результат в главный поток.
                callback(data)
            except Exception:
                log.exception(f"Ошибка асинхронного чтения {name}")
                try:
                    callback(None)
                except Exception:
                    log.exception(f"Ошибка callback для {name}")

        try:
            self._read_executor.submit(_bg_read)
        except RuntimeError:
            log.warning("Read executor уже закрыт")

    # =========================================================
    # КЭШ
    # =========================================================
    def invalidate(self, name):
        if name in self._cache:
            self._cache[name] = (self._cache[name][0], None)

    def invalidate_all(self):
        for name in list(self._cache.keys()):
            self._cache[name] = (self._cache[name][0], None)

    # =========================================================
    # ХЭШ
    # =========================================================
    @staticmethod
    def signature(data):
        if data is None:
            return None
        try:
            s = json.dumps(data, sort_keys=True)
            return hashlib.md5(s.encode("utf-8")).hexdigest()
        except Exception:
            return str(data)

    # =========================================================
    # ЗАКРЫТИЕ
    # =========================================================
    def shutdown(self):
        self._closing = True

        try:
            self._write_queue.put_nowait(None)
        except queue.Full:
            pass

        try:
            self._writer_thread.join(timeout=1.0)
        except Exception:
            pass

        try:
            self._read_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass


_data_manager = None


def get_data_manager():
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager