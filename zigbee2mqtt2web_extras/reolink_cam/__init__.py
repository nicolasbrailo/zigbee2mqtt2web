""" Doorbell/ONVIF-camera service """

from datetime import datetime, timedelta
from threading import Lock
import asyncio
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from flask import request as FlaskRequest

import os
import pathlib
import sys

log = logging.getLogger(__name__)
sys.path.append(os.path.join(pathlib.Path(__file__).parent.parent.resolve(), 'thirdparty', 'reolink_aio'))

from reolink_aio.api import Host as ReolinkDoorbellHost
from reolink_aio.exceptions import SubscriptionError
from reolink_aio.helpers import parse_reolink_onvif_event

from .rtsp import Rtsp
from .nvrish import Nvr

logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("apscheduler.executors.default").setLevel(logging.ERROR)
logging.getLogger("reolink_aio.api").setLevel(logging.ERROR)
logging.getLogger("reolink_aio.api.data").setLevel(logging.ERROR)
logging.getLogger("reolink_aio.helpers").setLevel(logging.ERROR)
logging.getLogger(
    "zigbee2mqtt2web_extras.thirdparty.reolink_aio.reolink_aio.api").setLevel(logging.ERROR)
logging.getLogger(
    "zigbee2mqtt2web_extras.thirdparty.reolink_aio.reolink_aio.api.data").setLevel(logging.ERROR)
logging.getLogger(
    "zigbee2mqtt2web_extras.thirdparty.reolink_aio.reolink_aio.helpers").setLevel(logging.ERROR)

log = logging.getLogger(__name__)


# Watchdog for cam subscription
_CAM_SUBSCRIPTION_CHECK_INTERVAL_SECS = 60
# If ONVIF messages arrive in this timewindow, we'll consider them duplicated
_DEBOUNCE_TIMEOUT_SEC = 15
# How often should we check if movement is still detected after the event fires
_CAM_MOVEMENT_ACTIVE_WATCHDOG = 60


def _register_webhook_url(cfg, zmw, cb):
    # Ensure cfg has required keys
    cfg['webhook_base_path']  # pylint: disable=pointless-statement
    if 'webhook_service' not in cfg or len(cfg['webhook_service']) == 0:
        raise KeyError(
            "webhook_service must be configured to a server accesible by the camera")

    # Create a webhook endpoint in the zmw web server
    if len(cfg['webhook_base_path']
           ) > 0 and cfg['webhook_base_path'][0] == '/':
        webhook_path = f"{cfg['webhook_base_path']}{cfg['host']}"
    else:
        webhook_path = f"/{cfg['webhook_base_path']}{cfg['host']}"

    if cfg['webhook_service'][-1] == '/':
        webhook_url = f"{cfg['webhook_service']}{webhook_path}"
    else:
        webhook_url = f"{cfg['webhook_service']}/{webhook_path}"

    zmw.webserver.add_url_rule(webhook_path, cb, methods=['GET', 'POST'])
    log.info(
        "Registered webhook %s for camera %s...",
        webhook_url,
        cfg['host'])
    return webhook_url


async def _connect_to_cam(cfg, webhook_url):
    log.info("Connecting to doorbell at %s...", cfg['host'])
    cam = ReolinkDoorbellHost(
        cfg['host'],
        cfg['user'],
        cfg['pass'],
        use_https=True)

    # Fetch all cam state
    await cam.get_host_data()
    await cam.get_states()
    cam.construct_capabilities()

    # Cleanup old subscriptions, if there were any
    # await cam.unsubscribe()
    await cam.unsubscribe_all()
    await cam.subscribe(webhook_url)

    log.info("Connected to doorbell %s %s model %s - firmware %s",
             cfg['host'],
             cam.camera_name(0),
             cam.camera_model(0),
             cam.camera_sw_version(0))

    if not cam.is_doorbell(0):
        log.error(
            "Something is wrong, %s reports it isn't a doorbell!",
            cfg['host'])

    rtsp = await cam.get_rtsp_stream_source(0, "main")

    return cam, rtsp


class ReolinkDoorbell:
    """ Subscribe to ONVIF notifications from a Reolink cam """

    def __init__(self, cfg, zmw):
        """ Logs in and subscribes to camera events """
        # __del__ will run if the ctor fails, so mark "we've been here" somehow
        self._cam = None

        webhook_url = _register_webhook_url(cfg, zmw, self._on_cam_webhook)
        self._runner = asyncio.get_event_loop()
        cam, rtspurl = self._runner.run_until_complete(
            _connect_to_cam(cfg, webhook_url))

        self._cam_host = cfg['host']

        self._scheduler = BackgroundScheduler()
        self._cam_subscription_watchdog = self._scheduler.add_job(
            func=self._check_cam_subscription,
            trigger="interval",
            seconds=_CAM_SUBSCRIPTION_CHECK_INTERVAL_SECS)

        # Object should be fully constructed now
        self._snap_path_on_movement = None
        if 'snap_path_on_movement' in cfg:
            self._snap_path_on_movement = cfg['snap_path_on_movement']

        self._debounce_msg = {}
        self._motion_evt_lvl = 0
        self._motion_evt_job = None
        self._cfg = cfg
        self._webhook_url = webhook_url
        self._zmw = zmw
        self._cam = cam

        self._rec_on_movement = False
        self.rtsp = None
        if 'rec_path' in cfg:
            self._rec_on_movement = cfg['rec_on_movement'] if 'rec_on_movement' in cfg else False
            self.rtsp = Rtsp(self._cam_host,
                             self._zmw.announce_system_event,
                             rtspurl,
                             cfg['rec_path'],
                             int(cfg['rec_retention_days']),
                             int(cfg['rec_default_duration_secs']))

        self._announce_lock = Lock()
        self._scheduler.start()

    def __del__(self):
        self.deinit()

    def deinit(self):
        """ Logs out and tries to cleanup subscriptions to events in the camera """
        if self._cam is None:
            # Constructor failed
            return

        async def _async_deinit():
            await self._cam.unsubscribe()
            await self._cam.logout()
            log.info("Disconnecting from doorbell at %s...", self._cam_host)
        self._cam_subscription_watchdog.remove()
        self._runner.run_until_complete(_async_deinit())
        self._runner.close()

    def _check_cam_subscription(self):
        async def _renew_async():
            try:
                await self._cam.renew()
                return
            except SubscriptionError:
                log.error(
                    "Cam %s subscription error",
                    self._cam_host,
                    exc_info=True)
            except RuntimeError:
                log.error(
                    "Runtime error renewing cam %s subscription",
                    self._cam_host,
                    exc_info=True)

            try:
                await self._cam.unsubscribe()
                await self._cam.subscribe(self._webhook_url)
                log.info(
                    "Set up new subscription %s for cam %s...",
                    self._webhook_url,
                    self._cam_host)
                return
            except SubscriptionError:
                log.error(
                    "Error creating new cam %s subscription",
                    self._cam_host,
                    exc_info=True)
            except RuntimeError:
                log.error(
                    "Runtime error creating new cam %s subscription",
                    self._cam_host,
                    exc_info=True)

            log.error(
                "All recovery attempts failed, start new connection to cam %s",
                self._cam_host)
            try:
                # Try to cleanup (but likely to fail, if we got here everything
                # may be broken)
                await self._cam.unsubscribe()
                await self._cam.logout()
            except Exception:  # pylint: disable=broad-except
                pass
            self._cam, rtspurl = await _connect_to_cam(self._cfg, self._webhook_url)
            #TODO check if the rtspurl changed

        must_renew = False
        try:
            t = self._cam.renewtimer()
            if t <= 100:
                log.debug(
                    "Subscription to cam %s has %s seconds remaining, renewing",
                    self._cam_host,
                    t)
                must_renew = True
        except Exception:  # pylint: disable=broad-except
            must_renew = True
            log.error(
                "Error checking for cam %s subscription",
                self._cam_host,
                exc_info=True)

        if must_renew:
            self._runner.run_until_complete(_renew_async())

    def _on_cam_webhook(self):
        try:
            msg = parse_reolink_onvif_event(FlaskRequest.data)
            log.debug(
                "Received event from camera %s: %s",
                self._cam_host,
                str(msg))
            # Flatten the message: we don't care about channels
            flatmsg = {}
            for k in msg.keys():
                for kk in msg[k].keys():
                    if kk in flatmsg:
                        log.error(
                            "Format error from camera %s: duplicated key %s",
                            self._cam_host,
                            k)
                    flatmsg[kk] = msg[k][kk]

            with self._announce_lock:
                self._on_cam_webhook_msg(flatmsg)
        except Exception:  # pylint: disable=broad-except
            log.error("Error processing event from camera %s: %s",
                      self._cam_host, str(msg), exc_info=True)
        # Tell the camera we succesfully processed the message, always, so it
        # doesn't retry
        return "", 200

    def _on_cam_webhook_msg(self, msg):
        # msg should look something like this:
        # {'Motion': False, 'MotionAlarm': False, 'Visitor': False,
        #  'FaceDetect': False, 'PeopleDetect': False, 'VehicleDetect': False,
        # 'DogCatDetect': False}

        def debounce(msg, key, key_must_exist=True):
            if key not in msg:
                if key_must_exist:
                    log.error(
                        "Camera %s missing expected key %s from subscription",
                        self._cam_host,
                        key)
                return False

            # Event isn't active, skip debounce logic
            if not msg[key]:
                return False

            dt = 2 * _DEBOUNCE_TIMEOUT_SEC
            if f'{key}_last_true' in self._debounce_msg:
                dt = time.time() - self._debounce_msg[f'{key}_last_true']
            debounced_active = dt > _DEBOUNCE_TIMEOUT_SEC
            self._debounce_msg[f'{key}_last_true'] = time.time()
            return debounced_active

        if debounce(msg, 'Visitor'):
            self.on_doorbell_button_pressed(msg)

        # Ignore debounce rules for rtsp pet rules
        for key in ['Visitor', 'Motion', 'MotionAlarm', 'PeopleDetect']:
            if key in msg and msg[key]:
                self.rtsp.pet_timer()
                break

        if msg['PeopleDetect'] and not msg['Motion'] and not msg['MotionAlarm']:
            log.debug("Ignoring camera %s event: people detect outside alarm zone.", self._cam_host)
            return

        prev_motion_event_lvl = self._motion_evt_lvl
        self._motion_evt_lvl = 0
        if debounce(msg, 'Motion', key_must_exist=False):
            self._motion_evt_lvl += 1
        if debounce(msg, 'MotionAlarm', key_must_exist=False):
            self._motion_evt_lvl += 1
        if debounce(msg, 'PeopleDetect', key_must_exist=False):
            self._motion_evt_lvl += 1

        if prev_motion_event_lvl == 0 and self._motion_evt_lvl > 0:
            self._motion_evt_job = self._scheduler.add_job(
                func=self._motion_check_active,
                trigger="interval",
                seconds=_CAM_MOVEMENT_ACTIVE_WATCHDOG)
            self.on_motion_detected(self._motion_evt_lvl, msg)
        elif prev_motion_event_lvl > 0 and self._motion_evt_lvl > 0:
            # Camera reports motion still detected, add more timeout
            if self._motion_evt_job is not None:
                self._motion_evt_job.remove()
            self._motion_evt_job = self._scheduler.add_job(
                func=self._motion_check_active,
                trigger="interval",
                seconds=_CAM_MOVEMENT_ACTIVE_WATCHDOG)
        elif prev_motion_event_lvl > 0 and self._motion_evt_lvl == 0:
            if self._motion_evt_job is not None:
                self._motion_evt_job.remove()
            self._motion_evt_job = None
            self.on_motion_cleared(msg)

    def _motion_check_active(self):
        state_updated = self._runner.run_until_complete(
            self._cam.get_ai_state_all_ch())
        if state_updated and self._cam.motion_detected(0):
            log.info(
                "Doorbell cam %s motion timeout, but motion still active. Waiting more.",
                self._cam_host)

            self._motion_evt_job = self._scheduler.add_job(
                func=self._motion_check_active,
                trigger="interval",
                seconds=_CAM_MOVEMENT_ACTIVE_WATCHDOG)
            return

        if not state_updated:
            log.info(
                "Doorbell cam %s motion timeout, polling state failed",
                self._cam_host)
        elif not self._cam.motion_detected(0):
            log.info(
                "Doorbell cam %s motion timeout, and motion not active: event lost?",
                self._cam_host)

        self._motion_evt_job = None
        self.on_motion_timeout()

    def on_doorbell_button_pressed(self, cam_msg):
        """ Visitor even triggered, someone pressed the doorbell button """
        log.info(
            "Doorbell cam %s says someone pressed the visitor button",
            self._cam_host)
        self._zmw.announce_system_event({
            'event': 'on_doorbell_button_pressed',
            'doorbell_cam': self._cam_host,
            'msg': cam_msg,
        })

    def on_motion_detected(self, motion_level, cam_msg):
        """ Motion detect event fired. Higher motion level means more confidence. """
        log.info("Doorbell cam %s says someone is at the door", self._cam_host)

        if self._snap_path_on_movement is not None:
            try:
                self.get_snapshot(self._snap_path_on_movement)
            except:
                log.error("Failed to save doorbell snapshot", exc_info=True)
                return

        if self._rec_on_movement:
            try:
                self.rtsp.trigger_recording()
            except:
                log.error("Failed to start doorbell recording", exc_info=True)
                return

        self._zmw.announce_system_event({
            'event': 'on_doorbell_cam_motion_detected',
            'doorbell_cam': self._cam_host,
            'snap': self._snap_path_on_movement,
            'motion_level': motion_level,
            'msg': cam_msg,
        })

    def on_motion_cleared(self, msg):
        """ Camera reports no motion is detected now """
        log.info("Doorbell cam %s says no motion is detected", self._cam_host)
        self._zmw.announce_system_event({
            'event': 'on_doorbell_cam_motion_cleared',
            'doorbell_cam': self._cam_host,
            'msg': msg,
        })

    def on_motion_timeout(self):
        """ Motion event started but never finished within a configured timeout """
        log.info(
            "Doorbell cam %s doesn't report motion, but never cleared the event",
            self._cam_host)
        self._zmw.announce_system_event({
            'event': 'on_doorbell_cam_motion_timeout',
            'doorbell_cam': self._cam_host,
        })

    def get_snapshot(self, fpath):
        """ Save a snapshot of the camera feed to fpath """
        with open(fpath, 'wb') as fp:
            fp.write(
                self._runner.run_until_complete(
                    self._cam.get_snapshot(0)))

