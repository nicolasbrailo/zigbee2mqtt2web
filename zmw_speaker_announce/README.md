# ZmwSpeakerAnnounce

Sonos speaker announcement service with TTS and user recording support. Can be controlled over MQTT.

![](README_screenshot.png)

* TTS mode: enter a text on the UI of this service and it will be converted to an audio asset, then played over all known speakers in your network. Different languages supported for TTS.
* User record: use your device's microphone to record a message, then broadcast it over your speakers. Note this requires running the server in HTTPS mode, as phones won't enable microphone access for web apps without SSL. Since the server uses a self-signed certificate, a security warning will be displayed when the UI runs in HTTPS mode.

## MQTT

**Topic:** `mqtt_speaker_announce`

**Methods (subscribe):**
- `ls` - List available speakers
- `tts` - Text-to-speech
- `play_asset` - Play audio (`{name}` or `{local_path}` or `{public_www}`, `vol?`)

## WWW Endpoints

- `/announce_tts?phrase=X&lang=X&vol=N` - Trigger TTS announcement
- `/ls_speakers` - List available Sonos speakers
- `/announcement_history` - Recent announcements
- `/tts/*` - Cached TTS audio files
