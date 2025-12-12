"""Sensor monitoring and history service."""
from zzmw_lib.zmw_mqtt_nullsvc import ZmwMqttNullSvc
from zzmw_lib.logs import build_logger
from zzmw_lib.service_runner import service_runner_with_www

from zz2m.z2mproxy import Z2MProxy
from zz2m.www import Z2Mwebservice

from sensors import SensorsHistory

import os
import pathlib

log = build_logger("ZmwSensormon")

# 'linkquality' can be monitored too, but that means we're monitoring a lot more than sensors
INTERESTING_ACTIONS = [
    'ac_frequency', 'battery', 'contact', 'current_a', 'current_b', 'device_temperature',
    'energy_a', 'energy_b', 'energy_flow_a', 'energy_flow_b', 'energy_produced_a', 'energy_produced_b',
    'humidity', 'occupancy', 'pm25', 'power_a', 'power_ab', 'power_b', 'power_factor_a',
    'power_factor_b', 'temperature', 'voc_index', 'voltage']

def interesting_actions(thing):
    """Filter actions to return only those that are interesting sensors to monitor."""
    acts = []
    for action_name in thing.actions:
        if action_name in INTERESTING_ACTIONS:
            acts.append(action_name)
    return acts

class ShellyAdapter:
    """Adapts Shelly plug MQTT payloads to the thing interface expected by SensorsHistory."""
    METRICS = [
        'active_power_watts', 'voltage_volts', 'current_amps', 'device_temperature',
        'lifetime_energy_use_watt_hour', 'last_minute_energy_use_watt_hour'
    ]
    # Map payload keys to metric names (for renaming)
    PAYLOAD_TO_METRIC = {
        'temperature_c': 'device_temperature',
    }

    def __init__(self, name):
        self.name = name
        self.actions = {m: None for m in self.METRICS}
        self.on_any_change_from_mqtt = None
        self._values = {}

    def get(self, metric_name):
        return self._values.get(metric_name)

    def update(self, payload):
        for metric in self.METRICS:
            payload_key = next((k for k, v in self.PAYLOAD_TO_METRIC.items() if v == metric), metric)
            if payload_key in payload:
                self._values[metric] = payload[payload_key]
        if self.on_any_change_from_mqtt:
            self.on_any_change_from_mqtt(self)


class ShellyPlugMonitor:
    """Monitors Shelly plug devices and records their stats to sensor history."""

    def __init__(self, sensors):
        self._sensors = sensors
        self._known_shellies = {}

    def get_current_values(self, name):
        """Returns current values for a Shelly device, or None if not known."""
        if name not in self._known_shellies:
            return None
        adapter = self._known_shellies[name]
        return {metric: adapter.get(metric) for metric in ShellyAdapter.METRICS}

    def on_message(self, topic, payload):
        parts = topic.split('/')
        if len(parts) != 2:
            log.warning("Unexpected shelly topic format '%s': %s", topic, payload)
            return
        sensor_name, action = parts

        if action != 'stats':
            log.warning("Unhandled action '%s': %s", topic, payload)
            return

        if sensor_name not in self._known_shellies:
            adapter = ShellyAdapter(sensor_name)
            self._known_shellies[sensor_name] = adapter
            self._sensors.register_sensor(adapter, ShellyAdapter.METRICS)
            log.info("New shelly plug discovered: %s", sensor_name)

        self._known_shellies[sensor_name].update(payload)


class ZmwSensormon(ZmwMqttNullSvc):
    """MQTT service for monitoring sensor data and maintaining history."""
    def __init__(self, cfg, www):
        super().__init__(cfg)
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)

        self._sensors = SensorsHistory(dbpath=cfg['db_path'], retention_days=cfg['retention_days'])
        self._sensors.register_to_webserver(www)

        self._z2m = Z2MProxy(cfg, self,
                             cb_on_z2m_network_discovery=self._on_z2m_network_discovery,
                             cb_is_device_interesting=lambda t: len(interesting_actions(t)) > 0)
        self._z2mw = Z2Mwebservice(www, self._z2m)

        self._shelly_monitor = ShellyPlugMonitor(self._sensors)
        self.subscribe_with_cb('zmw_shelly_plug', self._shelly_monitor.on_message)
        www.serve_url('/sensors/get/<name>', self._get_sensor_values)

    def _get_sensor_values(self, name):
        """Unified endpoint to get current sensor values from any backend."""
        shelly_data = self._shelly_monitor.get_current_values(name)
        if shelly_data is not None:
            return shelly_data
        try:
            return self._z2m.get_thing(name).get_json_state()
        except KeyError:
            return {}

    def _on_z2m_network_discovery(self, _is_first_discovery, known_things):
        for thing_name, thing in known_things.items():
            acts = interesting_actions(thing)
            if len(acts) > 0:
                log.info('Will monitor %s, publishes %s', thing_name, str(acts))
                self._sensors.register_sensor(thing, acts)

service_runner_with_www(ZmwSensormon)
