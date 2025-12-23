import os
import signal
import pathlib
import threading
import time

from sonos_helpers import *
import json
import soco
from flask import request
from flask_sock import Sock
from simple_websocket import ConnectionClosed

from zzmw_lib.service_runner import service_runner
from zzmw_lib.zmw_mqtt_service import ZmwMqttService
from zzmw_lib.logs import build_logger

log = build_logger("ZmwSonosCtrl")

class ZmwSonosCtrl(ZmwMqttService):
    """Service to manage Sonos speaker groups and audio source selection."""

    def __init__(self, cfg, www, sched):
        super().__init__(cfg, svc_topic="zmw_sonos_ctrl", scheduler=sched, svc_deps=['ZmwSpotify'])
        self._cfg = cfg

        # Set up www directory and endpoints
        www_path = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        self._public_url_base = www.register_www_dir(www_path)

        www.serve_url('/get_sonos_play_uris', get_all_sonos_playing_uris)
        www.serve_url('/ls_speakers', lambda: list(ls_speakers().keys()))
        www.serve_url('/world_state', get_all_sonos_state)
        www.serve_url('/stop_all_playback', self._stop_all, methods=['PUT'])
        www.serve_url('/get_spotify_uri', self._get_spotify_uri)
        www.serve_url('/volume', self._set_volume, methods=['PUT'])

        # Initialize WebSocket support
        self._sock = Sock(www)
        self._sock.route('/spotify_hijack')(self._ws_spotify_hijack)

        # Cache for Spotify state
        self._spotify_context_uri = None
        self._spotify_ready = threading.Event()

    def _ws_spotify_hijack(self, ws):
        # TODO: Bail out if request is in flight

        try:
            #speakers_cfg = {"Baticocina": {"vol": 14}, "BatiDiscos": {"vol": 50}, "BatiPatio": {"vol": 15}}
            speakers_cfg = json.loads(ws.receive())
        except ConnectionClosed:
            log.info("WebSocket closed before receiving data")
            return
        except json.JSONDecodeError as ex:
            ws.send(f"Error: Invalid request - {ex}")
            return

        log.info("User requests to hijack Spotify to %s", speakers_cfg)
        spotify_uri = self._get_spotify_uri(ws)['spotify_uri']
        sonos_hijack_spotify(speakers_cfg, spotify_uri, "sid=9&flags=8232&sn=6", ws.send)

    def _get_spotify_uri(self, ws=None):
        if ws is not None:
            ws_log = ws.send
        else:
            ws_log = lambda msg: log.info(msg)
        ws_log("Requesting Spotify state...")
        self._spotify_ready.clear()
        self.message_svc("ZmwSpotify", "publish_state", {})
        if not self._spotify_ready.wait(timeout=5):
            ws_log("Error! Timeout waiting for Spotify state.")
            return {'spotify_uri': None}
        return {'spotify_uri': self._spotify_context_uri}

    def _stop_all(self):
        log.info("Stop-all request: will stop Spotify and reset Sonos states")
        self.message_svc("ZmwSpotify", "publish_state", {})
        for _, dev in ls_speakers().items():
            # TODO: Send all these in parallel
            sonos_reset_state(dev, lambda msg: log.info(msg))
            log.info("Stopped media on %s", dev.player_name)
        return {}

    def _set_volume(self):
        vol_cfg = request.get_json()
        devs = ls_speakers()
        for spk_name, volume in vol_cfg.items():
            if spk_name in devs:
                devs[spk_name].volume = volume
                log.info("Set %s volume to %s", spk_name, volume)
            else:
                log.warning("Speaker %s not found", spk_name)
        return {}

    def on_service_received_message(self, subtopic, msg):
        log.info("IGNORE %s: %s", subtopic, msg)

    def on_dep_published_message(self, svc_name, subtopic, msg):
        """Handle messages from dependent services."""
        if svc_name == "ZmwSpotify" and subtopic == "state":
            if msg is None:
                log.error("Bad message form ZmwSpotify")
                return
            if not msg.get("media_info") or not msg["media_info"].get("context"):
                log.info("Spotify has no context: %s", msg)
                log.info("Did you select a single song, or an album/playlist? Spotify doesn't have context for single songs.")
                return
            log.info("Received Spotify state")
            self._spotify_context_uri = msg["media_info"]["context"].get("uri")
            if self._spotify_context_uri:
                log.info("Spotify published playlist URI: %s", self._spotify_context_uri)
            else:
                log.warning("Spotify not playing media, or doesn't expose media URI.")
                log.debug("Received media_info: %s", msg.get("media_info"))
            self._spotify_ready.set()



## XXX    def _switch_to_line_in(self, coordinator, line_in_source=None):
## XXX        """Switch the speaker group to line-in source."""
## XXX        if coordinator is None:
## XXX            log.error("No coordinator to switch to line-in")
## XXX            return False
## XXX        try:
## XXX            if line_in_source:
## XXX                # Play line-in from a specific speaker (e.g., Sonos Port)
## XXX                coordinator.switch_to_line_in(source=line_in_source)
## XXX            else:
## XXX                coordinator.switch_to_line_in()
## XXX            log.info("Switched %s to line-in", coordinator.player_name)
## XXX            return True
## XXX        except soco.exceptions.SoCoException as ex:
## XXX            log.error("Failed to switch to line-in: %s", ex)
## XXX            return False

service_runner(ZmwSonosCtrl)
