"""MQTT speaker announcement service using Sonos."""
import json
import shutil
import os
import pathlib
import subprocess
from collections import deque
from datetime import datetime

from flask import abort, request

from zzmw_lib.logs import build_logger
from zzmw_lib.service_runner import service_runner
from zzmw_lib.zmw_mqtt_service import ZmwMqttService

from https_server import HttpsServer
from sonos_helpers import get_sonos_by_name, config_soco_logger
from sonos_announce import sonos_announce
from tts import get_local_path_tts

log = build_logger("ZmwSpeakerAnnounce")
config_soco_logger(False)


def save_audio_as_mp3(audio_file, output_dir):
    """Save audio file as ogg, convert to mp3, return mp3 path. Returns None on error."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_filename = f"user_recording_{timestamp}"
    ogg_path = os.path.join(output_dir, f"{base_filename}.ogg")
    mp3_path = os.path.join(output_dir, f"{base_filename}.mp3")

    try:
        audio_file.save(ogg_path)
        subprocess.run(['ffmpeg', '-i', ogg_path, '-y', mp3_path], check=True, timeout=5)
    except subprocess.TimeoutExpired:
        log.error("ffmpeg conversion timed out for '%s'", ogg_path)
        return None
    except subprocess.CalledProcessError:
        log.error("ffmpeg conversion failed for '%s'", ogg_path, exc_info=True)
        return None
    except OSError as e:
        log.error("Failed to save/convert audio: %s", e)
        return None

    return mp3_path


class ZmwSpeakerAnnounce(ZmwMqttService):
    """MQTT proxy for Sonos speaker announcements."""
    def __init__(self, cfg, www, _sched):
        super().__init__(cfg, "zmw_speaker_announce", scheduler=_sched)
        self._cfg = cfg
        self._announce_vol = cfg['announce_volume']
        self._announcement_history = deque(maxlen=10)

        # Save cache path for tts and register it as a www dir, to serve assets
        self._tts_assets_cache_path = cfg['tts_assets_cache_path']
        if not os.path.isdir(self._tts_assets_cache_path):
            raise FileNotFoundError(f"Invalid cache path '{self._tts_assets_cache_path}'")

        # Create HTTPS server that proxies to the HTTP server
        # All endpoints registered on https_www will be available on both HTTP and HTTPS
        # Register TTS assets - Sonos uses HTTP (can't validate self-signed certs) so make sure HTTP works
        # User recording (mic) requires HTTPS, so make sure we can serve an HTTPS page
        self._https = HttpsServer(www, cfg)
        self._https.mirror_http_routes(['/zmw.css', '/zmw.js'])

        self._https.register_www_dir(cfg['tts_assets_cache_path'], '/tts/')
        self._public_tts_base = f"{www.public_url_base}/tts"
        log.info("Sonos will fetch TTS assets from HTTP server: %s", self._public_tts_base)

        # Register all other endpoints on both HTTP and HTTPS
        self._https.register_www_dir(os.path.join(pathlib.Path(__file__).parent.resolve(), 'www'), '/')
        self._https.serve_url('/announce_user_recording', self._announce_user_recording, methods=['PUT', 'POST'])
        self._https.serve_url('/announce_tts', self._www_announce_tts)
        self._https.serve_url('/ls_speakers', lambda: json.dumps(sorted(list(get_sonos_by_name()))))
        self._https.serve_url('/announcement_history', lambda: json.dumps(list(self._announcement_history)))
        self._https.serve_url('/svc_config', lambda: json.dumps({'https_server': self._https.server_url}))

        # Start the HTTPS server (if certs available)
        self._https.start()
        if self._https.server_url:
            log.info("HTTPS server available at: %s", self._https.server_url)


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
        vol = self._get_payload_vol(request.args)
        txt = request.args.get('phrase')
        if txt is None:
            return abort(400, "Message has no phrase")

        local_path = get_local_path_tts(self._tts_assets_cache_path, txt, lang)
        remote_path = f"{self._public_tts_base}/{local_path}"
        self._record_announcement(txt, lang, vol, remote_path)
        sonos_announce(remote_path, volume=vol, ws_api_cfg=self._cfg)
        return "OK"

    def _announce_user_recording(self):
        """Handle user-recorded audio announcement."""
        if 'audio_data' not in request.files:
            return abort(400, "No audio_data in request")

        audio_file = request.files['audio_data']
        mp3_path = save_audio_as_mp3(audio_file, self._tts_assets_cache_path)
        if mp3_path is None:
            return abort(500, "Failed to convert audio")

        filename = os.path.basename(mp3_path)
        remote_path = f"{self._public_tts_base}/{filename}"

        vol = self._get_payload_vol(request.form)
        log.info("Saved recording to '%s' -> '%s'. Will announce at vol=%s", mp3_path, remote_path, vol)
        self._record_announcement('<user recording>', '', vol, remote_path)
        sonos_announce(remote_path, volume=vol, ws_api_cfg=self._cfg)

        return "OK"

    def on_service_received_message(self, subtopic, payload):
        match subtopic:
            case "ls_reply":
                pass # Ignore self-reply
            case "ls":
                self.publish_own_svc_message("ls_reply", list(get_sonos_by_name()))
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
                log.error("Unknown message %s payload %s", subtopic, payload)

    def _tts_and_play(self, payload):
        if 'msg' not in payload:
            log.error("Received request for tts, but payload has no msg")
            return
        lang = payload.get('lang', self._cfg['tts_default_lang'])
        local_path = get_local_path_tts(self._tts_assets_cache_path, payload['msg'], lang)
        remote_path = f"{self._public_tts_base}/{local_path}"
        msg = {'local_path': local_path, 'uri': remote_path}
        self.publish_own_svc_message("tts_reply", msg)
        vol = self._get_payload_vol(payload)
        self._record_announcement(payload['msg'], lang, vol, remote_path)
        sonos_announce(remote_path, volume=vol, ws_api_cfg=self._cfg)

    def _save_asset_to_www(self, local_path):
        try:
            local_path = str(local_path)
            if not os.path.isfile(local_path):
                log.warning('Bad path to asset: "%s" is not a file', local_path)
                self.publish_own_svc_message("save_asset_reply",
                               {'status': 'error', 'cause': 'Bad path to asset "{local_path}"'})
                return None
            # If file existed, overwrite
            local_asset_path = shutil.copy2(local_path, self._tts_assets_cache_path)
        except OSError as e:
            log.error("Saving asset failed", exc_info=True)
            self.publish_own_svc_message("save_asset_reply", {'status': 'error', 'cause': str(e)})
            return None

        fname = os.path.basename(local_asset_path)
        asset_uri = f"{self._public_tts_base}/{fname}"
        log.info("Saved asset '%s' to '%s', available at uri '%s'", local_path, local_asset_path, asset_uri)
        self.publish_own_svc_message("save_asset_reply", {
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


service_runner(ZmwSpeakerAnnounce)
