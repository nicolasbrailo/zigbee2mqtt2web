"""Sensor monitoring and history service."""
from zzmw_lib.zmw_mqtt_nullsvc import ZmwMqttNullSvc
from zzmw_lib.logs import build_logger
from zzmw_lib.service_runner import service_runner

from zz2m.z2mproxy import Z2MProxy
from zz2m.www import Z2Mwebservice

from sensors import SensorsHistory
from virtual_metrics import get_virtual_metrics, compute_virtual_metrics

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

    def __init__(self, name, sensors_history):
        self.name = name
        self._sensors = sensors_history
        self._values = {}

    def get(self, metric_name):
        """Return the current value for a metric."""
        return self._values.get(metric_name)

    def update(self, payload):
        """Update internal values from a Shelly MQTT payload and save to DB."""
        for metric in self.METRICS:
            payload_key = next((k for k, v in self.PAYLOAD_TO_METRIC.items() if v == metric), metric)
            if payload_key in payload:
                self._values[metric] = payload[payload_key]
        self._sensors.save_reading(self.name, {m: self.get(m) for m in self.METRICS})


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
        """Handle incoming Shelly MQTT messages and update sensor history."""
        parts = topic.split('/')
        if len(parts) != 2:
            log.warning("Unexpected shelly topic format '%s': %s", topic, payload)
            return
        sensor_name, action = parts

        if action != 'stats':
            log.warning("Unhandled action '%s': %s", topic, payload)
            return

        if sensor_name not in self._known_shellies:
            try:
                self._sensors.register_sensor(sensor_name, ShellyAdapter.METRICS)
                self._known_shellies[sensor_name] = ShellyAdapter(sensor_name, self._sensors)
                log.info("New shelly plug discovered: %s", sensor_name)
            except ValueError:
                log.error("New sensor '%s' can't be registered. This may be normal if a Shelly plug has no known name yet",
                          sensor_name, exc_info=True)
                return

        self._known_shellies[sensor_name].update(payload)


class ZmwSensormon(ZmwMqttNullSvc):
    """MQTT service for monitoring sensor data and maintaining history."""
    def __init__(self, cfg, www, sched):
        super().__init__(cfg)
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)

        self._sensors = SensorsHistory(dbpath=cfg['db_path'], scheduler=sched, retention_days=cfg['retention_days'])
        self._sensors.register_to_webserver(www)

        self._z2m = Z2MProxy(cfg, self, sched,
                             cb_on_z2m_network_discovery=self._on_z2m_network_discovery,
                             cb_is_device_interesting=lambda t: len(interesting_actions(t)) > 0)
        self._z2mw = Z2Mwebservice(www, self._z2m)

        self._shelly_monitor = ShellyPlugMonitor(self._sensors)
        self.subscribe_with_cb('zmw_shelly_plug', self._shelly_monitor.on_message)
        www.serve_url('/sensors/get/<name>', self._get_sensor_values)
        www.serve_url('/sensors/get_all/<metric>', self._get_all_sensor_values)

    def _get_sensor_values(self, name):
        """Unified endpoint to get current sensor values from any backend."""
        shelly_data = self._shelly_monitor.get_current_values(name)
        if shelly_data is not None:
            return shelly_data
        try:
            return self._z2m.get_thing(name).get_json_state()
        except KeyError:
            return {}

    def _get_all_sensor_values(self, metric):
        """Get current values for all sensors measuring a specific metric."""
        sensors = self._sensors.get_known_sensors_measuring(metric)
        result = {}
        for sensor_name in sensors:
            values = self._get_sensor_values(sensor_name)
            if metric in values:
                result[sensor_name] = values[metric]
        return result

    def _on_sensor_update(self, thing):
        """Handle sensor update: save to DB with virtual metrics."""
        metrics = interesting_actions(thing)
        values = {m: thing.get(m) for m in metrics}
        virtual_values = compute_virtual_metrics(values)
        self._sensors.save_reading(thing.name, {**values, **virtual_values})

    def _on_z2m_network_discovery(self, _is_first_discovery, known_things):
        for thing_name, thing in known_things.items():
            acts = interesting_actions(thing)
            if len(acts) > 0:
                virtual_metrics = get_virtual_metrics(acts)
                all_metrics = acts + virtual_metrics
                log.info('Will monitor %s, publishes %s (virtual: %s)', thing_name, str(acts), str(virtual_metrics))
                try:
                    self._sensors.register_sensor(thing.name, all_metrics)
                    thing.on_any_change_from_mqtt = self._on_sensor_update
                except ValueError as ex:
                    # This will happen if a sensor has a name we don't like. Usually will happen when a new device
                    # is added to the network, before it gets a friendly name
                    log.error("Can't register sensor %s: %s", thing.name, ex)

service_runner(ZmwSensormon)
