"""Doorbell event handler and notification service."""
import time
import threading

from geo_helpers import is_sun_out

from zzmw_common.mqtt_proxy import MqttServiceClient
from zzmw_common.service_runner import service_runner, build_logger

log = build_logger("ZmwDoorman")

class ZmwDoorman(MqttServiceClient):
    """Doorbell service that handles button press events and motion detection."""

    # TODO:
    # * Add command to send video
    # * Telegram command to pause notifications
    def __init__(self, cfg):
        super().__init__(cfg, ['zmw_speaker_announce', 'zmw_whatsapp',
                               'zmw_telegram', 'zmw_reolink_doorbell', 'zmw_contactmon'])
        self._cfg = cfg
        # Ensure required config keys exist
        _ = self._cfg["doorbell_announce_volume"]
        _ = self._cfg["doorbell_announce_sound"]
        _ = self._cfg["doorbell_contact_sensor"]
        is_sun_out(cfg["latlon"][0], cfg["latlon"][1])

        self._waiting_on_telegram_snap = None
        self._snap_request_timeout_secs = 5
        self._telegram_cmd_door_snap = 'door_snap'
        self._door_open_scene_timer = None
        self._door_open_scene_timeout_secs = 30

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
                self._maybe_start_door_open_scene()

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
        self._pet_door_open_scene_timer()

    def on_door_motion_cleared(self):
        """Handle door motion cleared event."""
        log.info("Door reports motion event cleared")

    def on_door_motion_timeout(self):
        """Handle door motion timeout event."""
        log.warning("Motion event timedout, no vacancy reported")

    def _pet_door_open_scene_timer(self):
        """ Something happened that should extend the door-open scene """
        if self._door_open_scene_timer is None:
            # Trying to reset timer, but no timer is active
            return
        self._door_open_scene_timer.cancel()
        log.info("DOOR OPEN SCENE TIMEOUT HAS BEEN EXTENDED...")
        self._door_open_scene_timer = threading.Timer(
            self._door_open_scene_timeout_secs,
            self._on_door_open_scene_timeout
        )
        self._door_open_scene_timer.start()

    def _maybe_start_door_open_scene(self):
        """ Door has opened, check if we need to launch a door-open scene or not """
        # [re]schedule timeout
        log.info("STARTING DOOR OPEN SCENE...")
        self._pet_door_open_scene_timer()
        # TODO schedule scene

    def _on_door_open_scene_timeout(self):
        """ Called when the door-open scene timer expires """
        self._door_open_scene_timer = None
        log.info("DOOR OPEN SCENE TIMEOUT HAS EXPIRED...")
        # TODO shutdown scene


service_runner(ZmwDoorman)
