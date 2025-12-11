"""Cronenberg service for scheduled home automation tasks."""
import json
import os
import pathlib
from datetime import datetime
from collections import deque

from zzmw_lib.mqtt_proxy import MqttServiceClient
from zzmw_lib.service_runner import service_runner_with_www, build_logger

from zz2m.z2mproxy import Z2MProxy
from zz2m.light_helpers import turn_all_lights_off

from apscheduler.triggers.cron import CronTrigger

log = build_logger("ZmwCronenberg")


class ZmwCronenberg(MqttServiceClient):
    """
    Scheduled tasks service. Runs calendar-based automation like:
    - Turning off lights at specific times
    - Sending notifications about scheduled events
    """

    def __init__(self, cfg, www):
        super().__init__(cfg, svc_deps=['zmw_telegram'])
        self._z2m = Z2MProxy(cfg, self, cb_on_z2m_network_discovery=self.on_z2m_network_discovery)

        self._light_check_history = deque(maxlen=10)

        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)
        www.serve_url('/stats', self.get_stats)

        # Schedule the 9 AM weekday light check
        log.info("Scheduling light check for weekdays at 9:00 AM")
        self._scheduler.add_job(
            self.check_and_turn_off_lights,
            trigger=CronTrigger(day_of_week='mon-fri', hour=9, minute=0, second=0),
            id='weekday_morning_lights_off'
        )

    def on_z2m_network_discovery(self, _is_first_discovery, known_things):
        """
        Callback when Z2M network is discovered.
        """
        log.info("Z2M network discovered, there are %d things", len(known_things))

    def get_service_meta(self):
        return {
            "name": "zmw_cronenberg",
            "mqtt_topic": None,
            "methods": [],
            "announces": [],
            "www": self._public_url_base,
        }

    def get_stats(self):
        """Flask endpoint to serve light check statistics"""
        return json.dumps(list(self._light_check_history), default=str)

    def check_and_turn_off_lights(self):
        """
        Check which lights are on, turn them off, and send a notification.
        Runs at 9:00 AM on weekdays.
        """
        lights_on = self._z2m.get_things_if(lambda t: t.thing_type == 'light' and t.is_light_on())

        # Track this check in history
        check_event = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            'lights_forgotten': len(lights_on) > 0,
            'lights_left_on': [l.name for l in lights_on] if len(lights_on) > 0 else []
        }
        self._light_check_history.append(check_event)

        if len(lights_on) == 0:
            log.info("Light checker: no lights forgot on, nothing to do")
            return

        turn_all_lights_off(self._z2m)
        names = ", ".join([l.name for l in lights_on])
        msg = f'Someone forgot the lights on. Will turn off {names}'
        self.message_svc("zmw_telegram", "send_text", {'msg': msg})
        log.info(msg)


service_runner_with_www(ZmwCronenberg)
