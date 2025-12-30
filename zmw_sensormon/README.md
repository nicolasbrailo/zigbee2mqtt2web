# ZmwSensors

Sensor data monitoring and history service.

![](README_screenshot.png)

Monitors MQTT sensors (temperature, humidity, power, battery, contact, occupancy, etc.) and stores historical readings in a database. Integrates with Z2M out of the box. Also has an integration with ZmwShelly (see readme for this service). Provides APIs for querying sensor data, and a React component to display badges with readings for a set of sensors.

Sensormon can also create virtual metrics based on real metrics. This is useful, for example, to adjust readings from a sensor to better calibrate it, or to create feels-like metrics based on real temperature/humidity measurements.

## WWW Endpoints

- Sensor history query endpoints (registered via `SensorsHistory`)
- `/z2m/*` - Z2M web service endpoints
