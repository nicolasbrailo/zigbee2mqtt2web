import os
import pathlib
import threading
import json

from shelly import ShellyPlug

from zzmw_lib.service_runner import service_runner_with_www
from zzmw_lib.zmw_mqtt_service import ZmwMqttService
from zzmw_lib.logs import build_logger

log = build_logger("ZmwShellyPlug")

class ZmwShellyPlug(ZmwMqttService):
    def __init__(self, cfg, www):
        super().__init__(cfg, svc_topic="zmw_shelly_plug")
        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)

        self._devices = [ShellyPlug(host) for host in cfg["devices_to_monitor"]]
        self._bcast_period_secs = cfg["bcast_period_secs"]
        self._timer = None

        www.serve_url('/ls_devs', lambda: [d.get_name() for d in self._devices])
        www.serve_url('/all_stats', lambda: {d.get_name(): d.get_stats() for d in self._devices})
        self._bcast()

    def _bcast(self):
        self._timer = threading.Timer(self._bcast_period_secs, self._bcast)
        self._timer.start()
        for dev in self._devices:
            stats = dev.get_stats()
            self.publish_own_svc_message(f'{stats["device_name"]}/stats', stats)

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None
        super().stop()

    def on_service_received_message(self, subtopic, msg):
        # Ignore: we'll receive an echo of our own messages here
        pass

    def on_dep_published_message(self, svc_name, subtopic, msg):
        log.error("Unexpected dep message %s %s", subtopic, msg)


service_runner_with_www(ZmwShellyPlug)
