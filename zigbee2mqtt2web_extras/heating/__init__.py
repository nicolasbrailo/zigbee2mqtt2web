from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, time, timedelta
import logging
import os
import pathlib
import sys

sys.path.append(os.path.join(pathlib.Path(__file__).parent.resolve(), "zigbee2mqtt2web"))

from zigbee2mqtt2web_extras.phony import PhonyZMWThing

from .schedule import Schedule
from ._hijack_thing_as_boiler import _hijack_thing_as_boiler

log = logging.getLogger(__name__)

class Heating(PhonyZMWThing):
    def _print_stat_change(self, new, old):
        # TODO: Delay until boiler is found
        if self.boiler is not None:
            self.boiler.set('boiler_state', new.should_be_on)
            self.zmw.registry.broadcast_thing(self.boiler)

    def __init__(self, zmw):
        super().__init__(
            name="Heating",
            description="Heating controller",
            thing_type="heating",
        )

        self.zmw = zmw
        self.log_file = '/home/batman/BatiCasa/heating.log'
        #self.boiler_name = 'Boiler'
        self.boiler_name = 'Batioficina'
        self.boiler = None

        log_file = logging.FileHandler(self.log_file, mode='w')
        log_file.setLevel(logging.DEBUG)
        log_file.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        log.addHandler(log_file)
        log.info("BatiCasa heating manager starting...")

        self.schedule = Schedule(self._print_stat_change)

        self._add_action('schedule', 'Get the schedule for the next 24 hours',
                         getter=self.schedule.as_table)
        self._add_action('boost', 'Boost heating for a number of hours',
                         setter=self.schedule.boost)
        self._add_action('off_now', 'Heating off until the end of the current block',
                         setter=lambda _: self.schedule.off_now())
        self._add_action('slot_toggle', 'Toggle a specific slot on or off',
                         setter=self.schedule.toggle_slot_by_name)

        self.zmw.webserver.add_url_rule('/heating/log', self._www_log)
        self.zmw.registry.on_mqtt_network_discovered(self._on_mqtt_net_discovery_cb)

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()

    def get_json_state(self):
        return {"schedule": self.schedule.as_table()}

    def _on_mqtt_net_discovery_cb(self):
        if self.boiler is not None:
            try:
                self.zmw.registry.get_thing(self.boiler_name)
                log.debug("MQTT network published update, boiler didn't change")
                return
            except KeyError:
                self.boiler = None
                log.error("MQTT network published update, boiler named %s is now gone", self.boiler_name)
                return

        try:
            boiler = self.zmw.registry.get_thing(self.boiler_name)
            log.debug("MQTT network discovered, found boiler %s...", self.boiler_name)
        except KeyError:
            log.error("MQTT network discovered, but there is no known boiler named %s", self.boiler_name)
            return

        # Delay processing until after network settles and we get boiler state/info
        self.zmw.registry._mqtt.update_thing_state(self.boiler_name)

        def _on_boiler_discovered():
            _hijack_thing_as_boiler(self.zmw, boiler)
            log.info("BatiCasa heating manager started. Heating state %s link %s PowerOn %s",
                      boiler.get('boiler_state'),
                      boiler.get('linkquality'),
                      boiler.get('power_on_behavior'))
            # Assign boiler only after all hacks applied - doing it before may break, as the thing won't have
            # the expected API
            self.boiler = boiler
            self.zmw.registry.register(self)
        self._scheduler.add_job(func=_on_boiler_discovered, trigger="date", run_date=datetime.now() + timedelta(seconds=3))

    def _www_log(self):
        try:
            with open(self.log_file, 'r') as fp:
                return '<pre>' + fp.read()
        except Exception as ex:
            return f"Can't get heating logs: {ex}", 500

