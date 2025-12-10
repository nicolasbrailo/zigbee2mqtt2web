# mqtt_heating

Heating system manager controlling a boiler via Zigbee relay.
Controls an on/off relay powering a boiler based on a configurable schedule. Supports user boosts, manual overrides, temperature sensor rules, and Telegram commands (`/tengofrio` for heating boost).

## WWW Endpoints

- `/svc_state` - Current schedule, boiler state, sensor readings
- `/get_cfg_rules` - Configured heating rules
- `/active_schedule` - Current day's schedule
- `/boost=<hours>` - Activate heating boost
- `/off_now` - Turn heating off immediately
- `/slot_toggle=<name>` - Toggle a schedule slot
- `/template_slot_set=<vals>` - Set template slot
- `/template_apply` - Apply template to today
- `/template_reset=<state>` - Reset template schedule
- `/template_schedule` - Get template schedule
