"""MQTT speaker announcement service using Sonos."""
import json
import shutil
import os
import pathlib
from collections import deque
from datetime import datetime

from flask import abort, request

from zzmw_lib.mqtt_proxy import MqttProxy
from zzmw_lib.service_runner import service_runner_with_www, build_logger

from sonos_helpers import get_sonos_by_name, config_soco_logger
from sonos_announce import sonos_announce
from tts import get_local_path_tts

log = build_logger("ZmwSpeakerAnnounce")
config_soco_logger(False)

class ZmwSpeakerAnnounce(MqttProxy):
    """MQTT proxy for Sonos speaker announcements."""
    def __init__(self, cfg, www):
        self._cfg = cfg
        self._topic_base = "zmw_speaker_announce"
        self._public_tts_base = f"{www.public_url_base}/tts"
        self._public_www_base = www.public_url_base
        self._tts_assets_cache_path = cfg['tts_assets_cache_path']
        self._announce_vol = cfg['announce_volume']
        self._announcement_history = deque(maxlen=10)
        if not os.path.isdir(self._tts_assets_cache_path):
            raise FileNotFoundError(f"Invalid cache path '{self._tts_assets_cache_path}'")

        MqttProxy.__init__(self, cfg, self._topic_base)
        www.register_www_dir(cfg['tts_assets_cache_path'], '/tts/')
        www.register_www_dir(os.path.join(pathlib.Path(__file__).parent.resolve(), 'www'), '/')
        www.serve_url('/announce_tts', self._www_announce_tts)
        www.serve_url('/ls_speakers', self._www_known_speakers)
        www.serve_url('/announcement_history', self._www_announcement_history)

    def get_service_meta(self):
        return {
            "name": self._topic_base,
            "mqtt_topic": self._topic_base,
            "methods": ["ls", "tts", "save_asset", "play_asset"],
            "announces": ["ls_reply", "tts_reply", "save_asset_reply"],
            "www": self._public_www_base,
        }

    def _www_known_speakers(self):
        return json.dumps(sorted(list(get_sonos_by_name())))

    def _www_announcement_history(self):
        return json.dumps(list(self._announcement_history))

    def _record_announcement(self, phrase, lang, volume, uri):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'phrase': phrase,
            'lang': lang,
            'volume': volume,
            'uri': uri
        }
        self._announcement_history.append(entry)

    def _www_announce_tts(self):
        """Web endpoint for TTS announcements."""
        lang = request.args.get('lang', self._cfg['tts_default_lang'])
        txt = request.args.get('phrase')
        if txt is None:
            return abort(400, "Message has no phrase")
        try:
            vol = int(request.args.get('vol', self._announce_vol))
        except ValueError:
            log.warning("Ignore non-number volume (%s) requested by user", request.args.get('vol'))
            vol = self._announce_vol

        local_path = get_local_path_tts(self._tts_assets_cache_path, txt, lang)
        remote_path = f"{self._public_tts_base}/{local_path}"
        self._record_announcement(txt, lang, vol, remote_path)
        sonos_announce(remote_path, volume=vol, ws_api_cfg=self._cfg)
        return "OK"

    def on_mqtt_json_msg(self, topic, payload):
        match topic:
            case "ls":
                self.broadcast(f"{self._topic_base}/ls_reply", list(get_sonos_by_name()))
            case "tts_reply":
                pass # Ignore self-reply
            case "tts":
                return self._tts_and_play(payload)
            case "save_asset_reply":
                pass # Ignore self-reply
            case "save_asset":
                self._save_asset_to_www(payload.get('local_path', None))
            case "play_asset":
                self._play_asset(payload)
            case _:
                log.error("Unknown message %s payload %s", topic, payload)

    def _tts_and_play(self, payload):
        if 'msg' not in payload:
            log.error("Received request for tts, but payload has no msg")
            return
        lang = payload.get('lang', self._cfg['tts_default_lang'])
        local_path = get_local_path_tts(self._tts_assets_cache_path, payload['msg'], lang)
        remote_path = f"{self._public_tts_base}/{local_path}"
        msg = {'local_path': local_path, 'uri': remote_path}
        self.broadcast(f"{self._topic_base}/tts_reply", msg)
        vol = self._get_payload_vol(payload)
        self._record_announcement(payload['msg'], lang, vol, remote_path)
        sonos_announce(remote_path, volume=vol, ws_api_cfg=self._cfg)

    def _save_asset_to_www(self, local_path):
        try:
            local_path = str(local_path)
            if not os.path.isfile(local_path):
                log.warning('Bad path to asset: "%s" is not a file', local_path)
                self.broadcast(f"{self._topic_base}/save_asset_reply",
                               {'status': 'error', 'cause': 'Bad path to asset "{local_path}"'})
                return None
            # If file existed, overwrite
            local_asset_path = shutil.copy2(local_path, self._tts_assets_cache_path)
        except OSError as e:
            log.error("Saving asset failed", exc_info=True)
            self.broadcast(f"{self._topic_base}/save_asset_reply", {'status': 'error', 'cause': str(e)})
            return None

        fname = os.path.basename(local_asset_path)
        asset_uri = f"{self._public_tts_base}/{fname}"
        log.info("Saved asset '%s' to '%s', available at uri '%s'", local_path, local_asset_path, asset_uri)
        self.broadcast(f"{self._topic_base}/save_asset_reply", {
            'status': 'ok',
            'asset': fname,
            'uri': asset_uri})
        return asset_uri

    def _play_asset(self, payload):
        srcs = 1 if 'name' in payload else 0
        srcs += 1 if 'local_path' in payload else 0
        srcs += 1 if 'public_www' in payload else 0
        if srcs != 1:
            log.error(
                "Request to play an asset must specifiy one and only one source "
                "out of name, local_path or public_www. Message: '%s'", str(payload))
            return

        asset_uri = None
        if 'local_path' in payload:
            asset_uri = self._save_asset_to_www(payload['local_path'])
        elif 'public_www' in payload:
            asset_uri = payload['public_www']
        else:
            asset_name = payload['name']
            asset_uri = f"{self._public_tts_base}/{asset_name}"
            local_path = os.path.join(self._tts_assets_cache_path, asset_name)
            if not os.path.isfile(local_path):
                log.error("Request to play an asset, but asset doesn't exist. Message: %s", str(payload))
                return

        if asset_uri is None:
            log.error("Failed to announce, MQTT payload: %s", str(payload))
            return

        vol = self._get_payload_vol(payload)
        log.info("Announcing asset %s with volume %d", asset_uri, vol)
        self._record_announcement('<asset playback>', '', vol, asset_uri)
        sonos_announce(asset_uri, volume=vol, ws_api_cfg=self._cfg)


    def _get_payload_vol(self, payload):
        vol = payload.get('vol', self._announce_vol)
        if vol == 'default':
            return self._announce_vol

        try:
            vol = int(vol)
        except (ValueError, TypeError):
            log.warning("Requested invalid volume '%s', using default announcement volume", vol)
            return self._announce_vol

        if vol < 0 or vol > 100:
            log.warning("Requested invalid volume '%d', using default announcement volume '%d'",
                        vol, self._announce_vol)
            return self._announce_vol
        return vol


service_runner_with_www(ZmwSpeakerAnnounce)
