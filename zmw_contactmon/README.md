# mqtt_contact_mon

Contact sensor monitoring with timeout and curfew alerts.
Monitors Zigbee contact sensors (doors, windows). Triggers configured actions (notifications over SMS, announcements on local speaker) on state changes (door open/close), timeouts (door open for too long), or curfew violations (window forgot open at night).

## MQTT

**Announces (publish):**
- `mqtt_contact_mon/$sensor/contact` - Sensor state change event

## WWW Endpoints

- `/svc_state` - Current sensor states, history, chime status
- `/skip_chimes` - Temporarily disable chime notifications
- `/skip_chimes_with_timeout/<secs>` - Disable chimes with timeout
- `/enable_chimes` - Re-enable chime notifications
