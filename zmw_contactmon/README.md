# ZmwContactMon

Contact sensor monitoring with timeout and curfew alerts.
Monitors Zigbee contact sensors (doors, windows). On state change, triggers configured actions (notifications over SMS, announcements on local speaker).

![](README_screenshot.png)

This service will monitor transitions in contact sensors between open (non-normal) and closed (normal). With this service, you can

* Monitor state of contact sensors in a Zigbee network.
* Trigger actions when a sensor changes from open to close, or from close to open.
* Trigger actions when a sensor has been left open for too long (eg if someone forgot a door open).
* Trigger actions when a sensor is open after a curfew time (eg if someone forgets a window open at night).
* Skip alerts: if you have a door-open alert, and you come home late, there's a button to disable chimes that may wake people up.

## Actions

The following actions are supported for each transition (normal/closed, non-normal/open, timeout, curfew):

* Telegram: delivers a message to a Telegram service (which will relay it to a set of contacts).
* Whatsapp: delivers a picture to a Whatsapp service, similar to Telegram.
* tts_announce: will ask a LAN speaker announcement service to broadcast a message over loudspeakers. Google translate will be used as a TTS service. Different languages supported.
* sound asset annoucne: ask a LAN speaker announcement service to broadcast a chime/sound effect, using a local file or a URL accessible to the speakers.


## WWW Endpoints

- `/svc_state` - Current sensor states, history, chime status
- `/skip_chimes` - Temporarily disable chime notifications
- `/skip_chimes_with_timeout/<secs>` - Disable chimes with timeout
- `/enable_chimes` - Re-enable chime notifications
