# ui/components/weather_widget.py
"""
Виджет погоды для главной страницы.
Использует WebView2 (pywv2) с невидимым родительским окном.
"""
import json
import time
import ctypes
from ctypes import wintypes

from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel

from ui.components.widgets import create_card
from ui.icons import get_icon_simple
from core.geo_helper import get_local_ip, find_gm_by_ip, get_city_by_gm_code, get_coords_by_city
from utils.logger import log

try:
    import pywv2
    WEBVIEW_AVAILABLE = True
except ImportError:
    WEBVIEW_AVAILABLE = False
    log.warning("pywv2 не установлен — виджет погоды будет показывать заглушку")

# --- WinAPI для создания невидимого родительского окна ---
user32 = ctypes.windll.user32
WS_POPUP = 0x80000000
WS_EX_TOOLWINDOW = 0x00000080
SW_HIDE = 0

def create_hidden_window() -> int:
    """Создаёт невидимое родительское окно и возвращает его HWND."""
    hwnd = user32.CreateWindowExW(
        WS_EX_TOOLWINDOW,  # Чтобы не было в панели задач
        "STATIC",          # Класс окна (просто заглушка)
        "WeatherProxy",    # Заголовок
        WS_POPUP,          # Стиль (без рамок)
        0, 0, 0, 0,        # Позиция и размер (0x0)
        0, 0, 0, 0,
    )
    if hwnd:
        user32.ShowWindow(hwnd, SW_HIDE)
    return hwnd


# Погодные коды Open-Meteo (WMO)
WEATHER_CODES = {
    0: ("Ясно", "sun"),
    1: ("Преим. ясно", "cloud-sun"),
    2: ("Переменная облачность", "cloud-sun"),
    3: ("Пасмурно", "cloud"),
    45: ("Туман", "cloud"),
    48: ("Туман", "cloud"),
    51: ("Морось", "rain"),
    53: ("Морось", "rain"),
    55: ("Морось", "rain"),
    61: ("Дождь", "rain"),
    63: ("Дождь", "rain"),
    65: ("Сильный дождь", "rain"),
    71: ("Снег", "snow"),
    73: ("Снег", "snow"),
    75: ("Сильный снег", "snow"),
    77: ("Снежная крупа", "snow"),
    80: ("Ливень", "rain"),
    81: ("Ливень", "rain"),
    82: ("Сильный ливень", "rain"),
    85: ("Снегопад", "snow"),
    86: ("Снегопад", "snow"),
    95: ("Гроза", "rain"),
    96: ("Гроза", "rain"),
    99: ("Гроза", "rain"),
}


class _WeatherFetchThread(QThread):
    finished = pyqtSignal(dict)

    def run(self):
        result = {}
        city = ""
        try:
            ip = get_local_ip()
            code = find_gm_by_ip(ip) if ip else ""
            city = get_city_by_gm_code(code) if code else ""
            coords = get_coords_by_city(city) if city else None

            if not coords:
                raise ValueError("Локация не определена")

            lat, lon = coords
            city = city.capitalize()

            if not WEBVIEW_AVAILABLE:
                raise ValueError("WebView2 недоступен")

            url = f"https://wttr.in/{lat},{lon}?format=j1"

            # Создаём невидимое родительское окно
            parent_hwnd = create_hidden_window()
            if not parent_hwnd:
                raise ValueError("Не удалось создать невидимое окно")

            view = pywv2.WebView(
                title="Weather Fetch",
                size=(100, 100),
                parent_hwnd=parent_hwnd,  # Привязываем к скрытому окну
                auto_pump=True,
                context_menu=False,
            )
            view.start()
            
            # Окно скрыто через родителя, но на всякий случай прячем само окно WebView
            try:
                hwnd = view.hwnd
                if hwnd:
                    user32.ShowWindow(hwnd, SW_HIDE)
            except Exception:
                pass

            view.load_html("<html><body>Loading...</body></html>")
            time.sleep(2)
            
            js = f"""
            (function() {{
                var xhr = new XMLHttpRequest();
                xhr.open('GET', '{url}', false);
                xhr.send();
                return xhr.responseText;
            }})()
            """
            
            text = view.eval(js)
            
            # Закрываем
            try:
                hwnd = view.hwnd
                if hwnd:
                    user32.ShowWindow(hwnd, SW_HIDE)
            except Exception:
                pass
                
            view.close()
            
            # Уничтожаем родительское окно
            if parent_hwnd:
                try:
                    user32.DestroyWindow(parent_hwnd)
                except Exception:
                    pass
            
            if not text:
                raise ValueError("Пустой ответ от API")
            
            data = json.loads(text)
            current = data.get("current_condition", [{}])[0]
            temp = float(current.get("temp_C", 0))
            
            wwo_code = current.get("weatherCode", "113")
            if wwo_code in ("113",):
                code = 0
            elif wwo_code in ("116", "119", "122"):
                code = 3
            elif wwo_code in ("176", "293", "296", "299", "302", "305", "308"):
                code = 61
            elif wwo_code in ("179", "323", "326", "329", "332", "335", "338"):
                code = 71
            else:
                code = 3

            result = {
                "success": True,
                "city": city,
                "temp": temp,
                "code": code,
            }

        except Exception as e:
            log.warning(f"WeatherWidget: ошибка загрузки: {e}")
            result = {"success": False, "error": str(e), "city": city}

        self.finished.emit(result)


class WeatherWidget:
    @staticmethod
    def create(parent, colors, fonts):
        card = create_card(parent)
        card.setFixedWidth(340)
        card.setMinimumHeight(140)

        layout = card.layout()

        top_row = QHBoxLayout()
        top_row.setSpacing(15)
        top_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        icon_label = QLabel(card)
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(icon_label)

        temp_col = QVBoxLayout()
        temp_col.setSpacing(2)
        
        temp_label = QLabel("—", card)
        font_temp = QFont("Segoe UI", 28)
        font_temp.setBold(True)
        temp_label.setFont(font_temp)
        temp_label.setStyleSheet(f"color: {colors.get('text', '#E0E0E0')};")
        temp_col.addWidget(temp_label)

        desc_label = QLabel("Загрузка...", card)
        desc_label.setFont(fonts['small'])
        desc_label.setStyleSheet(f"color: {colors.get('text_dim', '#A0A0A0')};")
        temp_col.addWidget(desc_label)

        top_row.addLayout(temp_col)
        top_row.addStretch()
        layout.addLayout(top_row)

        city_label = QLabel("Определение локации...", card)
        city_label.setFont(fonts['small'])
        city_label.setStyleSheet(f"color: {colors.get('text_dim', '#A0A0A0')};")
        layout.addWidget(city_label)

        def _update_ui(data):
            city = data.get("city", "")
            if not data.get("success"):
                if city:
                    temp_label.setText("—")
                    desc_label.setText("Погода недоступна")
                    city_label.setText(city)
                    icon = get_icon_simple("cloud", color=colors.get('text_dim', '#A0A0A0'), size=48)
                    if not icon.isNull():
                        icon_label.setPixmap(icon.pixmap(48, 48))
                else:
                    desc_label.setText("Нет данных")
                    city_label.setText("Локация не определена")
                return

            temp = data.get("temp")
            code = data.get("code")
            if temp is not None:
                temp_label.setText(f"{round(temp)}°C")
            else:
                temp_label.setText("—")

            desc, icon_name = WEATHER_CODES.get(code, ("Неизвестно", "cloud"))
            desc_label.setText(desc)
            city_label.setText(city)

            icon = get_icon_simple(icon_name, color=colors.get('text_dim', '#A0A0A0'), size=48)
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(48, 48))

        def _fetch():
            thread = _WeatherFetchThread(card)
            thread.finished.connect(_update_ui)
            card._weather_thread = thread
            thread.start()

        _fetch()

        refresh_timer = QTimer(card)
        refresh_timer.timeout.connect(_fetch)
        refresh_timer.start(10 * 60 * 1000)  # 10 минут

        card._weather_timer = refresh_timer

        return card