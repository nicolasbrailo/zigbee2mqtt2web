"""MQTT doorbell camera service with motion detection and recording."""
import os
import pathlib
import time

from flask import send_file, request, jsonify

from zzmw_lib.zmw_mqtt_service import ZmwMqttService
from zzmw_lib.logs import build_logger
from zzmw_lib.service_runner import service_runner

from reolink import ReolinkDoorbell
from nvrish import Nvr

log = build_logger("ZmwReolinkCams")

class ZmwReolinkDoorbellCam(ReolinkDoorbell):
    """ Link Reolink events to mqtt b-casts """

    def __init__(self, cfg, webhook_url, mqtt, scheduler):
        super().__init__(cfg, webhook_url, scheduler)
        self._mqtt = mqtt

    def on_doorbell_button_pressed(self, cam_host, snap_path, full_cam_msg):
        self._mqtt.on_doorbell_pressed()
        self._mqtt.publish_own_svc_message("on_doorbell_button_pressed", {
            'event': 'on_doorbell_button_pressed',
            'cam_host': cam_host,
            'snap_path': snap_path,
            'full_cam_msg': full_cam_msg,
        })

    def on_motion_detected(self, cam_host, path_to_img, motion_level, full_cam_msg):
        self._mqtt.publish_own_svc_message("on_motion_detected", {
            'event': 'on_motion_detected',
            'cam_host': cam_host,
            'path_to_img': path_to_img,
            'motion_level': motion_level,
            'full_cam_msg': full_cam_msg,
        })

    def on_motion_cleared(self, cam_host, full_cam_msg):
        self._mqtt.publish_own_svc_message("on_motion_cleared", {
            'event': 'on_motion_cleared',
            'cam_host': cam_host,
            'full_cam_msg': full_cam_msg,
        })

    def on_motion_timeout(self, cam_host, timeout):
        self._mqtt.publish_own_svc_message("on_motion_timeout", {
            'event': 'on_motion_timeout',
            'cam_host': cam_host,
            'timeout': timeout,
        })

    def on_new_recording(self, cam_host, path):
        self._mqtt.publish_own_svc_message("on_new_recording", {
            'event': 'on_new_recording',
            'cam_host': cam_host,
            'path': path,
        })

    def on_recording_failed(self, cam_host, path):
        self._mqtt.publish_own_svc_message("on_recording_failed", {
            'event': 'on_recording_failed',
            'cam_host': cam_host,
            'path': path,
        })

    def on_reencoding_ready(self, cam_host, orig_path, reencode_path):
        self._mqtt.publish_own_svc_message("on_reencoding_ready", {
            'event': 'on_reencoding_ready',
            'cam_host': cam_host,
            'orig_path': orig_path,
            'reencode_path': reencode_path,
        })

    def on_reencoding_failed(self, cam_host, path):
        self._mqtt.publish_own_svc_message("on_reencoding_failed", {
            'event': 'on_reencoding_failed',
            'cam_host': cam_host,
            'path': path,
        })

class ZmwReolinkCam(ZmwMqttService):
    """ Bridge between Zmw services and a Reolink cam """
    DOORBELL_ALERT_DURATION_SECS = 60

    def __init__(self, cfg, www, sched):
        super().__init__(cfg, "zmw_reolink_doorbell", scheduler=sched)
        self._doorbell_pressed_at = None

        # Initialize camera and NVR
        self.cam = ZmwReolinkDoorbellCam(cfg, webhook_url=f"{www.public_url_base}/doorbell", mqtt=self, scheduler=sched)
        self.nvr = Nvr(cfg['rec_path'], www)

        # Register Flask routes
        www.serve_url('/doorbell', self.cam.on_cam_webhook, methods=['GET', 'POST'])
        www.serve_url('/snap', self._get_snap)
        www.serve_url('/lastsnap', self._get_last_snap)
        www.serve_url('/record', self._record)

        # Register www directory
        wwwdir = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        www.register_www_dir(wwwdir)

        # Connect to camera (starts background tasks)
        self.cam.connect()

    def on_doorbell_pressed(self):
        """Record when the doorbell was pressed"""
        self._doorbell_pressed_at = time.time()

    def get_service_alerts(self):
        """Return alert if doorbell was pressed within the last 60 seconds"""
        if self._doorbell_pressed_at is None:
            return []
        elapsed = time.time() - self._doorbell_pressed_at
        if elapsed < self.DOORBELL_ALERT_DURATION_SECS:
            secs_ago = int(elapsed)
            return [f"Doorbell pressed {secs_ago} seconds ago"]
        return []

    def _get_snap(self):
        """Get a new snapshot from camera"""
        snap_path = self.cam.get_snapshot()
        if snap_path is None:
            return jsonify({'error': 'Failed to get snapshot from camera'}), 500
        return send_file(snap_path, mimetype='image/jpeg')

    def _get_last_snap(self):
        """Get the last saved snapshot"""
        snap_path = self.cam.get_last_snapshot_path()
        if snap_path is None:
            return jsonify({'error': 'No snapshot available'}), 404
        return send_file(snap_path, mimetype='image/jpeg')

    def _record(self):
        """Start video recording with duration validation"""
        try:
            secs = request.args.get('secs', type=int)
            if secs is None or secs < 5 or secs > 120:
                return jsonify({'error': f'Invalid duration {secs}, must be [5, 120]'}), 400

            self.cam.start_recording(secs)
            return jsonify({'status': 'ok', 'duration': secs})
        except ValueError:
            return jsonify({'error': 'Invalid secs parameter'}), 400

    def stop(self):
        """Cleanup on shutdown"""
        log.info("Stopping doorbell service: disconnect from camera...")
        self.cam.disconnect()
        super().stop()

    def on_service_received_message(self, subtopic, payload):
        """Handle MQTT messages for snapshot and recording commands."""
        match subtopic:
            case "snap":
                self.publish_own_svc_message("on_snap_ready", {
                    'event': 'on_snap_ready',
                    'cam_host': self.cam.get_cam_host(),
                    'snap_path': self.cam.get_snapshot(),
                })
            case "rec":
                self.cam.start_recording(payload.get('secs', None))
            case _:
                pass

service_runner(ZmwReolinkCam)
