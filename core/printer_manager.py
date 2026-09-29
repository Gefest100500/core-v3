# core/printer_manager.py
import win32print
import pywintypes
import subprocess
import json
import os
import tempfile
import re
import time

from utils.logger import log
from utils.network_utils import normalize_ip, is_valid_ip, check_host


class PrinterManager:
    def __init__(self):
        try:
            self.default_printer = win32print.GetDefaultPrinter()
        except Exception:
            self.default_printer = None

    # =========================================================
    # 1. Установленные принтеры
    # =========================================================
    def get_installed_printers(self):
        printers = []
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS

        try:
            raw_list = win32print.EnumPrinters(flags, None, 4)
            for printer_info in raw_list:
                p_name = printer_info.get('pPrinterName', 'Без имени')
                p_port = printer_info.get('pPortName', 'Локальный')
                p_status = printer_info.get('Status', 0)

                status_text = ""
                if p_status & win32print.PRINTER_STATUS_ERROR:
                    status_text += "[Ошибка] "
                if p_status & win32print.PRINTER_STATUS_OFFLINE:
                    status_text += "[Оффлайн]"

                printers.append({
                    'name': p_name,
                    'port': p_port,
                    'status': status_text.strip() or "Готов"
                })
        except Exception as e:
            return {"error": f"Не удалось получить список: {e}"}

        return sorted(printers, key=lambda x: x['name'])

    # =========================================================
    # 2. Запуск PowerShell
    # =========================================================
    def _run_powershell(self, script, timeout=60):
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".ps1")
            os.close(fd)
            with open(tmp_path, "w", encoding="utf-8-sig") as f:
                f.write(script)

            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-File", tmp_path
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            return result.stdout, result.stderr, result.returncode

        except subprocess.TimeoutExpired:
            return "", "timeout", -1
        except Exception as e:
            log.exception(f"Ошибка запуска PowerShell: {e}")
            return "", str(e), -1
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    # =========================================================
    # 3. Проверка доступности
    # =========================================================
    def ping_host(self, host, timeout=3):
        result = check_host(host, timeout=timeout)

        if result["online"]:
            if result["port"]:
                if result["ping_ok"]:
                    return True, f"порт {result['port']} открыт, ping {result['ping_info']}"
                else:
                    return True, f"порт {result['port']} открыт"
            else:
                return True, f"ping {result['ping_info']}"
        else:
            return False, result["ping_info"] or "нет ответа"

    # =========================================================
    # 4. Доступные драйверы
    # =========================================================
    def get_available_drivers(self):
        """Возвращает список установленных драйверов принтеров."""
        try:
            script = (
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
                "Get-PrinterDriver | Select-Object -ExpandProperty Name\n"
            )
            stdout, stderr, code = self._run_powershell(script, timeout=15)

            drivers = []
            for line in (stdout or "").splitlines():
                line = line.strip()
                if line and not line.startswith("Name") and "----" not in line:
                    drivers.append(line)

            return drivers
        except Exception as e:
            log.warning(f"Ошибка получения драйверов: {e}")
            return []

    # =========================================================
    # 5. Установка принтера по IP
    # =========================================================
    def add_printer_by_ip(self, ip_address, printer_name="", timeout=90):
        ip = ip_address.strip()

        if ip.startswith("\\\\"):
            ok, err = self.connect_network_printer(ip)
            if ok:
                return True, {"name": ip, "port": ip, "driver": ""}
            return False, err

        normalized_ip = normalize_ip(ip)
        if not is_valid_ip(normalized_ip):
            return False, f"Неверный IP-адрес: {ip}"

        log.info(f"Установка принтера по IP: {ip} → {normalized_ip}")

        port_name = f"IP_{normalized_ip}"
        temp_name = printer_name.strip() or f"Принтер {normalized_ip}"

        # ----------------------------------------------------
        # Шаг 1: Проверить — есть ли уже принтер на этом порту?
        # ----------------------------------------------------
        existing = self._find_printer_by_port(port_name)
        if existing:
            log.info(f"Принтер с портом {port_name} уже есть: {existing['name']}")
            return True, {
                "name": existing["name"],
                "port": port_name,
                "driver": existing.get("driver", ""),
                "already_existed": True,
            }

        # ----------------------------------------------------
        # Шаг 2: Создать порт (если нет)
        # ----------------------------------------------------
        port_script = (
            "$ErrorActionPreference = 'Stop'\n"
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
            "try {\n"
            f"    $portName = \"{port_name}\"\n"
            f"    $targetIp = \"{normalized_ip}\"\n"
            "    $existingPort = Get-PrinterPort -Name $portName -ErrorAction SilentlyContinue\n"
            "    if (-not $existingPort) {\n"
            "        Add-PrinterPort -Name $portName -PrinterHostAddress $targetIp -ErrorAction Stop\n"
            "        \"PORT_CREATED\"\n"
            "    } else {\n"
            "        \"PORT_EXISTS\"\n"
            "    }\n"
            "}\n"
            "catch {\n"
            "    \"PORT_ERROR: $($_.Exception.Message)\"\n"
            "}\n"
        )

        stdout, stderr, code = self._run_powershell(port_script, timeout=30)
        port_output = (stdout or "").strip()
        log.info(f"Порт: {port_output}")

        if "PORT_ERROR" in port_output:
            err = port_output.replace("PORT_ERROR:", "").strip()
            return False, f"Не удалось создать порт:\n{err}"

        # ----------------------------------------------------
        # Шаг 3: Удалить существующий принтер с таким же именем (если есть)
        # ----------------------------------------------------
        check_name_script = (
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
            f"$p = Get-Printer -Name \"{temp_name}\" -ErrorAction SilentlyContinue\n"
            "if ($p) { \"EXISTS\" } else { \"NOT_EXISTS\" }\n"
        )
        stdout, _, _ = self._run_powershell(check_name_script, timeout=15)

        if "EXISTS" in (stdout or ""):
            log.info(f"Принтер с именем '{temp_name}' уже существует — удаляю")
            remove_script = (
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
                "try {\n"
                f"    Remove-Printer -Name \"{temp_name}\" -ErrorAction Stop\n"
                "    \"REMOVED\"\n"
                "}\n"
                "catch {\n"
                "    \"ERROR: $($_.Exception.Message)\"\n"
                "}\n"
            )
            self._run_powershell(remove_script, timeout=20)

        # ----------------------------------------------------
        # Шаг 4: Получить список РЕАЛЬНО установленных драйверов
        # ----------------------------------------------------
        available_drivers = self.get_available_drivers()
        log.info(f"Доступных драйверов: {len(available_drivers)}")

        # Приоритетный список драйверов (по надёжности)
        drivers_to_try = [
            "Microsoft IPP Class Driver",
            "Microsoft Virtual Print Class Driver",
            "Universal Print Class Driver",
            "Microsoft enhanced Point and Print compatibility driver",
            "Microsoft MS-XPS Class Driver 2",
            "Microsoft Print To PDF",
        ]

        # Также добавляем все HP-драйверы, которые есть
        for d in available_drivers:
            if "HP" in d and d not in drivers_to_try:
                drivers_to_try.append(d)

        last_error = ""
        success = False

        for driver in drivers_to_try:
            if driver not in available_drivers:
                log.info(f"Пропускаю (нет драйвера): {driver}")
                continue

            log.info(f"Пробуем драйвер: {driver}")

            add_script = (
                "$ErrorActionPreference = 'Stop'\n"
                "$OutputEncoding = [System.Text.Encoding]::UTF8\n"
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
                f"$portName = \"{port_name}\"\n"
                f"$printerName = \"{temp_name}\"\n"
                f"$driverName = \"{driver}\"\n"
                "try {\n"
                "    Add-Printer -Name $printerName -DriverName $driverName -PortName $portName -ErrorAction Stop\n"
                "    \"SUCCESS\"\n"
                "}\n"
                "catch {\n"
                "    \"ERROR: $($_.Exception.Message)\"\n"
                "}\n"
            )

            stdout, stderr, code = self._run_powershell(add_script, timeout=60)
            output = (stdout or "").strip()
            log.info(f"Результат ({driver}): {output[:200]}")

            if "SUCCESS" in output:
                success = True
                break

            if output.startswith("ERROR"):
                last_error = output.replace("ERROR:", "").strip()
                continue

        # ----------------------------------------------------
        # Шаг 5: Если не сработало — fallback на rundll32
        # ----------------------------------------------------
        if not success:
            log.info("Каскад не сработал, пробуем rundll32 printui.dll")
            try:
                cmd = [
                    "rundll32", "printui.dll,PrintUIEntry",
                    "/if", "/b", temp_name,
                    "/r", port_name,
                ]
                subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="cp866",
                    errors="replace",
                    timeout=60,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
                time.sleep(1)
            except Exception as e:
                log.warning(f"Ошибка rundll32: {e}")

        # ----------------------------------------------------
        # Шаг 6: Найти созданный принтер по порту
        # ----------------------------------------------------
        found = self._find_printer_by_port(port_name)
        if found:
            return True, {
                "name": found["name"],
                "port": port_name,
                "driver": found.get("driver", ""),
            }

        # Если всё провалилось
        error_msg = (
            f"Не удалось установить принтер автоматически.\n\n"
            f"Последняя ошибка: {last_error}\n\n"
            f"Что можно попробовать:\n"
            f"1. Запустить программу от имени администратора\n"
            f"2. Установить драйвер принтера вручную\n"
            f"3. Использовать мастер установки принтера Windows"
        )
        return False, error_msg

    # =========================================================
    # 6. Найти принтер по порту
    # =========================================================
    def _find_printer_by_port(self, port_name):
        try:
            script = (
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
                f"$p = Get-Printer -ErrorAction SilentlyContinue | Where-Object {{ $_.PortName -eq \"{port_name}\" }} | Select-Object -First 1\n"
                "if ($p) {\n"
                "    $p | Select-Object Name, PortName, DriverName | ConvertTo-Json -Compress\n"
                "} else {\n"
                "    \"NOTFOUND\"\n"
                "}\n"
            )

            stdout, stderr, code = self._run_powershell(script, timeout=15)
            output = (stdout or "").strip()

            if not output or output == "NOTFOUND":
                return None

            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                return None

            if isinstance(data, list):
                if not data:
                    return None
                data = data[0]

            return {
                "name": data.get("Name", ""),
                "port": data.get("PortName", ""),
                "driver": data.get("DriverName", ""),
            }

        except Exception as e:
            log.warning(f"Ошибка поиска принтера по порту: {e}")
            return None

    # =========================================================
    # 7. Подключение по UNC
    # =========================================================
    def connect_network_printer(self, unc_path):
        if not unc_path.startswith("\\\\"):
            unc_path = "\\\\" + unc_path

        script = (
            "$ErrorActionPreference = 'Stop'\n"
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
            "try {\n"
            f"    Add-Printer -ConnectionName \"{unc_path}\" -ErrorAction Stop\n"
            "    \"DONE\"\n"
            "}\n"
            "catch {\n"
            "    \"ERROR: $($_.Exception.Message)\"\n"
            "}\n"
        )

        stdout, stderr, code = self._run_powershell(script, timeout=30)
        output = (stdout or "").strip()

        if "DONE" in output:
            return True, ""
        else:
            err = output.replace("ERROR:", "").strip() or stderr.strip() or "Не удалось подключить"
            return False, err

    # =========================================================
    # 8. Переименование
    # =========================================================
    def rename_printer(self, old_name, new_name):
        log.info(f"Переименование: '{old_name}' → '{new_name}'")

        check_script = (
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
            f"$p = Get-Printer -Name \"{old_name}\" -ErrorAction SilentlyContinue\n"
            "if ($p) { \"YES\" } else { \"NO\" }\n"
        )
        stdout, _, _ = self._run_powershell(check_script, timeout=15)
        if "YES" not in (stdout or ""):
            return False

        script1 = (
            "$ErrorActionPreference = 'Stop'\n"
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
            "try {\n"
            f"    Rename-Printer -Name \"{old_name}\" -NewName \"{new_name}\" -ErrorAction Stop\n"
            "    \"RENAMED\"\n"
            "}\n"
            "catch {\n"
            "    \"ERROR: $($_.Exception.Message)\"\n"
            "}\n"
        )

        stdout, stderr, code = self._run_powershell(script1, timeout=30)
        output = (stdout or "").strip()
        log.info(f"Rename-Printer: {output[:200]}")

        if output == "RENAMED":
            return True

        # WMI
        script2 = (
            "$ErrorActionPreference = 'Stop'\n"
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
            "try {\n"
            f"    $p = Get-CimInstance Win32_Printer -Filter \"Name='{old_name}'\" -ErrorAction Stop\n"
            "    if (-not $p) { \"NOTFOUND\"; exit 0 }\n"
            f"    $result = Invoke-CimMethod -InputObject $p -MethodName Rename -Arguments @{{ NewName = \"{new_name}\" }}\n"
            "    if ($result.ReturnValue -eq 0) { \"RENAMED\" }\n"
            "    else { \"ERROR: ReturnValue = $($result.ReturnValue)\" }\n"
            "}\n"
            "catch {\n"
            "    \"ERROR: $($_.Exception.Message)\"\n"
            "}\n"
        )

        stdout, stderr, code = self._run_powershell(script2, timeout=30)
        output = (stdout or "").strip()
        log.info(f"WMI Rename: {output[:200]}")

        if output == "RENAMED":
            return True

        # win32print
        try:
            hprinter = win32print.OpenPrinter(old_name)
            info = win32print.GetPrinter(hprinter, 2)
            info['pPrinterName'] = new_name
            win32print.SetPrinter(hprinter, 2, info, 0)
            win32print.ClosePrinter(hprinter)
            return True
        except Exception as e:
            log.warning(f"win32print не сработал: {e}")

        return False

    # =========================================================
    # 9. Установка по умолчанию
    # =========================================================
    def set_default(self, name):
        try:
            win32print.SetDefaultPrinter(name)
            return True
        except pywintypes.error:
            return False