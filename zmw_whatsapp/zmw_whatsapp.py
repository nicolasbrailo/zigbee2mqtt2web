""" MQTT to Whatsapp bridge service. """

import json
import os
import pathlib
from datetime import datetime
from collections import deque

from zzmw_lib.logs import build_logger
from zzmw_lib.service_runner import service_runner_with_www
from zzmw_lib.zmw_mqtt_service import ZmwMqttService

from whatsapp import WhatsApp

log = build_logger("ZmwWhatsapp")

class ZmwWhatsapp(ZmwMqttService):
    """ Expose Whatsapp methods over MQTT """
    def __init__(self, cfg, www):
        super().__init__(cfg, "zmw_whatsapp")
        self._wa = WhatsApp(cfg, test_mode=False)
        self._message_history = deque(maxlen=cfg['msg_history_len'])

        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)
        www.serve_url('/messages', lambda: json.dumps(list(self._message_history), default=str))

    def _track_message(self, direction, msg_type, **details):
        """Track message events for history"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'direction': direction,  # 'sent'
            'type': msg_type,
        }
        event.update(details)
        self._message_history.append(event)

    def on_service_received_message(self, subtopic, payload):
        """ MQTT callback """
        match subtopic:
            case "send_photo":
                if 'path' not in payload:
                    log.error("Received request to send image but payload has no path: '%s'", payload)
                    return
                if not os.path.isfile(payload['path']):
                    log.error("Received request to send image but path is not a file: '%s'", payload['path'])
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
                log.error("Ignoring unknown message '%s'", subtopic)

service_runner_with_www(ZmwWhatsapp)
