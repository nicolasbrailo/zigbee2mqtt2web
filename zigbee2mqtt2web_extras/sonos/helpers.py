"""
Random Sonos helpers.

Alarm/announcement system inspired from
https://github.com/SoCo/SoCo/blob/master/examples/snapshot/multi_zone_snap.py
https://github.com/jishi/node-sonos-http-api/blob/master/lib/helpers/all-player-announcement.js
"""

import time
from soco.snapshot import Snapshot

import logging
logger = logging.getLogger('ZMWSonos')


def sonos_announce(zones, alert_uri, volume, timeout, force_play):
    """ Send an announcement to all zones """

    logger.info(
        'Preparing announcement %s volume %s timeout %s',
        alert_uri, volume, timeout)

    # prepare all zones for playing the alert
    announce_zones = []
    for zone in zones:
        trans_state = zone.get_current_transport_info()
        if trans_state["current_transport_state"] == "PLAYING" and not force_play:
            logger.info(
                'Will skip %s from announcement, currently playing media',
                zone.player_name)
            continue

        # Each Sonos group has one coordinator only these can play, pause, etc.
        if zone.is_coordinator:
            if zone.is_playing_tv:  # can't pause TV - so don't try!
                continue
            # pause music for each coordinators if playing
            trans_state = zone.get_current_transport_info()
            if trans_state["current_transport_state"] == "PLAYING":
                zone.pause()

        # For every Sonos player set volume and mute for every zone
        zone.mute = False
        zone.volume = volume

        # Save current state
        zone.snap = Snapshot(zone)
        zone.snap.snapshot()

        announce_zones.append(zone)

    # play the sound (uri) on each sonos coordinator
    logger.info('Requesting Sonos to play announcement: %s', alert_uri)
    for zone in announce_zones:
        logger.info('  ask %s to play announcement', zone.player_name)
        if zone.is_coordinator:
            try:
                zone.play_uri(uri=alert_uri, title="Sonos Alert")
            except Exception: # pylint: disable=broad-except
                logging.error(
                    'Failed to announce on %s',
                    zone.player_name,
                    exc_info=True)

    # Sleep to synchronize: make sure we're not checking for announcement finished
    # before the speaker had time to process the announce request
    time.sleep(1)

    # Wait for alert to finish (or timeout)
    announcement_finished = False
    finished_waits = 0
    while not announcement_finished:
        logger.info('Waiting for announcement to finish...')
        for zone in announce_zones:
            # transport info isn't reliable for all device types (eg Sonos amps may say they are
            # always playing when line-in is connected), so we wait until any single device says
            # that playback is fininshed: if announcement was sent to all devices, any of them
            # finishing should be an indication that the real announcement is
            # finished.
            trans_state = zone.get_current_transport_info()
            if trans_state["current_transport_state"] != "PLAYING":
                announcement_finished = True
                break

        if not announcement_finished:
            time.sleep(1)
            finished_waits += 1
            if finished_waits >= timeout:
                logging.error(
                    'Announcement still playing after timeout of %s seconds, will force stop',
                    timeout)
                break

    # restore each zone to previous state
    for zone in announce_zones:
        logger.info('Restoring state for %s', zone.player_name)
        try:
            zone.snap.restore(fade=True)
        except Exception: # pylint: disable=broad-except
            logging.error(
                'Failed to restore state on %s',
                zone.player_name,
                exc_info=True)
