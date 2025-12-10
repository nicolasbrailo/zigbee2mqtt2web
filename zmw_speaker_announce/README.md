# mqtt_speaker_announce

Sonos speaker announcement service with TTS support.

## Behaviour

Plays audio announcements on Sonos speakers. Supports text-to-speech conversion, custom audio assets, and volume control.

## MQTT

**Topic:** `mqtt_speaker_announce`

**Methods (subscribe):**
- `ls` - List available speakers
- `tts` - Text-to-speech (`{msg, lang?, vol?}`)
- `save_asset` - Save audio file to cache (`{local_path}`)
- `play_asset` - Play audio (`{name}` or `{local_path}` or `{public_www}`, `vol?`)

**Announces (publish):**
- `ls_reply` - List of speakers
- `tts_reply` - TTS result with URI
- `save_asset_reply` - Asset save status

## WWW Endpoints

- `/announce_tts?phrase=X&lang=X&vol=N` - Trigger TTS announcement
- `/ls_speakers` - List available Sonos speakers
- `/announcement_history` - Recent announcements
- `/tts/*` - Cached TTS audio files
