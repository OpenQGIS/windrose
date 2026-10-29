# -*- coding: utf-8 -*-
"""
windrose_worker.py

后台线程：从 Open-Meteo 历史天气 API 获取风向和风速数据。
"""

import calendar
import numpy as np
import requests
from qgis.PyQt.QtCore import QObject, pyqtSignal

from . import i18n


class WindRoseWorker(QObject):
    """异步获取风向数据的后台工作对象。"""

    finished = pyqtSignal(object, object, object, object)
    error = pyqtSignal(str)

    def __init__(self, lon, lat, year, month, height):
        super().__init__()
        self.lon = lon
        self.lat = lat
        self.year = year
        self.month = month
        self.height = height
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self._cancelled:
                return
            wind_dirs, wind_speeds = self._fetch()
            if self._cancelled:
                return
            labels = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                      "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            angles = list(np.arange(0, 360, 22.5))
            self.finished.emit(wind_dirs, wind_speeds, labels, angles)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def _fetch(self):
        """从 Open-Meteo API 获取风向风速数据。"""
        url = "https://archive-api.open-meteo.com/v1/archive"

        if self.month is None:
            start_date = f"{self.year}-01-01"
            end_date = f"{self.year}-12-31"
        else:
            last_day = calendar.monthrange(self.year, self.month)[1]
            start_date = f"{self.year}-{self.month:02d}-01"
            end_date = f"{self.year}-{self.month:02d}-{last_day:02d}"

        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": f"wind_direction_{self.height}m,wind_speed_{self.height}m",
            "timezone": "auto",
            "models": "era5",
        }

        try:
            if self._cancelled:
                raise Exception("Cancelled")
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            if self._cancelled:
                raise Exception("Cancelled")

            data = resp.json()
            dir_key = f"wind_direction_{self.height}m"
            speed_key = f"wind_speed_{self.height}m"

            if "hourly" not in data:
                raise Exception(i18n.tr("msg_no_wind_data", height=self.height))
            if dir_key not in data["hourly"] or speed_key not in data["hourly"]:
                raise Exception(i18n.tr("msg_no_wind_data", height=self.height))

            wind_dirs = np.array(data["hourly"][dir_key], dtype=float)
            wind_speeds = np.array(data["hourly"][speed_key], dtype=float)

            # 过滤无效值（None、NaN、Inf）
            mask = np.isfinite(wind_dirs) & np.isfinite(wind_speeds)
            if not np.any(mask):
                raise Exception(i18n.tr("msg_wind_data_empty"))

            return wind_dirs[mask].tolist(), wind_speeds[mask].tolist()

        except requests.exceptions.Timeout:
            raise Exception(i18n.tr("msg_error_api", error="Request timeout (60s)"))
        except requests.exceptions.ConnectionError:
            raise Exception(i18n.tr("msg_error_api", error="Connection failed"))
        except requests.exceptions.RequestException as e:
            raise Exception(i18n.tr("msg_error_api", error=str(e)))
