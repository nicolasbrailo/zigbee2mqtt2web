import json
import os
import pathlib
from datetime import datetime
from collections import deque

from zzmw_lib.mqtt_proxy import MqttServiceClient
from zzmw_lib.service_runner import service_runner_with_www, build_logger

from zz2m.z2mproxy import Z2MProxy
from zz2m.light_helpers import turn_all_lights_off
from zz2m.www import Z2Mwebservice

from apscheduler.triggers.cron import CronTrigger

log = build_logger("ZmwLights")


class ZmwLights(MqttServiceClient):
    def __init__(self, cfg, www):
        super().__init__(cfg, svc_deps=['zmw_telegram'])

        self._lights = []

        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)
        www.serve_url('/get_lights', self.get_lights)

        self._z2m = Z2MProxy(cfg, self,
                             cb_on_z2m_network_discovery=self._on_z2m_network_discovery,
                             cb_is_device_interesting=lambda t: t.thing_type == 'light')
        self._z2mw = Z2Mwebservice(www, self._z2m)


    def _on_z2m_network_discovery(self, _is_first_discovery, known_things):
        log.info("Z2M network discovered, there are %d lights", len(known_things))
        self._lights = self._z2m.get_all_registered_things()
        # TODO get delta between old and new lights, if it changed announce the changes
        for light in self._lights:
            log.info("Discovered light %s", light.name)

    def get_service_meta(self):
        return {
            "name": "zmw_lights",
            "mqtt_topic": None,
            "methods": [],
            "announces": [],
            "www": self._public_url_base,
        }

    def get_lights(self):
        return [l.get_json_state() for l in self._lights]

service_runner_with_www(ZmwLights)
