# mqtt_sensor_mon

Sensor data monitoring and history service.

## Behaviour

Monitors Zigbee sensors (temperature, humidity, power, battery, contact, occupancy, etc.) and stores historical readings in a database. Provides APIs for querying sensor data.

## WWW Endpoints

- Sensor history query endpoints (registered via `SensorsHistory`)
- `/z2m/*` - Z2M web service endpoints
