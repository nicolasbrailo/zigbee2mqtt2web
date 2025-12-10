""" MQTT to Whatsapp bridge service. """

import json
import os
import pathlib
from datetime import datetime
from collections import deque

from zzmw_lib.mqtt_proxy import MqttProxy
from zzmw_lib.service_runner import service_runner_with_www, build_logger
from whatsapp import WhatsApp

log = build_logger("ZmwWhatsapp")

class ZmwWA(MqttProxy):
    """ Expose Whatsapp methods over MQTT """
    def __init__(self, cfg, www):
        self._wa = WhatsApp(cfg, test_mode=False)
        self._topic_base = "zmw_whatsapp"
        self._message_history = deque(maxlen=cfg['msg_history_len'])

        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)
        www.serve_url('/messages', self.get_messages)

        MqttProxy.__init__(self, cfg, self._topic_base)

    def _track_message(self, direction, msg_type, **details):
        """Track message events for history"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'direction': direction,  # 'sent'
            'type': msg_type,
        }
        event.update(details)
        self._message_history.append(event)

    def get_messages(self):
        """Flask endpoint to serve message history"""
        return json.dumps(list(self._message_history), default=str)

    def get_service_meta(self):
        """ Metadata on this service """
        return {
            "name": self._topic_base,
            "mqtt_topic": self._topic_base,
            "methods": ["send_photo", "send_text"],
            "announces": [],
            "www": self._public_url_base,
        }

    def on_mqtt_json_msg(self, topic, payload):
        """ MQTT callback """
        match topic:
            case "send_photo":
                if 'path' not in payload:
                    log.error(
                        "Received request to send image but payload has no path: '%s'",
                        payload)
                    return
                if not os.path.isfile(payload['path']):
                    log.error(
                        "Received request to send image but path is not a file: '%s'",
                        payload['path'])
                    return
                self._wa.send_photo(payload['path'], payload['msg'])
                self._track_message('sent', 'photo', path=payload['path'], caption=payload.get('msg'))
            case "send_text":
                if 'msg' not in payload:
                    log.error("Received request to send text but payload has no msg: '%s'", payload)
                    return
                log.warning("User requested Whatsapp text, but this isn't implemented: '%s'", payload)
                self._track_message('sent', 'text', text=payload['msg'], status='not_implemented')
            case _:
                log.error("Ignoring unknown message '%s'", topic)


service_runner_with_www(ZmwWA)
