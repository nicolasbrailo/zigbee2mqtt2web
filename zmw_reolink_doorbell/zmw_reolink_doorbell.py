"""MQTT doorbell camera service with motion detection and recording."""
import os
import pathlib
import threading

from flask import send_file, request, jsonify

from zzmw_lib.mqtt_proxy import MqttProxy
from zzmw_lib.service_runner import service_runner_with_www, build_logger

from reolink import ReolinkDoorbell
from nvrish import Nvr

log = build_logger("ZmwReolinkDoorbell")


class _MqttProxy(MqttProxy):
    """Dummy class to bypass required on_mqtt_json_msg def, and let it instead be overriden on runtime"""
    def __init__(self, cfg, topic):
        self.topic = topic
        super().__init__(cfg, topic)

    def on_mqtt_json_msg(self, topic, payload):
        pass

    def get_service_meta(self):
        return {
            "name": self.topic,
            "mqtt_topic": self.topic,
            "methods": ["snap", "rec"],
            "announces": ["on_snap_ready", "on_doorbell_button_pressed", "on_motion_detected",
                          "on_motion_cleared", "on_motion_timeout", "on_new_recording",
                          "on_recording_failed", "on_reencoding_ready", "on_reencoding_failed"],
            "www": self._public_url_base,
        }


class ZmwReolinkDoorbell(ReolinkDoorbell):
    """MQTT-enabled doorbell camera that broadcasts events and handles commands."""
    def __init__(self, cfg, webhook, public_url_base):
        ReolinkDoorbell.__init__(self, cfg, webhook)
        self._mqtt = _MqttProxy(cfg, "zmw_reolink_doorbell")
        self._mqtt.on_mqtt_json_msg = self.on_mqtt_json_msg
        self._mqtt._public_url_base = public_url_base
        self._mqtt.loop_forever_bg()

    def disconnect(self):
        self._mqtt.stop()
        super().disconnect()

    def on_mqtt_json_msg(self, topic, payload):
        """Handle MQTT messages for snapshot and recording commands."""
        match topic:
            case "snap":
                self._mqtt.broadcast(f"{self._mqtt.topic}/on_snap_ready", {
                    'event': 'on_snap_ready',
                    'cam_host': self.get_cam_host(),
                    'snap_path': self.get_snapshot(),
                })
            case "rec":
                self.start_recording(payload.get('secs', None))
            case _:
                pass

    def on_doorbell_button_pressed(self, cam_host, snap_path, full_cam_msg):
        self._mqtt.broadcast(f"{self._mqtt.topic}/on_doorbell_button_pressed", {
            'event': 'on_doorbell_button_pressed',
            'cam_host': cam_host,
            'snap_path': snap_path,
            'full_cam_msg': full_cam_msg,
        })

    def on_motion_detected(self, cam_host, path_to_img, motion_level, full_cam_msg):
        self._mqtt.broadcast(f"{self._mqtt.topic}/on_motion_detected", {
            'event': 'on_motion_detected',
            'cam_host': cam_host,
            'path_to_img': path_to_img,
            'motion_level': motion_level,
            'full_cam_msg': full_cam_msg,
        })

    def on_motion_cleared(self, cam_host, full_cam_msg):
        self._mqtt.broadcast(f"{self._mqtt.topic}/on_motion_cleared", {
            'event': 'on_motion_cleared',
            'cam_host': cam_host,
            'full_cam_msg': full_cam_msg,
        })

    def on_motion_timeout(self, cam_host, timeout):
        self._mqtt.broadcast(f"{self._mqtt.topic}/on_motion_timeout", {
            'event': 'on_motion_timeout',
            'cam_host': cam_host,
            'timeout': timeout,
        })

    def on_new_recording(self, cam_host, path):
        self._mqtt.broadcast(f"{self._mqtt.topic}/on_new_recording", {
            'event': 'on_new_recording',
            'cam_host': cam_host,
            'path': path,
        })

    def on_recording_failed(self, cam_host, path):
        self._mqtt.broadcast(f"{self._mqtt.topic}/on_recording_failed", {
            'event': 'on_recording_failed',
            'cam_host': cam_host,
            'path': path,
        })

    def on_reencoding_ready(self, cam_host, orig_path, reencode_path):
        self._mqtt.broadcast(f"{self._mqtt.topic}/on_reencoding_ready", {
            'event': 'on_reencoding_ready',
            'cam_host': cam_host,
            'orig_path': orig_path,
            'reencode_path': reencode_path,
        })

    def on_reencoding_failed(self, cam_host, path):
        self._mqtt.broadcast(f"{self._mqtt.topic}/on_reencoding_failed", {
            'event': 'on_reencoding_failed',
            'cam_host': cam_host,
            'path': path,
        })


class DoorbellService:
    """Wrapper to make doorbell cam compatible with standard service_runner_with_www"""

    def __init__(self, cfg, www):
        # Build webhook URL from Flask server info
        webhook_url = f"{www.public_url_base}/doorbell"

        # Initialize camera and NVR
        self.cam = ZmwReolinkDoorbell(cfg, webhook_url, www.public_url_base)
        self.nvr = Nvr(cfg['rec_path'], www)
        self._stop_event = threading.Event()

        # Register Flask routes using www.serve_url()
        www.serve_url('/doorbell', self._doorbell_webhook, methods=['GET', 'POST'])
        www.serve_url('/snap', self._snap)
        www.serve_url('/lastsnap', self._lastsnap)
        www.serve_url('/record', self._record)

        # Register www directory
        wwwdir = os.path.join(pathlib.Path(__file__).parent.resolve(), 'www')
        www.register_www_dir(wwwdir)

        # Connect to camera (starts background tasks)
        self.cam.connect()

    def _doorbell_webhook(self):
        """Handle camera webhook events"""
        return self.cam.on_cam_webhook()

    def _snap(self):
        """Get current snapshot from camera"""
        fpath = self.cam.get_snapshot()
        return send_file(fpath, mimetype='image/jpeg')

    def _lastsnap(self):
        """Get last saved snapshot"""
        return send_file(self.cam.get_last_snapshot_path(), mimetype='image/jpeg')

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

    def loop_forever(self):
        """Block until stop() is called. Actual work happens in background threads."""
        log.info("Doorbell service running")
        self._stop_event.wait()  # Just block here

    def stop(self):
        """Cleanup on shutdown"""
        log.info("Stopping doorbell service...")
        self.cam.disconnect()
        self._stop_event.set()


service_runner_with_www(DoorbellService)
