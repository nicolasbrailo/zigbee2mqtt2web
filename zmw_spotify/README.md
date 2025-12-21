# ZmwSpotify

Spotify playback control service. Exposes Spotify control over MQTT.

Manages OAuth authentication, provides playback controls (play/pause, volume, track navigation), and exposes current playing state.

## MQTT

**Topic:** `mqtt_spotify`

**Methods (subscribe):**
- `publish_state` - Request current player state
- `stop` - Stop playback
- `toggle_play` - Toggle play/pause
- `relative_jump_to_track` - Skip tracks (`{value: N}`)
- `set_volume` - Set volume (`{value: 0-100}`)

**Announces (publish):**
- `state` - Current player state (is_playing, volume, media_info)

