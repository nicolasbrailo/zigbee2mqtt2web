"""Doorbell event handler and notification service."""
import time
import os
import pathlib

from zzmw_lib.service_runner import service_runner_with_www
from zzmw_lib.zmw_mqtt_service import ZmwMqttServiceNoCommands
from zzmw_lib.logs import build_logger

from door_open_scene import DoorOpenScene

log = build_logger("ZmwDoorman")

class ZmwDoorman(ZmwMqttServiceNoCommands):
    """Doorbell service that handles button press events and motion detection."""

    # TODO:
    # * Add command to send video
    # * Telegram command to pause notifications
    def __init__(self, cfg, www):
        super().__init__(cfg, svc_deps=['ZmwSpeakerAnnounce', 'ZmwWhatsapp', 'ZmwTelegram',
                                        'ZmwReolinkDoorbell', 'ZmwContactmon'])
        self._cfg = cfg
        # Ensure required config keys exist
        _ = self._cfg["doorbell_announce_volume"]
        _ = self._cfg["doorbell_announce_sound"]
        _ = self._cfg["doorbell_contact_sensor"]

        self._waiting_on_telegram_snap = None
        self._snap_request_timeout_secs = 5
        self._telegram_cmd_door_snap = 'door_snap'

        self._door_open_scene = DoorOpenScene(cfg, self)

        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)


    def on_service_came_up(self, service_name):
        if service_name == "ZmwTelegram":
            self.message_svc("ZmwTelegram", "register_command",
                             {'cmd': self._telegram_cmd_door_snap,
                              'descr': 'Take and send a doorbell cam picture'})

    def on_dep_published_message(self, service_name, msg_topic, msg):
        log.debug("%s.%s: %s", service_name, msg_topic, msg)
        match service_name:
            case 'ZmwContactmon':
                self.on_contact_report(msg_topic, msg)
            case 'ZmwSpeakerAnnounce':
                pass
            case 'ZmwWhatsapp':
                pass
            case 'ZmwTelegram':
                if msg_topic.startswith("on_command/"):
                    self.on_telegram_cmd(msg_topic[len("on_command/"):], msg)
            case 'ZmwReolinkDoorbell':
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
            self.message_svc("ZmwReolinkDoorbell", "snap", {})

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
        self.message_svc("ZmwTelegram", "send_photo", {'path': msg['snap_path']})
        self._waiting_on_telegram_snap = None

    def on_doorbell_button_pressed(self, msg):
        """Handle doorbell button press event."""
        url = self._public_url_base + self._cfg["doorbell_announce_sound"]
        log.info("Doorbell reports button pressed, announce '%s' over speakers", url)
        self.message_svc("ZmwSpeakerAnnounce", "play_asset", {
                            'vol': self._cfg.get("doorbell_announce_volume", "default"),
                            'public_www': url})

        if not 'snap_path' in msg:
            log.warning("Doorbell button pressed but no snap available")
        else:
            log.info("Send visitor snap from doorbell camera")
            self.message_svc("ZmwWhatsapp", "send_photo",
                             {'path': msg['snap_path'], 'msg': "RING!"})
            self.message_svc("ZmwTelegram", "send_photo",
                             {'path': msg['snap_path'], 'msg': "RING!"})

    def on_door_motion_detected(self, msg):
        """Handle door motion detection event."""
        log.info("Door reports motion! Sending snap over WA")
        self.message_svc("ZmwWhatsapp", "send_photo",
                         {'path': msg['path_to_img'], 'msg': "Motion detected"})
        self._door_open_scene.pet_timer()

    def on_door_motion_cleared(self):
        """Handle door motion cleared event."""
        log.info("Door reports motion event cleared")

    def on_door_motion_timeout(self):
        """Handle door motion timeout event."""
        log.warning("Motion event timedout, no vacancy reported")

service_runner_with_www(ZmwDoorman)
