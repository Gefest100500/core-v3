# ui/components/weather_widget.py
"""
Виджет погоды для главной страницы.
Использует WebView2 (pywv2) для запроса к API (обход блокировок фаервола).
"""
import json
import time

from PyQt6.QtCore import Qt, pyqtSignal, QThread
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
            # 1. Определяем город по IP
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

            # 2. Запрашиваем погоду через WebView2
            # Используем wttr.in (формат j1 — JSON)
            url = f"https://wttr.in/{lat},{lon}?format=j1"

            view = pywv2.WebView(
                title="Weather Fetch",
                size=(100, 100),
                auto_pump=True,
                context_menu=False,
            )
            view.start()
            
            # Загружаем пустую страницу, чтобы контекст был готов
            view.load_html("<html><body>Loading...</body></html>")
            
            # Даём время на инициализацию
            time.sleep(2)
            
            # Выполняем синхронный XHR запрос
            js = f"""
            (function() {{
                var xhr = new XMLHttpRequest();
                xhr.open('GET', '{url}', false); // false = синхронный
                xhr.send();
                return xhr.responseText;
            }})()
            """
            
            text = view.eval(js)
            view.close()
            
            if not text:
                raise ValueError("Пустой ответ от API")
            
            # Парсим JSON от wttr.in
            data = json.loads(text)
            current = data.get("current_condition", [{}])[0]
            temp = float(current.get("temp_C", 0))
            
            # Маппинг кодов wttr.in (WWO)
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

        thread = _WeatherFetchThread(card)

        def _on_loaded(data):
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

            icon = get_icon_simple(
                icon_name,
                color=colors.get('text_dim', '#A0A0A0'),
                size=48
            )
            if not icon.isNull():
                icon_label.setPixmap(icon.pixmap(48, 48))

        thread.finished.connect(_on_loaded)
        thread.start()

        card._weather_thread = thread

        return card