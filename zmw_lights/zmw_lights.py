""" Expose a set of lights form zigbee2mqtt over a rest endpoint """
import os
import pathlib

from zzmw_lib.zmw_mqtt_nullsvc import ZmwMqttNullSvc
from zzmw_lib.logs import build_logger
from zzmw_lib.service_runner import service_runner

from zz2m.z2mproxy import Z2MProxy
from zz2m.www import Z2Mwebservice

log = build_logger("ZmwLights")

class ZmwLights(ZmwMqttNullSvc):
    """ ZmwService for REST lights """
    def __init__(self, cfg, www, sched):
        super().__init__(cfg)
        self._lights = []
        self._switches = []

        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        www.register_www_dir(www_path)
        www.serve_url('/all_lights_on/prefix/<prefix>', self._all_lights_on, methods=['PUT'])
        www.serve_url('/all_lights_off/prefix/<prefix>', self._all_lights_off, methods=['PUT'])
        www.serve_url('/get_lights', lambda: [l.get_json_state() for l in self._lights])
        www.serve_url('/get_switches', lambda: [s.get_json_state() for s in self._switches])

        self._z2m = Z2MProxy(cfg, self, sched,
                             cb_on_z2m_network_discovery=self._on_z2m_network_discovery,
                             cb_is_device_interesting=lambda t: t.thing_type in ('light', 'switch'))
        self._z2mw = Z2Mwebservice(www, self._z2m)


    def _on_z2m_network_discovery(self, is_first_discovery, known_things):
        all_things = self._z2m.get_all_registered_things()
        new_lights = [t for t in all_things if t.thing_type == 'light']
        new_switches = [t for t in all_things if t.thing_type == 'switch']

        log.info("Z2M network discovered, there are %d lights and %d switches",
                 len(new_lights), len(new_switches))

        old_light_names = {light.name for light in self._lights}
        new_light_names = {light.name for light in new_lights}
        old_switch_names = {switch.name for switch in self._switches}
        new_switch_names = {switch.name for switch in new_switches}

        if not is_first_discovery:
            if old_light_names != new_light_names:
                added = new_light_names - old_light_names
                removed = old_light_names - new_light_names
                if added:
                    log.warning("New lights discovered: %s", ', '.join(added))
                if removed:
                    log.warning("Lights no longer available: %s", ', '.join(removed))
            if old_switch_names != new_switch_names:
                added = new_switch_names - old_switch_names
                removed = old_switch_names - new_switch_names
                if added:
                    log.warning("New switches discovered: %s", ', '.join(added))
                if removed:
                    log.warning("Switches no longer available: %s", ', '.join(removed))

        self._lights = new_lights
        self._switches = new_switches

        for light in self._lights:
            log.info("Discovered light %s", light.name)
        for switch in self._switches:
            log.info("Discovered switch %s", switch.name)

    def _all_lights_on(self, prefix):
        ls = self._z2m.get_things_if(lambda t: t.thing_type == 'light' and t.name.startswith(prefix))
        for l in ls:
            l.set_brightness_pct(80)
            l.turn_on()
        self._z2m.broadcast_things(ls)
        return {}

    def _all_lights_off(self, prefix):
        ls = self._z2m.get_things_if(lambda t: t.thing_type == 'light' and t.name.startswith(prefix))
        for l in ls:
            l.turn_off()
        self._z2m.broadcast_things(ls)
        return {}

service_runner(ZmwLights)
