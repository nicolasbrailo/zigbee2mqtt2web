# ZmwReolinkDoorbell

Reolink doorbell camera service with motion detection, recording, and event broadcasting over MQTT.

![](README_screenshot.png)

This service connects to a Reolink doorbell camera via webhook/ONVIF, and exposes a set of functionality over MQTT and WWW:

## MQTT messages
**Methods (subscribe):**
- `mqtt_doorbell_cam/snap` - Takes a snapshot, announces response when ready
- `mqtt_doorbell_cam/rec` - Start doorbell cam recording (`{secs: N}`)

**Announces (publish):**
- `on_snap_ready` - Snapshot captured, will reply with the path of the captured file
- `on_doorbell_button_pressed` - Doorbell button pressed
- `on_motion_detected` - Camera reports motion
- `on_motion_cleared` - Motion cleared
- `on_motion_timeout` - Motion event timed out without camera reporting clear
- `on_new_recording` - A new recording completed and it's available. Will broadcast local path over MQTT.
- `on_recording_failed` - Recording failed
- `on_reencoding_ready` - Re-encoding completed
- `on_reencoding_failed` - Re-encoding failed

## WWW Endpoints

- `/doorbell` - Camera webhook endpoint
- `/snap` - Get current snapshot (JPEG)
- `/lastsnap` - Get last saved snapshot (JPEG)
- `/record?secs=N` - Start recording (5-120 seconds)

## NVR

This service also has an NVR-like functionality. Unlike an NVR, the service doesn't record all the time: it will just start recording once the camera reports motion or doorbell-press. This means you will always miss the first few seconds of motion (but will save a lot on energy and storage).

![](README_screenshot2.png)

## Integrations

This service will integrate with ZmwDoorman to:

* Send Telegram notifications when the doorbell is pressed
* Play audio chimes over LAN speakers when the doorbell is pressed
* Send Whatsapp messages when motion is detected

And others (see the readme for ZmwDoorman for details).

