import os
import pathlib

from zzmw_lib.zmw_mqtt_nullsvc import ZmwMqttNullSvc
from zzmw_lib.logs import build_logger
from zzmw_lib.service_runner import service_runner_with_www

from zz2m.z2mproxy import Z2MProxy
from zz2m.www import Z2Mwebservice

log = build_logger("ZmwLights")

class ZmwLights(ZmwMqttNullSvc):
    def __init__(self, cfg, www):
        super().__init__(cfg)
        self._lights = []

        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        www.register_www_dir(www_path)
        www.serve_url('/get_lights', lambda: [l.get_json_state() for l in self._lights])

        self._z2m = Z2MProxy(cfg, self,
                             cb_on_z2m_network_discovery=self._on_z2m_network_discovery,
                             cb_is_device_interesting=lambda t: t.thing_type == 'light')
        self._z2mw = Z2Mwebservice(www, self._z2m)


    def _on_z2m_network_discovery(self, is_first_discovery, known_things):
        log.info("Z2M network discovered, there are %d lights", len(known_things))
        old_light_names = {light.name for light in self._lights}
        self._lights = self._z2m.get_all_registered_things()
        new_light_names = {light.name for light in self._lights}

        if not is_first_discovery and old_light_names != new_light_names:
            added = new_light_names - old_light_names
            removed = old_light_names - new_light_names
            if added:
                log.warning("New lights discovered: %s", ', '.join(added))
            if removed:
                log.warning("Lights no longer available: %s", ', '.join(removed))

        for light in self._lights:
            log.info("Discovered light %s", light.name)

service_runner_with_www(ZmwLights)
