""" Sonos helpers for ZMW """

import time
import json
from json import JSONDecodeError

from soco import discover
from soco.exceptions import SoCoUPnPException
from soco.exceptions import SoCoSlaveException

from .phony import PhonyZMWThing

import logging
logger = logging.getLogger(__name__)

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

    def __init__(self, cfg):
        super().__init__(
            name="Sonos",
            description="Wrapper over Sonos for ZMW",
            thing_type="media_player",
        )

        _config_logger(cfg['debug_log'])

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

        return self.play_announcement(uri, volume, timeout_secs, force)

    def play_announcement(
            self,
            uri,
            announcement_volume=50,
            timeout_secs=10,
            force=None):
        """ Attempts to play a short clip over all known Sonos devices. Will skip devices
        playing some media, unless their name is specified in the force field. The
        announcement will be played at announcement_volume, but the volume of each
        device will be restored after the announcement finishes. This call blocks until
        all devices have finished playing (and their volume restored) or until the timeout
        is reached. """
        logger.info(
            'Will play announcement from %s at volume %d',
            uri,
            announcement_volume)
        vols_to_restore = {}
        all_devs = get_sonos_by_name()
        if force is None:
            force = []

        for name, device in all_devs.items():
            try:
                if is_this_sonos_playing_something(device):
                    if name in force:
                        logger.info(
                            'Sonos %s is playing something else, it will be forced-stopped', name)
                    else:
                        logger.info(
                            'Skip Sonos announcement on %s, something else is playing', name)
                        continue

                vols_to_restore[name] = device.volume
                device.volume = announcement_volume
                device.play_uri(uri, title='Baticasa Announcement')
                logger.info(
                    'Playing %s in Sonos %s, volume to restore is %d',
                    uri,
                    name,
                    all_devs[name].volume)
            except Exception:  # pylint: disable=broad-except
                logger.error(
                    'Announcement failed in Sonos %s',
                    name,
                    exc_info=True)

        for name, volume in vols_to_restore.items():
            timeout = timeout_secs
            device = all_devs[name]
            while True:
                try:
                    if not is_this_sonos_playing_something(
                            device) or timeout <= 0:
                        logger.info(
                            "Restore Sonos %s volume to %d",
                            name,
                            volume)
                        device.volume = volume
                        break
                except Exception:  # pylint: disable=broad-except
                    logger.error(
                        'Volume restore failed in Sonos %s',
                        name,
                        exc_info=True)
                    break

                timeout -= 1
                if timeout <= 0:
                    logger.info(
                        "Sonos %s is still playing and timeout expired", name)
                else:
                    logger.info("Sonos %s is still playing, waiting...", name)
                time.sleep(1)
