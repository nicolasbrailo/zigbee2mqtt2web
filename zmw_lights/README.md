# mqtt_lights

Zigbee2MQTT light discovery and control service.

Connects to Zigbee2MQTT, discovers all light devices on the network, and exposes them via a web API. Applies light helper patches for extended functionality.

## WWW Endpoints

- `/get_lights` - Returns JSON array of all discovered lights with their state
- `/z2m/*` - Z2M web service endpoints (device listing, control)
