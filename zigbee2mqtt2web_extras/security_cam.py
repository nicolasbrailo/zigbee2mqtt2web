""" FTP server for a security cam: sends a Whatsapp notification on file upload """

import os
from dataclasses import dataclass
from apscheduler.schedulers.background import BackgroundScheduler

from .utils.ftpd import Ftpd

import logging
logger = logging.getLogger(__name__)


@dataclass(frozen=False)
class _CamMotionEvent:
    motion_detected: bool = False
    watchdog: object = None


class SecurityCam(Ftpd):
    """ Creates an FTPD. This class expects the camera to upload a picture when motion starts,
    and then a video once the motion ends """

    def __init__(self, cfg, wa):
        cfg['ftp']['ip_allowlist'] = cfg['cam_ips']
        Ftpd.__init__(self, cfg['ftp'])
        logger.info('Known cameras: %s', cfg['cam_ips'])

        self._wa = wa
        self._motion_events = {}
        for cam_ip in cfg['cam_ips']:
            self._motion_events[cam_ip] = _CamMotionEvent()

        self._timeout_secs = cfg['motion_timeout_secs']
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()

    def _clear_watchdog(self, remote_ip):
        if self._motion_events[remote_ip].watchdog is None:
            logger.error('BUG: watchdog out of sync with motion event')
        else:
            self._motion_events[remote_ip].watchdog.remove()
            self._motion_events[remote_ip].watchdog = None

    def _on_upload_complete(self, remote_ip, fpath):
        if remote_ip not in self._motion_events:
            logger.critical(
                "This shouldn't happen: unknown client %s uploaded file %s",
                remote_ip,
                fpath)
            return

        _, ext = os.path.splitext(fpath)
        ext = ext[1:]
        if ext in ['jpg', 'jpeg']:
            self._motion_detected(remote_ip, fpath)
            return
        if ext == 'mp4':
            self._motion_cleared(remote_ip, fpath)
            return
        logger.error(
            'Error: client %s uploaded unknown file type %s',
            remote_ip,
            fpath)

    def _motion_detected(self, remote_ip, fpath):
        if self._motion_events[remote_ip].motion_detected:
            logger.info(
                'Client %s sent update image, alarm already on',
                remote_ip)
            self._clear_watchdog(remote_ip)

        # Schedule timeout, in case we never get motion cleared event
        self._motion_events[remote_ip].watchdog = self._scheduler.add_job(
            func=self._make_watchdog_handler(remote_ip),
            trigger="interval",
            seconds=self._timeout_secs)

        if self._motion_events[remote_ip].motion_detected:
            # Motion was already detected, no need to re-send alarm
            return

        # Send alarms
        self._motion_events[remote_ip].motion_detected = True
        media_id = self._wa.upload_image(fpath)
        self._wa.message_from_params_template(media_id)

    def _motion_cleared(self, remote_ip, _fpath):
        if not self._motion_events[remote_ip].motion_detected:
            logger.error(
                "This shouldn't happen: camera %s cleared unknown motion alarm",
                remote_ip)
            return

        self._clear_watchdog(remote_ip)
        self._motion_events[remote_ip].motion_detected = False
        logger.info('Camera %s cleared motion alarm', remote_ip)

    def _make_watchdog_handler(self, remote_ip):
        def _watchdog_timeout():
            if not self._motion_events[remote_ip].motion_detected:
                logger.error(
                    "This shouldn't happen: watchdog for camera %s "
                    "triggered, but motion event is inactive", remote_ip)
                return
            logger.warning(
                'Camera %s failed to clear motion alarm after timeout '
                'of %d seconds. Assuming motion event expired and '
                'camera is buggy.', remote_ip, self._timeout_secs)
            self._motion_events[remote_ip].motion_detected = False
            self._clear_watchdog(remote_ip)
        return _watchdog_timeout
