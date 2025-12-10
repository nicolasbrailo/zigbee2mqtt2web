"""Doorbell event handler and notification service."""
import time
import threading

from geo_helpers import is_sun_out

from zzmw_lib.mqtt_proxy import MqttServiceClient
from zzmw_lib.service_runner import service_runner_with_www, build_logger
from zz2m.z2mproxy import Z2MProxy

log = build_logger("ZmwDoorman")

class DoorOpenSceneLightManager:
    def __init__(self, cfg, mqtt_client):
        self._wanted_things = cfg["door_open_scene_thing_to_manage"]
        self._known_things = {}
        self._managing_things = {}
        self._ignoring_updates_until = None
        self._ignore_updates_secs = 3
        self._z2m = Z2MProxy(cfg, mqtt_client,
                             cb_on_z2m_network_discovery=self._on_z2m_network_discovery,
                             cb_is_device_interesting=lambda t: t.name in self._wanted_things)

    def _on_z2m_network_discovery(self, _is_first_discovery, known_things):
        log.info("Z2M network discovered, monitoring %d things: %s", len(known_things), list(known_things.keys()))
        for thing_name in self._wanted_things:
            if thing_name not in known_things:
                log.error("Thing %s missing, door-open scene may not work as expected", thing_name)

        for _, thing in known_things.items():
            if thing.thing_type != 'light':
                log.error("Asked to monitor %s for door-open scene, but it's not a light", thing_name)
            else:
                self._known_things[thing.name] = thing
                thing.on_any_change_from_mqtt = lambda t=thing: self._light_received_mqtt_update(t)

    def _light_received_mqtt_update(self, thing):
        if thing.name not in self._managing_things:
            return
        if self._ignoring_updates_until is not None and time.time() < self._ignoring_updates_until:
            # When the light is turned on, we're going to get callbacks here. There is no way to distinguish
            # an external update from an update triggered by an internal sync.
            return
        del self._managing_things[thing.name]
        log.info("Thing %s is not managed anymore, something else started using it", thing.name)

    def start(self):
        """ Starts the door-open scene: it will turn on all of the managed lights, until stop() is called. If other
        service starts making use of this light, it will stop being managed (we will ignore it during the stop()
        phase """
        for _, thing in self._known_things.items():
            if thing.is_light_on():
                log.info("Won't apply door-open scene to %s, something else is using this light", thing.name)
                continue
            thing.turn_on()
            self._managing_things[thing.name] = thing
        self._ignoring_updates_until = time.time() + self._ignore_updates_secs
        self._z2m.broadcast_things(self._managing_things.keys())

    def stop(self):
        """ Stop scene: all lights that are still managed will be shut down """
        log.info("Door-open scene expired, turn off lights")
        # Ignore self-updates for a few secs
        self._ignoring_updates_until = time.time() + self._ignore_updates_secs
        # TODO add mutex
        for _, thing in self._managing_things.items():
            log.info("Door-open scene timeout, shutdown %s", thing.name)
            thing.turn_off()
        self._z2m.broadcast_things(self._managing_things.keys())
        self._managing_things = {}

class DoorOpenScene:
    def __init__(self, cfg, mqtt_client):
        self._light_mgr = DoorOpenSceneLightManager(cfg, mqtt_client)
        self._door_open_scene_timer = None
        self._door_open_scene_timeout_secs = cfg["door_open_scene_timeout_secs"]
        self._latlon = cfg["latlon"]
        _ = is_sun_out(self._latlon[0], self._latlon[1])

    def maybe_start(self):
        """ Door has opened, check if we need to launch a door-open scene or not """
        if is_sun_out(self._latlon[0], self._latlon[1]):
            log.debug("DoorOpenScene won't start, there is enough light outside")
            return

        if self._door_open_scene_timer is not None:
            return self._pet_door_open_scene_timer()

        log.debug("DoorOpenScene starting, it is dark outside")
        self._door_open_scene_timer = threading.Timer(
            self._door_open_scene_timeout_secs,
            self._on_door_open_scene_timeout
        )
        self._door_open_scene_timer.start()
        self._light_mgr.start()

    def pet_timer(self):
        """ Something happened that should extend the door-open scene """
        if self._door_open_scene_timer is None:
            # Trying to reset timer, but no timer is active
            return
        self._door_open_scene_timer.cancel()
        log.debug("DoorOpenScene timeout has been extended")
        self._door_open_scene_timer = threading.Timer(
            self._door_open_scene_timeout_secs,
            self._on_door_open_scene_timeout
        )
        self._door_open_scene_timer.start()


    def _on_door_open_scene_timeout(self):
        """ Called when the door-open scene timer expires """
        self._door_open_scene_timer = None
        self._light_mgr.stop()


class ZmwDoorman(MqttServiceClient):
    """Doorbell service that handles button press events and motion detection."""

    # TODO:
    # * Add command to send video
    # * Telegram command to pause notifications
    def __init__(self, cfg, www):
        super().__init__(cfg, ['zmw_speaker_announce', 'zmw_whatsapp',
                               'zmw_telegram', 'zmw_reolink_doorbell', 'zmw_contactmon'])
        self._cfg = cfg
        # Ensure required config keys exist
        _ = self._cfg["doorbell_announce_volume"]
        _ = self._cfg["doorbell_announce_sound"]
        _ = self._cfg["doorbell_contact_sensor"]

        self._waiting_on_telegram_snap = None
        self._snap_request_timeout_secs = 5
        self._telegram_cmd_door_snap = 'door_snap'

        self._door_open_scene = DoorOpenScene(cfg, self)

    def get_service_meta(self):
        return {
            "name": "zmw_doorman",
            "mqtt_topic": None,
            "www": None,
        }

    def on_service_came_up(self, service_name):
        if service_name == "zmw_telegram":
            self.message_svc("zmw_telegram", "register_command",
                             {'cmd': self._telegram_cmd_door_snap,
                              'descr': 'Take and send a doorbell cam picture'})

    def on_service_message(self, service_name, msg_topic, msg):
        match service_name:
            case 'zmw_contactmon':
                self.on_contact_report(msg_topic, msg)
            case 'zmw_speaker_announce':
                pass
            case 'zmw_whatsapp':
                pass
            case 'zmw_telegram':
                if msg_topic.startswith("on_command/"):
                    self.on_telegram_cmd(msg_topic[len("on_command/"):], msg)
            case 'zmw_reolink_doorbell':
                match msg_topic:
                    case "on_snap_ready":
                        self.on_snap_ready(msg)
                    case "on_doorbell_button_pressed":
                        self.on_doorbell_button_pressed(msg)
                    case "on_motion_detected":
                        self.on_door_motion_detected(msg)
                    case "on_motion_cleared":
                        self.on_door_motion_cleared()
                    case "on_motion_timeout":
                        self.on_door_motion_timeout()
                    case _:
                        pass
            case _:
                log.error("Received unexpected message from service %s/%s: %s", service_name, msg_topic, msg)

    def on_contact_report(self, msg_topic, msg):
        if self._cfg["doorbell_contact_sensor"] in msg_topic:
            if msg["entering_non_normal"] == True:
                self._door_open_scene.maybe_start()

    def on_telegram_cmd(self, cmd, _msg):
        """Handle Telegram commands."""
        if cmd == self._telegram_cmd_door_snap:
            log.info("User requested doorbell snap over Telegram, requesting snap from camera")
            if self._waiting_on_telegram_snap is not None:
                log.warning(
                    "A snap request is in progress. Requesting new snap. "
                    "First snap to arrive will be sent, others will be ignored."
                )
            self._waiting_on_telegram_snap = time.time()
            self.message_svc("zmw_reolink_doorbell", "snap", {})

    def on_snap_ready(self, msg):
        """Handle camera snap ready event."""
        if self._waiting_on_telegram_snap is None:
            log.debug("Received snap_ready command but this service didn't request it, will ignore")
            return

        snap_rq_t = time.time() - self._waiting_on_telegram_snap
        if snap_rq_t >= self._snap_request_timeout_secs:
            log.warning(
                "Snap was requested %d seconds ago, ignoring (max timeout %d)",
                snap_rq_t, self._snap_request_timeout_secs
            )
            self._waiting_on_telegram_snap = None
            return

        if 'snap_path' not in msg:
            log.error("Bad message format for snap_ready, missing path. Message: %s", msg)
            return

        log.info("Received camera snap, sending over Telegram")
        self.message_svc("zmw_telegram", "send_photo", {'path': msg['snap_path']})
        self._waiting_on_telegram_snap = None

    def on_doorbell_button_pressed(self, msg):
        """Handle doorbell button press event."""
        log.info("Doorbell reports button pressed, announce over speakers")
        self.message_svc("zmw_speaker_announce", "play_asset", {
                            'vol': self._cfg.get("doorbell_announce_volume", "default"),
                            'local_path': self._cfg["doorbell_announce_sound"]})

        if not 'snap_path' in msg:
            log.warning("Doorbell button pressed but no snap available")
        else:
            log.info("Send visitor snap from doorbell camera")
            self.message_svc("zmw_whatsapp", "send_photo",
                             {'path': msg['snap_path'], 'msg': "RING!"})
            self.message_svc("zmw_telegram", "send_photo",
                             {'path': msg['snap_path'], 'msg': "RING!"})

    def on_door_motion_detected(self, msg):
        """Handle door motion detection event."""
        log.info("Door reports motion! Sending snap over WA")
        self.message_svc("zmw_whatsapp", "send_photo",
                         {'path': msg['path_to_img'], 'msg': "Motion detected"})
        self._door_open_scene.pet_timer()

    def on_door_motion_cleared(self):
        """Handle door motion cleared event."""
        log.info("Door reports motion event cleared")

    def on_door_motion_timeout(self):
        """Handle door motion timeout event."""
        log.warning("Motion event timedout, no vacancy reported")

service_runner_with_www(ZmwDoorman)
