import os
import pathlib
from flask import abort

from zzmw_lib.service_runner import service_runner_with_www
from zzmw_lib.zmw_mqtt_service import ZmwMqttService
from zzmw_lib.logs import build_logger
from zz2m.z2mproxy import Z2MProxy
from zz2m.www import Z2Mwebservice

from config_enforcer import ConfigEnforcer
from dispense_tracking import DispenseTracking
from history import DispensingHistory
from schedule import DispensingSchedule

log = build_logger("ZmwCatSnackDispenser")

class ZmwCatSnackDispenser(ZmwMqttService):
    def __init__(self, cfg, www):
        super().__init__(cfg, svc_topic="zmw_cat_feeder", svc_deps=["ZmwTelegram"])
        self._z2m_cat_feeder_name = cfg["z2m_cat_feeder"]

        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)

        history = DispensingHistory(self._z2m_cat_feeder_name, history_len=10,
                                         cb_on_dispense=self._notify_dispense_event)
        schedule = DispensingSchedule(self._z2m_cat_feeder_name, history, self.feed_now,
                                            cfg["feeding_schedule"], cfg["schedule_tolerance_secs"])
        self._dispense_tracking = DispenseTracking(history, schedule)
        self._config_enforcer = ConfigEnforcer(backoff_secs=1, schedule=self._dispense_tracking)

        self._cat_feeder = None

        self._z2m = Z2MProxy(cfg, self,
                             cb_on_z2m_network_discovery=self._on_z2m_network_discovery,
                             cb_is_device_interesting=lambda t: t.name == self._z2m_cat_feeder_name)
        self._z2mw = Z2Mwebservice(www, self._z2m)

        www.serve_url('/feed_now', lambda: self.feed_now(source="User requested via WWW"))
        www.serve_url('/feed_history', self._dispense_tracking.get_history)
        www.serve_url('/feed_schedule', self._dispense_tracking.get_schedule)

    def get_service_alerts(self):
        if self._cat_feeder is None:
            return [f"No cat-feeder thing named {self._z2m_cat_feeder_name} found!"]
        return []

    def on_service_came_up(self, service_name):
        if service_name == "ZmwTelegram":
            self.message_svc("ZmwTelegram",
                             "register_command", {'cmd': 'DispenseCatSnacks', 'descr': 'Feed the cat'})

    def on_service_received_message(self, subtopic, payload):  # pylint: disable=unused-argument
        # Ignore: we'll receive an echo of our own messages here
        pass

    def on_dep_published_message(self, svc_name, subtopic, payload):  # pylint: disable=unused-argument
        if svc_name == 'ZmwTelegram' and subtopic.startswith("on_command/DispenseCatSnacks"):
            self.feed_now(source="Telegram")

    def _notify_dispense_event(self, source, error, portions_dispensed):
        if error is not None and (portions_dispensed is None or portions_dispensed == 0):
            msg = f"Error for {source} dispense on {self._z2m_cat_feeder_name}: {error}"
        else:
            if portions_dispensed is None:
                quantity = "an unknown quantity of snacks"
            elif portions_dispensed == 1:
                quantity = "1 snack"
            else:
                quantity = f"{portions_dispensed} snacks"
            msg = f"{source}: purveying {quantity} on {self._z2m_cat_feeder_name}."
            if error is not None:
                msg += f" (Warning: {error})"

        self.message_svc("ZmwTelegram", "send_text", {'msg': msg})

    ### Z2M behaviour ###
    def _on_z2m_network_discovery(self, _is_first_discovery, known_things):
        if self._z2m_cat_feeder_name not in known_things:
            log.critical("No cat feeder '%s' found in the network, cat will be angry", self._z2m_cat_feeder_name)

        log.info("Cat feeder '%s' found, this service will manage it", self._z2m_cat_feeder_name)
        self._cat_feeder = known_things[self._z2m_cat_feeder_name]
        self._config_enforcer.ensure_config(self._cat_feeder, correct_if_bad=True)
        self._z2m.broadcast_thing(self._cat_feeder)
        # Set callback after ensuring unit config; messages are delivered async so it's likely we'll be here before
        # any unit has had a chance to reply back through the network, this won't help prevent callback loops
        self._cat_feeder.on_any_change_from_mqtt = self._z2m_thing_bcasting

    def _z2m_thing_bcasting(self, _msg):
        self._dispense_tracking.check_dispensing(self._cat_feeder)
        self._config_enforcer.ensure_config(self._cat_feeder, correct_if_bad=True)
        self._z2m.broadcast_thing(self._cat_feeder)

    def feed_now(self, source="unknown", serving_size=None):
        if not self._dispense_tracking.request_feed_now(source, self._cat_feeder, serving_size):
            return abort(409, description="Can't request food now, another request may be in progress.")
        self._z2m.broadcast_thing(self._cat_feeder)
        return {}

service_runner_with_www(ZmwCatSnackDispenser)
