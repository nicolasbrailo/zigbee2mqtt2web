"""Virtual metrics that compute derived values from real sensor data."""

from zzmw_lib.logs import build_logger

log = build_logger("VirtualMetrics")


def _compute_heat_index(temp_c, humidity):
    """Compute heat index using Rothfusz regression equation.

    Only valid for temp >= 27°C and humidity >= 40%.
    Returns temperature in Celsius.
    """
    # Convert to Fahrenheit for the standard formula
    temp_f = temp_c * 9 / 5 + 32

    hi = (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * humidity
        - 0.22475541 * temp_f * humidity
        - 0.00683783 * temp_f ** 2
        - 0.05481717 * humidity ** 2
        + 0.00122874 * temp_f ** 2 * humidity
        + 0.00085282 * temp_f * humidity ** 2
        - 0.00000199 * temp_f ** 2 * humidity ** 2
    )

    # Convert back to Celsius
    return (hi - 32) * 5 / 9


def _compute_humid_cold_adjustment(temp_c, humidity):
    """Adjust perceived temperature for cold humid conditions.

    High humidity in cold conditions makes it feel colder due to
    increased thermal conductivity of moist air.
    """
    # Subtract 0.1°C per percentage point of humidity above 45%
    adjustment = -0.1 * (humidity - 45)
    return temp_c + adjustment


def _compute_feels_like(values):
    """Compute feels-like temperature using combined approach.

    - Hot and humid (T >= 27°C, RH >= 40%): Use heat index
    - Cold and humid (T < 20°C, RH > 45%): Use humid-cold adjustment
    - Otherwise: Return actual temperature
    """
    temp = values['temperature']
    humidity = values['humidity']

    if temp >= 27 and humidity >= 40:
        return _compute_heat_index(temp, humidity)
    elif temp < 20 and humidity > 45:
        return _compute_humid_cold_adjustment(temp, humidity)
    else:
        return temp


# Virtual metrics configuration
# Each entry defines: required source metrics and compute function
VIRTUAL_METRICS = {
    'feels_like_temp': {
        'requires': ['temperature', 'humidity'],
        'compute': _compute_feels_like,
    },
}


def get_virtual_metrics(sensor_metrics):
    """Return list of virtual metric names that can be added to a sensor.

    Args:
        sensor_metrics: List of metrics the sensor has

    Returns:
        List of virtual metric names that can be computed from those metrics
    """
    virtual = []
    sensor_metrics_set = set(sensor_metrics)

    for metric_name, config in VIRTUAL_METRICS.items():
        required = set(config['requires'])
        if required.issubset(sensor_metrics_set):
            virtual.append(metric_name)

    return virtual


def compute_virtual_metrics(values):
    """Compute all applicable virtual metrics from sensor values.

    Args:
        values: Dict of {metric: value} from the sensor

    Returns:
        Dict of {virtual_metric: computed_value}
    """
    result = {}

    for metric_name, config in VIRTUAL_METRICS.items():
        required = config['requires']
        # Check if all required metrics are present and not None
        if all(values.get(r) is not None for r in required):
            try:
                result[metric_name] = config['compute'](values)
            except Exception as e:
                log.error("Error computing virtual metric '%s': %s", metric_name, e)

    return result
