""" Sonos helpers for ZMW """

from pathlib import Path
import json
import os
import subprocess
import time

from json import JSONDecodeError
from flask import send_from_directory, url_for
from flask import request as FlaskRq

import soco
from soco import discover
from soco.exceptions import SoCoUPnPException
from soco.exceptions import SoCoSlaveException

from ..phony import PhonyZMWThing
from .helpers import sonos_announce
from .tts import get_local_path_tts

import logging
logger = logging.getLogger('ZMWSonos')

# sudo apt-get install python3-lxml libxslt1-dev
# python3 -m pipenv install soco --skip-lock

_DEFAULT_ANNOUNCEMENT_VOLUME = 50
_DEFAULT_ANNOUNCEMENT_TIMEOUT_SECS = 10


def _config_logger(use_debug_log):
    if not use_debug_log:
        logging.getLogger('soco.*').setLevel(logging.INFO)
        logging.getLogger('soco.core').setLevel(logging.INFO)
        logging.getLogger('soco.services').setLevel(logging.INFO)
        logging.getLogger('soco.discovery').setLevel(logging.INFO)
        logging.getLogger('soco.zonegroupstate').setLevel(logging.INFO)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)


def get_sonos_by_name():
    """ Returns a map of all LAN Sonos players """
    all_sonos = {}
    for player_obj in discover():
        all_sonos[player_obj.player_name] = player_obj
    return all_sonos


def is_this_sonos_playing_something(device):
    """ True if this Sonos device is playing any kind of media (eg TV, stream, line in...) """
    play_state = device.get_current_transport_info()['current_transport_state']
    return device.is_playing_tv \
        or device.is_playing_line_in \
        or device.is_playing_radio \
        or 'playing' in play_state.lower()


class Sonos(PhonyZMWThing):
    """ Wraps all Sonos in the LAN as a ZMW thing """

    def __init__(self, cfg, webserver):
        # Ensure we have all needed cfgs
        cfg['zmw_thing_name']  # pylint: disable=pointless-statement
        super().__init__(
            name=cfg['zmw_thing_name'],
            description="Wrapper over Sonos for ZMW",
            thing_type="media_player",
        )

        # If one API key is defined, all of them should be
        self._api_cfg = None
        if 'api_key' in cfg or 'api_key_name' in cfg or 'key_app_id' in cfg:
            self._api_cfg = {
                'api_key': cfg['api_key'],
                'api_key_name': cfg['api_key_name'],
                'key_app_id': cfg['key_app_id'],
            }

        _config_logger(cfg['debug_log'])
        self._cfg = cfg
        self._www = webserver
        self._add_base_zmw_actions()
        self._add_tts_actions(webserver)
        self._add_user_audio_actions(webserver)

    def _add_base_zmw_actions(self):
        """ Add ZMW general actions, like stop or announce """
        self._add_action('stop',
                         'Stop all Sonos in the LAN from playing anything',
                         setter=self._stop)
        self._add_action('list_known_sonos',
                         'List the Sonos devices in the LAN',
                         getter=get_sonos_by_name)
        self._add_action(
            'media_player_state',
            'get_json_state() is disabled for this object, as it needs remote access '
            'and may be very slow. Use this action instead to retrieve the full state',
            getter=self.get_json_state)
        self._add_action(
            'play_announcement',
            'Play a (short) clip on all LAN Sonos. Request should contain either only'
            'a URL, or a message like {"uri": $, "volume": $, "timeout_secs": [$, $]}',
            setter=self._play_announcement)

    def _add_user_audio_actions(self, webserver):
        """ Add user recording playback actions + webserver routes """
        if 'enable_user_audio_annoucements' not in self._cfg or \
                self._cfg['enable_user_audio_annoucements'] is not True:
            logger.info(
                'Skip user audio announcmenets, disabled in configuration')
            return

        if not webserver.has_http_mode():
            raise RuntimeError(
                'Sonos user audio announce is enabled, but HTTP mode is not enabled. '
                'HTTP required for asset delivery')

        # Check if we have all required configs
        self._cfg['user_audio_cache_path']  # pylint: disable=pointless-statement
        self._cfg['url_base_asset_webserver']  # pylint: disable=pointless-statement

        self._add_action(
            'user_audio_announce',
            'Upload a user audio clip and play it as announcement on all known Sonos',
            setter=self._user_audio_announce_start)
        self._cfg['webpath_user_audio_asset'] = f'/{self._cfg["zmw_thing_name"]}/user_audio/<fname>'
        webserver.add_url_rule(
            f'/{self._cfg["zmw_thing_name"]}/say',
            self._announce_test_ui)
        webserver.add_url_rule(
            f'/{self._cfg["zmw_thing_name"]}/announce_user_recording',
            self._announce_user_recording, methods=['POST'])
        webserver.add_asset_url_rule(
            self._cfg["webpath_user_audio_asset"],
            self._serve_user_audio_asset)

        logger.info(
            '%s supports user audio announcmenets',
            self._cfg["zmw_thing_name"])

    def _add_tts_actions(self, webserver):
        """ Add TTS playback actions + webserver routes """
        if 'enable_tts_annoucements' not in self._cfg or \
                self._cfg['enable_tts_annoucements'] is not True:
            logger.info('Skip TTS init, disabled in configuration')
            return

        if not webserver.has_http_mode():
            raise RuntimeError('Sonos TTS is enabled, but HTTP mode is not. '
                               'HTTP required for asset delivery')

        # Verify required config exists
        self._cfg['tts_cache_path']  # pylint: disable=pointless-statement
        self._cfg['url_base_asset_webserver']  # pylint: disable=pointless-statement

        self._cfg['webpath_tts_asset'] = f'/{self._cfg["zmw_thing_name"]}/tts_asset/<fname>'
        self._add_action(
            'tts_announce',
            'Play a TTS clip on all LAN Sonos. Request should contain a message like '
            '{"phrase": $, "lang": $, "volume": $, "timeout_secs": $}',
            setter=self._tts_announce)
        webserver.add_url_rule(
            f'/{self._cfg["zmw_thing_name"]}/tts_announce/<lang>/<phrase>',
            self.tts_announce)
        webserver.add_asset_url_rule(
            self._cfg["webpath_tts_asset"],
            self._serve_tts_asset)

        logger.info(
            '%s supports TTS announcmenets',
            self._cfg["zmw_thing_name"])

    def _announce_test_ui(self):
        """ Creates a trivial form to test announcmenets """
        return f"""
            <script>
            function startAnnouncement() {{
                const phrase = document.getElementById('phrase').value;
                const lang = document.getElementById('lang').value;
                const url = `/{self._cfg["zmw_thing_name"]}/tts_announce/${{lang}}/${{phrase}}`;
                window.location.href = url;
            }}
            </script>


            <button onClick="javascript:startAnnouncement()">Say</button>
            <input type="text" id="phrase"/>
            in
            <input type="text" id="lang" value="en">
        """

    def _stop(self, _val):
        all_devs = get_sonos_by_name()
        for name, device in all_devs.items():
            logger.info('Stopping Sonos %s', name)
            try:
                device.pause()
            except SoCoSlaveException:
                # This player was part of a group, we can't address it
                # individually
                pass
            except SoCoUPnPException as exc:
                if exc.error_code == "701":
                    # This player wasn't playing anything, skip it
                    pass
                else:
                    logger.warning(
                        'Failed to stop Sonos %s: %s',
                        name,
                        exc,
                        exc_info=False)

    def stop(self):
        """ Stops all players in the LAN """
        # Set always comes with a value from ZMW
        return self._stop(0)

    def _play_announcement(self, uri_or_msg):
        uri = None
        volume = _DEFAULT_ANNOUNCEMENT_VOLUME
        timeout_secs = _DEFAULT_ANNOUNCEMENT_TIMEOUT_SECS
        force = []

        # Try to decode input as JSON. If it can't be parsed, assume the message is
        # just a URI
        try:
            msg = json.loads(uri_or_msg)
            uri = msg['uri']
            if 'volume' in msg:
                volume = msg['volume']
            if 'timeout_secs' in msg:
                timeout_secs = msg['timeout_secs']
            if 'force' in msg:
                force = msg['force']
        except (JSONDecodeError, TypeError, KeyError):
            uri = uri_or_msg

        if uri is None or len(uri) == 0:
            logger.warning(
                'Received request to Sonos-announce invalid uri %s', uri)
            return f"Can't play {uri}", 406

        self.play_announcement(uri, volume, timeout_secs, force)
        return "OK", 200

    def play_announcement(
            self,
            uri,
            announcement_volume=50,
            timeout_secs=10,
            force=False):
        """ Attempts to play a short clip over all known Sonos devices. Will skip devices
        playing some media, unless their name is specified in the force field. The
        announcement will be played at announcement_volume, but the volume of each
        device will be restored after the announcement finishes. This call blocks until
        all devices have finished playing (and their volume restored) or until the timeout
        is reached. """
        sonos_announce(
            uri,
            announcement_volume,
            timeout_secs=timeout_secs,
            force_play=force,
            ws_api_cfg=self._api_cfg)

    def _tts_announce(self, msg):
        volume = _DEFAULT_ANNOUNCEMENT_VOLUME
        timeout_secs = _DEFAULT_ANNOUNCEMENT_TIMEOUT_SECS
        force = False
        lang = 'en'

        try:
            msg = json.loads(msg)
        except (JSONDecodeError, TypeError, KeyError) as ex:
            raise ValueError(f"Can't parse TTS request {msg}") from ex

        if 'phrase' not in msg:
            raise ValueError(f"Missing 'phrase' in TTS request {msg}")

        if 'volume' in msg:
            volume = msg['volume']
        if 'timeout_secs' in msg:
            timeout_secs = msg['timeout_secs']
        if 'force' in msg:
            force = msg['force']
        if 'lang' in msg:
            lang = msg['lang']

        return self.tts_announce(
            lang, msg['phrase'], volume, timeout_secs, force)

    def _user_audio_announce_start(self):
        # TODO: Check PUT support
        raise RuntimeError('Not implemented')

    def tts_announce(self, lang, phrase,
                     announcement_volume=50,
                     timeout_secs=10,
                     force=False):
        """ Say something on all available speakers """
        # Attempt to download a TTS asset, or throw
        tts_local_file = get_local_path_tts(
            self._cfg['tts_cache_path'], phrase, lang)

        tts_asset_url = self._cfg['url_base_asset_webserver'] + \
            self._www.url_for(self._cfg['webpath_tts_asset'], tts_local_file)
        self.play_announcement(
            tts_asset_url,
            announcement_volume,
            timeout_secs,
            force)
        return tts_asset_url

    def _announce_user_recording(self):
        request_not_valid = FlaskRq.files is None or \
            len(FlaskRq.files) != 1 or \
            'audio_data' not in FlaskRq.files
        if request_not_valid:
            logger.warning(
                "Received request to store audio asset, but can't understand it")
            return "Can't find file in audio asset store request", 406

        # Try to create cache path, throw on fail
        Path(
            self._cfg['user_audio_cache_path']).mkdir(
            parents=True,
            exist_ok=True)

        # Where to store raw user upload
        user_audio_fname = f'user_audio_{time.time()}.probablyogg'
        user_audio_path = Path(
            os.path.join(
                self._cfg['user_audio_cache_path'],
                user_audio_fname))

        # Where to store sanitized user upload
        user_audio_cleaned_fname = f'user_audio_{time.time()}.mp3'
        user_audio_cleaned_path = Path(
            os.path.join(
                self._cfg['user_audio_cache_path'],
                user_audio_cleaned_fname))

        if user_audio_path.is_file() or user_audio_cleaned_path.is_file():
            # A clash shouldn't happen because time.time() has enough precision that even
            # concurrent requests should end up with different filename; if this fails, just
            # ask the user to retry.
            return "Error saving user audio, please try again", 429

        FlaskRq.files['audio_data'].save(user_audio_path)
        if not user_audio_path.is_file():
            return "Error saving user audio, please try again", 500
        logger.info('Saved raw user audio to %s', user_audio_path)

        # Give user upload a pass through ffmpeg, to ensure it's on a format
        # that we support
        cmd = f"ffmpeg -i {user_audio_path} -acodec mp3 {user_audio_cleaned_path}"
        try:
            subprocess.run(
                cmd.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=10)
        except subprocess.CalledProcessError:
            logger.warning(
                "Can't validate user uploaded audio file %s", user_audio_path,
                exc_info=True)
            return "Can't validate uploaded file", 406

        if not user_audio_cleaned_path.is_file():
            return "Error saving validated user audio, please try again", 429

        try:
            os.remove(user_audio_path)
        except (FileNotFoundError, OSError):
            logger.warning(
                "Can't cleanup temporary user uploaded audio file %s",
                user_audio_path,
                exc_info=True)

        user_audio_url = self._cfg['url_base_asset_webserver'] + url_for(
            self._cfg['webpath_user_audio_asset'], fname=user_audio_cleaned_fname)
        self.play_announcement(
            user_audio_url,
            announcement_volume=40,
            timeout_secs=10)
        logger.info(
            'Requested user audio announcement, asset url %s',
            user_audio_url)

        return "User audio sent for announcement", 200

    def _serve_tts_asset(self, fname):
        """ Serve a file asset created from tts_announce """
        logger.debug('Serve TTS Asset %s', fname)
        return send_from_directory(self._cfg['tts_cache_path'], fname)

    def _serve_user_audio_asset(self, fname):
        """ Serve a file asset created from user upload """
        logger.info('Serve user audio Asset %s', fname)
        return send_from_directory(self._cfg['user_audio_cache_path'], fname)
