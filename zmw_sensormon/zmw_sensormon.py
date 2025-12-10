"""Sensor monitoring and history service."""
from zzmw_lib.mqtt_proxy import MqttServiceClient
from zzmw_lib.service_runner import service_runner_with_www, build_logger

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

class ZmwSensormon(MqttServiceClient):
    """MQTT service for monitoring sensor data and maintaining history."""
    def __init__(self, cfg, www):
        super().__init__(cfg, svc_deps=[])
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)

        self._sensors = SensorsHistory(dbpath=cfg['db_path'], retention_days=cfg['retention_days'])
        self._sensors.register_to_webserver(www)

        self._z2m = Z2MProxy(cfg, self,
                             cb_on_z2m_network_discovery=self._on_z2m_network_discovery,
                             cb_is_device_interesting=lambda t: len(interesting_actions(t)) > 0)
        self._z2mw = Z2Mwebservice(www, self._z2m)

    def get_service_meta(self):
        return {
            "name": "zmw_sensormon",
            "mqtt_topic": None,
            "methods": [],
            "announces": [],
            "www": self._public_url_base,
        }

    def _on_z2m_network_discovery(self, _is_first_discovery, known_things):
        for thing_name, thing in known_things.items():
            acts = interesting_actions(thing)
            if len(acts) > 0:
                log.info('Will monitor %s, publishes %s', thing_name, str(acts))
                self._sensors.register_sensor(thing, acts)

service_runner_with_www(ZmwSensormon)
