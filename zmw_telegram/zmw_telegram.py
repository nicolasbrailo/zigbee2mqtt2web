"""MQTT to Telegram bridge service."""
import json
import pathlib
import os

from zzmw_lib.zmw_mqtt_service import ZmwMqttService
from zzmw_lib.logs import build_logger
from zzmw_lib.service_runner import service_runner_with_www

from pytelegrambot import TelegramLongpollBot

log = build_logger("ZmwTelegram")

class TelBot(TelegramLongpollBot):
    """Telegram bot wrapper that handles messages and commands."""

    def __init__(self, cfg):
        cmds = [
            ('ping', 'Usage: /ping', self._ping),
        ]
        super().__init__(
            cfg['tok'],
            accepted_chat_ids=cfg['accepted_chat_ids'],
            short_poll_interval_secs=cfg['short_poll_interval_secs'],
            long_poll_interval_secs=cfg['long_poll_interval_secs'],
            cmds=cmds,
            bot_name=cfg['bot_name'],
            bot_descr=cfg['bot_name'],
            message_history_len=cfg['msg_history_len'],
            terminate_on_unauthorized_access=True,
            try_parse_msg_as_cmd=True)

    def _ping(self, _bot, msg):
        log.info('Received user ping, sending pong')
        if len(msg['cmd_args']) == 0:
            self.send_message(msg['from']['id'], "PONG")
        else:
            t = ' '.join(msg['cmd_args'])
            self.send_message(msg['from']['id'], f"Echo: {t}")

    def on_bot_received_non_cmd_message(self, msg):
        """ Called when a message not in the list of commands is received. This is benign, it just means someone
        set a message in Telegram, but it's a known recipient """
        log.warning("Telegram bot received unknown message: %s", msg)

class ZmwTelegram(ZmwMqttService):
    """MQTT to Telegram bridge service for bidirectional messaging."""

    def __init__(self, cfg, www):
        super().__init__(cfg, "zmw_telegram")
        self._bcast_chat_id = cfg['bcast_chat_id']
        self._msg = TelBot(cfg)

        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)
        www.serve_url('/messages', lambda: json.dumps(list(self._msg.get_history()), default=str))

    def on_service_received_message(self, subtopic, payload):
        if subtopic.startswith('on_command/'):
            # We're relaying a Telegram command over mqtt, ignore self-echo
            return

        match subtopic:
            case "register_command":
                if 'cmd' not in payload or 'descr' not in payload:
                    log.error("Received request to add command, but missing 'cmd' or 'descr': '%s'", payload)
                    return
                log.info("Registered new user command '%s' for mqtt-relaying: '%s'", payload['cmd'], payload['descr'])
                self._msg.add_commands([(payload['cmd'], payload['descr'], self._relay_cmd)])
            case "send_photo":
                if not 'path' in payload:
                    log.error("Received request to send image but payload has no path: '%s'", payload)
                    return
                if not os.path.isfile(payload['path']):
                    log.error("Received request to send image but path is not a file: '%s'", payload)
                    return
                log.info("Sending photo to bcast chat, path %s", payload['path'])
                self._msg.send_photo(self._bcast_chat_id, payload['path'], payload.get('msg', None))
            case "send_text":
                if not 'msg' in payload:
                    log.error("Received request to send message but payload has no text: '%s'", payload)
                    return
                log.info("Sending text to bcast chat, message %s", payload['msg'])
                self._msg.send_message(self._bcast_chat_id, payload['msg'])
            case _:
                log.error("Ignoring unknown message '%s'", subtopic)

    def _relay_cmd(self, _bot, msg):
        """ Relay an mqtt-registered callback from Telegram back to mqtt. The Telegram client already
        validates this command is known, so we can just relay the command itself. """
        if 'cmd' not in msg:
            log.warning("Received user message but can't find associated cmd. Ignoring. Full message:\n\t%s", msg)
            return

        log.info("Received Telegram command '%s', relaying over mqtt", msg['cmd'])
        # Commands may have a / as a prefix, strip it to ensure we only send a single slash
        if msg['cmd'][0] == '/':
            cmd = msg['cmd'][1:]
        else:
            cmd = msg['cmd']
        self.publish_own_svc_message(f"on_command/{cmd}", msg)

service_runner_with_www(ZmwTelegram)
