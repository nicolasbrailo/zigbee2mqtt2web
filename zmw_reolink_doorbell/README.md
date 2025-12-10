# mqtt_doorbell_cam

Reolink doorbell camera service with motion detection, recording, and event broadcasting over MQTT.
Connects to a Reolink doorbell camera via webhook/ONVIF, captures snapshots, records video clips, and broadcasts camera events (button press, motion) to other services via MQTT.

## MQTT
**Methods (subscribe):**
- `mqtt_doorbell_cam/snap` - Take a snapshot
- `mqtt_doorbell_cam/rec` - Start recording (`{secs: N}`)

**Announces (publish):**
- `on_snap_ready` - Snapshot captured
- `on_doorbell_button_pressed` - Doorbell button pressed
- `on_motion_detected` - Motion detected
- `on_motion_cleared` - Motion cleared
- `on_motion_timeout` - Motion event timed out
- `on_new_recording` - Recording completed
- `on_recording_failed` - Recording failed
- `on_reencoding_ready` - Re-encoding completed
- `on_reencoding_failed` - Re-encoding failed

## WWW Endpoints

- `/doorbell` - Camera webhook endpoint
- `/snap` - Get current snapshot (JPEG)
- `/lastsnap` - Get last saved snapshot (JPEG)
- `/record?secs=N` - Start recording (5-120 seconds)
