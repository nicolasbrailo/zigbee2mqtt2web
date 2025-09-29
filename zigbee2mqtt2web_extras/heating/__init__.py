from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, time, timedelta
import logging
import os
import pathlib
import sys

sys.path.append(os.path.join(pathlib.Path(__file__).parent.resolve(), "zigbee2mqtt2web"))

from zigbee2mqtt2web_extras.phony import PhonyZMWThing

from .schedule import ScheduleSlot
from .rules import create_rules_from_config
from .schedule_builder import ScheduleBuilder, AllowOn
from ._hijack_thing_as_boiler import _hijack_thing_as_boiler

log = logging.getLogger(__name__)

_WWW_LOG_ENDPOINT = '/heating/log'

class Heating(PhonyZMWThing):
    def __init__(self, cfg, zmw):
        self.log_file = cfg['log_path']
        self.schedule_file = cfg['schedule_persist_file']
        self.boiler_name = cfg['boiler_mqtt_thing_name']
        self.zmw = zmw
        self.boiler = None
        self.pending_state = None

        #log_file = logging.FileHandler(self.log_file, mode='w')
        log_file = logging.TimedRotatingFileHandler(self.log_file, when='midnight', backupCount=3)
        log_file.setLevel(logging.DEBUG)
        log_file.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        log.addHandler(log_file)
        log.info("BatiCasa heating manager starting...")

        super().__init__(
            name="Heating",
            description="Heating controller",
            thing_type="heating",
        )

        self.schedule = ScheduleBuilder(self._on_boiler_state_should_change, self.schedule_file, create_rules_from_config(zmw, cfg['rules']))
        self._schedule_tick_interval_secs = 60 * 3

        self._add_action('active_schedule', 'Get the schedule for the next 24 hours',
                         getter=self.schedule.active().as_jsonifyable_dict)
        self._add_action('boost', 'Boost heating for a number of hours',
                         setter=self.schedule.active().boost)
        self._add_action('off_now', 'Heating off until the end of the current block',
                         setter=lambda _: self.schedule.active().off_now())
        self._add_action('slot_toggle', 'Toggle a specific slot on or off',
                         setter=self.schedule.active().toggle_slot_by_name)
        self._add_action('template_schedule', 'Get the schedule template (and active schedule) as json',
                         getter=self.schedule.as_json)
        self._add_action('template_slot_set', 'Set a slot for the schedule template',
                         setter=lambda vs: self.schedule.set_slot(*vs.split(',')))
        self._add_action('template_apply', 'Apply template to today\'s schedule, overwrite user settings',
                         setter=lambda _: self.schedule.apply_template_to_today())
        self._add_action('template_reset', "Reset the template to default (doesn't change active schedule)",
                         setter=self.schedule.reset_template)
        self._add_action('log_url', 'Retrieve heating logs',
                         getter=lambda: _WWW_LOG_ENDPOINT)

        self.zmw.webserver.add_url_rule(_WWW_LOG_ENDPOINT, self._www_log)
        self.zmw.registry.on_mqtt_network_discovered(self._on_mqtt_net_discovery_cb)

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()

    def get_json_state(self):
        tsched = self.schedule.active().as_jsonifyable_dict()
        return {
            "active_schedule": tsched,
            "allow_on": tsched[0]['allow_on'],
            "mqtt_thing_reports_on": self.boiler.get('boiler_state'),
        }

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
        self._scheduler.add_job(func=self._on_boiler_discovered, trigger="date",
                                run_date=datetime.now() + timedelta(seconds=3))

    def _on_boiler_discovered(self):
        try:
            self.boiler = self.zmw.registry.get_thing(self.boiler_name)
            _hijack_thing_as_boiler(self.zmw, self.boiler)
            log.info("BatiCasa heating manager started. Heating state %s link %s PowerOn %s",
                      self.boiler.get('boiler_state'),
                      self.boiler.get('linkquality'),
                      self.boiler.get('power_on_behavior'))
            # Register self only after a boiler is discovered
            self.zmw.registry.register(self)
            if self.pending_state is not None:
                log.info("Boiler discovered, applying pending state...")
                self._on_boiler_state_should_change(new=self.pending_state, old=ScheduleSlot(hour=0, minute=0))

            self._scheduler.add_job(func=self._tick, trigger="date", run_date=self.schedule.active().get_slot_change_time())
            # Tick every few minutes, just in case there's a bug in scheduling somewhere and to verify
            # the state of the mqtt thing
            self._scheduler.add_job(func=self._tick, trigger="interval",
                                    seconds=self._schedule_tick_interval_secs, next_run_time=datetime.now())
        except Exception:
            self.boiler = None
            log.fatal("Boiler discovered, but boiler manager startup failed. Heating control not available", exc_info=True)

    def _tick(self):
        # TODO: Check MQTT thing
        advanced_slot = self.schedule.tick()
        if advanced_slot:
            self._scheduler.add_job(func=self._tick, trigger="date", run_date=self.schedule.active().get_slot_change_time())

    def _on_boiler_state_should_change(self, new, old):
        if self.boiler is None:
            log.error("Boiler state changed to %s (reason: %s), but no boiler is known yet", new.request_on, new.reason)
            self.pending_state = new
            return

        log.info("Boiler state changed to %s, notifying MQTT thing (Policy: %s, reason: %s)", new.request_on, new.allow_on, new.reason)
        self.boiler.set('boiler_state', new.request_on)
        self.zmw.registry.broadcast_thing(self.boiler)

        self.zmw.announce_system_event({
            'event': 'on_boiler_state_change',
            'new_request_on': new.request_on,
            'old_request_on': old.request_on,
            'new_allow_on': new.allow_on,
            'old_allow_on': old.allow_on,
            'new_reason': new.reason,
            'old_reason': old.reason,
        })

    def _www_log(self):
        try:
            with open(self.log_file, 'r') as fp:
                return '<pre>' + fp.read()
        except Exception as ex:
            return f"Can't get heating logs: {ex}", 500
