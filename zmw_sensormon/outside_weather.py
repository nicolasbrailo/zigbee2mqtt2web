"""Outside weather sensor using Open-Meteo API."""

import json
import threading
import urllib.request
import urllib.error

from zzmw_lib.logs import build_logger
from virtual_metrics import get_virtual_metrics, compute_virtual_metrics

log = build_logger("OutsideWeather")


class OutsideWeatherSensor:
    """Fetches outside weather data from Open-Meteo and records to sensor history."""

    METRICS = ['temperature', 'humidity']
    SENSOR_NAME = 'Outside'

    def __init__(self, sensors_history, scheduler, latitude, longitude, update_interval_seconds=300):
        """Initialize the outside weather sensor.

        Args:
            sensors_history: SensorsHistory instance to save readings
            scheduler: Scheduler for periodic updates
            latitude: Location latitude
            longitude: Location longitude
            update_interval_seconds: How often to fetch new data (default: 5 minutes)
        """
        self._sensors = sensors_history
        self._scheduler = scheduler
        self._latitude = latitude
        self._longitude = longitude
        self.update_interval_seconds = update_interval_seconds
        self._values = {}

        self._api_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
            "&current=temperature_2m,relative_humidity_2m"
        )

        virtual_metrics = get_virtual_metrics(self.METRICS)
        all_metrics = self.METRICS + virtual_metrics
        self._sensors.register_sensor(self.SENSOR_NAME, all_metrics)
        log.info("Registered outside weather sensor at (%.4f, %.4f), updating every %ds (virtual: %s)",
                 latitude, longitude, update_interval_seconds, virtual_metrics)

        # Schedule periodic updates using APScheduler's add_job
        self._scheduler.add_job(
            func=self._trigger_async_update,
            trigger="interval",
            seconds=update_interval_seconds,
        )
        # Fetch immediately on startup
        self._trigger_async_update()

    def get(self, metric_name):
        """Return the current value for a metric."""
        return self._values.get(metric_name)

    def get_current_values(self):
        """Return all current values."""
        return {metric: self.get(metric) for metric in self.METRICS}

    def _trigger_async_update(self):
        """Trigger an async fetch in a background thread."""
        thread = threading.Thread(target=self._fetch_and_save, daemon=True)
        thread.start()

    def _fetch_and_save(self):
        """Fetch data from API and save to database. Runs in a background thread."""
        try:
            with urllib.request.urlopen(self._api_url, timeout=30) as response:
                raw_response = response.read().decode()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            log.warning("Can't reach Open-Meteo service: %s", e)
            self._values = {metric: None for metric in self.METRICS}
            self._sensors.save_reading(self.SENSOR_NAME, self._values)
            return

        try:
            data = json.loads(raw_response)
            current = data['current']
            self._values = {
                'temperature': current['temperature_2m'],
                'humidity': current['relative_humidity_2m'],
            }
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.error("Failed to parse Open-Meteo response: %s (response: %s)", e, raw_response)
            self._values = {metric: None for metric in self.METRICS}
            self._sensors.save_reading(self.SENSOR_NAME, self._values)
            return

        virtual_values = compute_virtual_metrics(self._values)
        self._sensors.save_reading(self.SENSOR_NAME, {**self._values, **virtual_values})
