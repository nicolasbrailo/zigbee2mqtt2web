""" Doorbell/ONVIF-camera service """

from threading import Lock
import aiohttp
import asyncio
import logging
import ssl
import sys
import time

from apscheduler.schedulers.background import BackgroundScheduler
from flask import request as FlaskRequest

from .thirdparty.reolink_aio.reolink_aio.api import Host as ReolinkDoorbellHost
from .thirdparty.reolink_aio.reolink_aio.exceptions import SubscriptionError
from .thirdparty.reolink_aio.reolink_aio.helpers import parse_reolink_onvif_event

logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("apscheduler.executors.default").setLevel(logging.ERROR)
logging.getLogger("reolink_aio.api").setLevel(logging.ERROR)
logging.getLogger("reolink_aio.api.data").setLevel(logging.ERROR)
logging.getLogger("reolink_aio.helpers").setLevel(logging.ERROR)
logging.getLogger("zigbee2mqtt2web_extras.thirdparty.reolink_aio.reolink_aio.api").setLevel(logging.ERROR)
logging.getLogger("zigbee2mqtt2web_extras.thirdparty.reolink_aio.reolink_aio.api.data").setLevel(logging.ERROR)
logging.getLogger("zigbee2mqtt2web_extras.thirdparty.reolink_aio.reolink_aio.helpers").setLevel(logging.ERROR)

log = logging.getLogger(__name__)


# Watchdog for cam subscription
_CAM_SUBSCRIPTION_CHECK_INTERVAL_SECS=60
# If ONVIF messages arrive in this timewindow, we'll consider them duplicated
_DEBOUNCE_TIMEOUT_SEC = 15


def _register_webhook_url(cfg, zmw, cb):
    # Ensure cfg has required keys
    cfg['webhook_base_path']
    if not 'webhook_service' in cfg or len(cfg['webhook_service']) == 0:
        raise KeyError("webhook_service must be configured to a server accesible by the camera")

    # Create a webhook endpoint in the zmw web server
    if len(cfg['webhook_base_path']) > 0 and cfg['webhook_base_path'][0] == '/':
        webhook_path = f"{cfg['webhook_base_path']}{cfg['host']}"
    else:
        webhook_path = f"/{cfg['webhook_base_path']}{cfg['host']}"

    if cfg['webhook_service'][-1] == '/':
        webhook_url = f"{cfg['webhook_service']}{webhook_path}"
    else:
        webhook_url = f"{cfg['webhook_service']}/{webhook_path}"

    zmw.webserver.add_url_rule(webhook_path, cb, methods=['GET', 'POST'])
    log.info("Registered webhook %s for camera %s...", webhook_url, cfg['host'])
    return webhook_url


async def _connect_to_cam(cfg, webhook_url):
    log.info("Connecting to doorbell at %s...", cfg['host'])
    cam = ReolinkDoorbellHost(cfg['host'], cfg['user'], cfg['pass'], use_https=True)

    # Fetch all cam state
    await cam.get_host_data()
    await cam.get_states()
    cam.construct_capabilities()

    # Cleanup old subscriptions, if there were any
    await cam.unsubscribe()
    await cam.subscribe(webhook_url)

    log.info("Connected to doorbell %s %s model %s - firmware %s",
        cfg['host'],
        cam.camera_name(0),
        cam.camera_model(0),
        cam.camera_sw_version(0))

    if not cam.is_doorbell(0):
        log.error("Something is wrong, %s reports it isn't a doorbell!", cfg['host'])

    return cam


class ReolinkDoorbell:
    """ Subscribe to ONVIF notifications from a Reolink cam """

    def __init__(self, cfg, zmw):
        """ Logs in and subscribes to camera events """
        # __del__ will run if the ctor fails, so mark "we've been here" somehow
        self._cam = None

        webhook_url = _register_webhook_url(cfg, zmw, self._on_cam_webhook)
        self._runner = asyncio.get_event_loop()
        cam = self._runner.run_until_complete(_connect_to_cam(cfg, webhook_url))
        self._cam_host = cfg['host']

        self._scheduler = BackgroundScheduler()
        self._cam_subscription_watchdog = self._scheduler.add_job(
            func=self._check_cam_subscription,
            trigger="interval",
            seconds=_CAM_SUBSCRIPTION_CHECK_INTERVAL_SECS)

        # Object should be fully constructed now
        self._debounce_msg = {}
        self._motionEventLevel = 0
        self._cfg = cfg
        self._webhook_url = webhook_url
        self._zmw = zmw
        self._cam = cam
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
                log.error(f"Cam %s subscription error", self._cam_host, exc_info=True)
            except RuntimeError:
                log.error(f"Runtime error renewing cam %s subscription", self._cam_host, exc_info=True)

            try:
                await self._cam.unsubscribe()
                await self._cam.subscribe(self._webhook_url)
                log.info("Set up new subscription %s for cam %s...", self._webhook_url, self._cam_host)
                return
            except SubscriptionError:
                log.error(f"Error creating new cam %s subscription", self._cam_host, exc_info=True)
            except RuntimeError:
                log.error(f"Runtime error creating new cam %s subscription", self._cam_host, exc_info=True)

            log.error(f"All recovery attempts failed, start new connection to cam %s", self._cam_host)
            try:
                # Try to cleanup (but likely to fail, if we got here everything may be broken)
                await self._cam.unsubscribe()
                await self._cam.logout()
            except:
                pass
            self._cam = await _connect_to_cam(self._cfg, self._webhook_url)

        must_renew = False
        try:
            t = self._cam.renewtimer()
            if t <= 100:
                log.debug("Subscription to cam %s has %s seconds remaining, renewing",
                          self._cam_host, t)
                must_renew = True
        except Exception:
            must_renew = True
            log.error(f"Error checking for cam %s subscription", self._cam_host, exc_info=True)

        if must_renew:
            self._runner.run_until_complete(_renew_async())

    def _on_cam_webhook(self):
        try:
            msg = parse_reolink_onvif_event(FlaskRequest.data)
            log.debug("Received event from camera %s: %s", self._cam_host, str(msg))
            # Flatten the message: we don't care about channels
            flatmsg = {}
            for k in msg.keys():
                for kk in msg[k].keys():
                    if kk in flatmsg:
                        log.error("Format error from camera %s: duplicated key %s", self._cam_host, k)
                    flatmsg[kk] = msg[k][kk]

            with self._announce_lock:
                self._on_cam_webhook_msg(flatmsg)
        except:
            log.error("Error processing event from camera %s: %s", self._cam_host, str(msg), exc_info=True)
        # Tell the camera we succesfully processed the message, always
        return "", 200

    def _on_cam_webhook_msg(self, msg):
        # msg should look something like this:
        # {'Motion': False, 'MotionAlarm': False, 'Visitor': False,
        #  'FaceDetect': False, 'PeopleDetect': False, 'VehicleDetect': False,
        # 'DogCatDetect': False}

        def debounce(msg, key, keyMustExist=True):
            if key not in msg:
                if keyMustExist:
                    log.error("Camera %s missing expected key %s from subscription", self._cam_host, key)
                return False

            # Event isn't active, skip debounce logic
            if msg[key] == False:
                return False

            dt = 2 * _DEBOUNCE_TIMEOUT_SEC
            if f'{key}_last_true' in self._debounce_msg:
                dt = time.time() - self._debounce_msg[f'{key}_last_true']
            debounceActive = dt > _DEBOUNCE_TIMEOUT_SEC
            self._debounce_msg[f'{key}_last_true'] = time.time()
            return debounceActive

        if debounce(msg, 'Visitor'):
            self.on_doorbell_button_pressed()

        prevMotionEventLevel = self._motionEventLevel
        self._motionEventLevel = 0
        if debounce(msg, 'Motion', keyMustExist=False):
            self._motionEventLevel += 1
        if debounce(msg, 'MotionAlarm', keyMustExist=False):
            self._motionEventLevel += 1
        if debounce(msg, 'PeopleDetect', keyMustExist=False):
            self._motionEventLevel += 1

        if prevMotionEventLevel > 0 and self._motionEventLevel == 0:
            self.on_motion_cleared()
        if self._motionEventLevel > 0:
            self.on_motion_detected(self._motionEventLevel)

        return

    def on_doorbell_button_pressed(self):
        log.info("Doorbell cam %s says someone pressed the visitor button", self._cam_host)

    def on_motion_detected(self, motion_level):
        log.info("Doorbell cam %s says someone is at the door", self._cam_host)

    def on_motion_cleared(self):
        log.info("Doorbell cam %s says no motion is detected", self._cam_host)

    def get_snapshot(self, fpath):
        with open(fpath, 'wb') as fp:
            fp.write(self._runner.run_until_complete(self._cam.get_snapshot(0)))

