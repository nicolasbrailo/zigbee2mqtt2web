import logging
log = logging.getLogger(__name__)

# T below this will be assumed to be a reading error
MIN_REASONABLE_T = -5
# T above this will be assumed to be a reading error and ignored
MAX_REASONABLE_T = 45

def safe_read_sensor(zmw, sensor, metric):
    try:
        thing = zmw.registry.get_thing(sensor)
    except KeyError as ex:
        log.debug("Sensor %s is not known, ignoring this tick().", sensor)
        return None

    if metric not in thing.actions:
        log.debug(f"Sensor %s isn't monitoring %s, ignoring this tick()", sensor, METRIC)
        return None

    temp = thing.get(metric)
    try:
        tempF = float(temp)
    except (ValueError, TypeError):
        log.debug("Sensor %s returned temp=%s, which isn't a number. Ignoring.", sensor, temp)
        return None

    temp = float(temp)
    if temp > MAX_REASONABLE_T:
        log.debug("Sensor %s returned temp=%s, which is probably a reading error (expected less than %s). Ignoring.", sensor, temp, MAX_REASONABLE_T)
        return None
    if temp < MIN_REASONABLE_T:
        log.debug("Sensor %s returned temp=%s, which is probably a reading error (expected less than %s). Ignoring.", sensor, temp, MIN_REASONABLE_T)
        return None

    return temp

class CheckTempsWithinRange:
    """ Failsafe rule: will shut down/turn on if temp sensors are not within a normal range """

    def __init__(self, zmw, cfg):
        self._zmw = zmw
        self.METRIC = 'temperature'
        self.MIN_T_DELTA = 10 # Min diff between user set max and user set min
        self.min_temp = cfg['min_temp']
        self.max_temp = cfg['max_temp']
        self.sensors_to_monitor = cfg['sensors']

        if type(self.min_temp) != type(42) or type(self.max_temp) != type(42):
            raise ValueError("Config error: min and max temp must be ints")

        if self.min_temp > self.max_temp:
            raise ValueError(f"Requested max temp ({self.max_temp}) is less than min temp ({self.min_temp})")

        if self.max_temp - self.min_temp < self.MIN_T_DELTA:
            raise ValueError(f"Requested difference between max and min temp is less than {self.MIN_T_DELTA} ({self.max_temp} and {self.min_temp})")

    def apply(self, sched):
        more_than_max = []
        less_than_min = []
        for sensor in self.sensors_to_monitor:
            temp = safe_read_sensor(self._zmw, sensor, self.METRIC)
            print(sensor, '==', temp)
            if temp is None:
                continue
            if temp > self.max_temp:
                more_than_max.append((sensor, temp))
            if temp < self.min_temp:
                less_than_min.append((sensor, temp))

        if len(more_than_max) > 0 and len(less_than_min) > 0:
            log.error("Found sensors above temp limit, and also sensors below temp limit. Skipping this rule, heating state can't be set.")
            log.error(f"Sensors above temp limit (%s): %s", self.max_temp, ', '.join([f"{n} ({t})" for n,t in more_than_max]))
            log.error(f"Sensors below temp limit (%s): %s", self.min_temp, ', '.join([f"{n} ({t})" for n,t in less_than_min]))
        elif len(more_than_max) > 0:
            reason = f"Sensor above {self.max_temp}C: " + ', '.join([f"{n} ({t})" for n,t in more_than_max])
            sched.set_now_from_rule(False, reason)
        elif len(less_than_min) > 0:
            reason = f"Sensor below {self.min_temp}C: " + ', '.join([f"{n} ({t})" for n,t in less_than_min])
            sched.set_now_from_rule(True, reason)

def create_rules_from_config(zmw, rules_cfg):
    known_rules = [CheckTempsWithinRange]

    def _get_rule_class(name):
        for cls in known_rules:
            if cls.__name__ == name:
                return cls
        return None

    rules = []
    for rule in rules_cfg:
        cls = _get_rule_class(rule['name'])
        if cls:
            try:
                rules.append(cls(zmw, rule))
            except:
                log.warning("Ignoring rule %s, failed to setup", rule['name'], exc_info=True)
        else:
            log.warning("Ignoring user-requested unknown heating config rule %s", rule['name'])
    return rules

