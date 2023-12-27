"""
Random Sonos helpers.

Alarm/announcement system inspired from
https://github.com/SoCo/SoCo/blob/master/examples/snapshot/multi_zone_snap.py
https://github.com/jishi/node-sonos-http-api/blob/master/lib/helpers/all-player-announcement.js
https://github.com/jjlawren/sonos-websocket/tree/main
"""

import asyncio
import aiohttp
import time

import soco
from soco.snapshot import Snapshot

import logging
log = logging.getLogger('ZMWSonos')

# XXX
API_KEY = "123e4567-e89b-12d3-a456-426655440000"

async def _sonos_ws_connect(ip_addr):
    uri = f"wss://{ip_addr}:1443/websocket/api"
    headers = {
        "X-Sonos-Api-Key": API_KEY,
        "Sec-WebSocket-Protocol": "v1.api.smartspeaker.audio",
    }

    log.debug("Opening websocket to %s", uri)
    try:
        session = aiohttp.ClientSession()
        session.ws = await session.ws_connect(uri, headers=headers, verify_ssl=False)
        return session
    except aiohttp.ClientResponseError as exc:
        log.error("HTTP return code %s connecting to Sonos speaker at %s", exc.code, uri)
    except (aiohttp.ClientConnectionError, asyncio.TimeoutError):
        log.error("Failed to connect to Sonos speaker at %s", uri)
    except Exception:  # pylint: disable=broad-except
        log.error("Unknown error connecting to Sonos speaker %s", uri, exc_info=True)
    return None

async def _async_sonos_announce_one(ip_addr, soco_uid, alert_uri, volume=None):
    # ~Inspired on~ stolen from https://github.com/jjlawren/sonos-websocket/blob/main/sonos_websocket/websocket.py
    session = await _sonos_ws_connect(ip_addr)
    if session is None:
        return

    if session.ws is None:
        return

    command = {
        "namespace": "audioClip:1",
        "command": "loadAudioClip",
        "playerId": soco_uid,
    }
    options: dict[str, Any] = {
        "name": "Sonos Websocket",
        "appId": "com.jjlawren.sonos_websocket",
        "streamUrl": alert_uri,
    }

    if volume:
        options["volume"] = volume

    try:
        await session.ws.send_json([command, options])
        log.debug("Asked speaker %s to play %s", ip_addr, alert_uri)
        msg = await session.ws.receive()
        log.debug("Speaker %s replies %s", ip_addr, str(msg))
    except Exception:  # pylint: disable=broad-except
        log.error("Unknown error sending command to Sonos speaker %s", ip_addr, exc_info=True)

    await session.ws.close()
    await session.close()
    return True

async def _async_sonos_announce_all(alert_uri, volume=None):
    tasks = []
    for spk in soco.discover():
        tasks.append(_async_sonos_announce_one(spk.ip_address, spk.uid, alert_uri, volume))
    await asyncio.gather(*tasks)

def sonos_announce_ws(alert_uri, volume=None):
    """ Send an announcement to all zones, in a fancy way: should lower the volume of current media,
    play announce and then restore. Requires an API key """
    asyncio.run(_async_sonos_announce_all(alert_uri, volume))



def sonos_announce_local(alert_uri, volume, timeout, force_play):
    """ Send an announcement to all zones, using local only APIs. Use as a fallback for
    sonos_announce_ws """

    log.info(
        'Preparing announcement %s volume %s timeout %s',
        alert_uri, volume, timeout)

    # prepare all zones for playing the alert
    zones = soco.discover()
    announce_zones = []
    for zone in zones:
        trans_state = zone.get_current_transport_info()
        if trans_state["current_transport_state"] == "PLAYING" and not force_play:
            log.info(
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
    log.info('Requesting Sonos to play announcement: %s', alert_uri)
    for zone in announce_zones:
        log.info('  ask %s to play announcement', zone.player_name)
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
        log.info('Waiting for announcement to finish...')
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
        log.info('Restoring state for %s', zone.player_name)
        try:
            zone.snap.restore(fade=True)
        except Exception: # pylint: disable=broad-except
            logging.error(
                'Failed to restore state on %s',
                zone.player_name,
                exc_info=True)



def sonos_announce(alert_uri, volume=None, timeout_secs=10, force_play=False):
    try:
        sonos_announce_ws(alert_uri, volume)
        return
    except:
        logging.error('Failed to Sonos announce, fallback to local only announce')

    sonos_announce_local(alert_uri, volume, timeout_secs, force_play)

