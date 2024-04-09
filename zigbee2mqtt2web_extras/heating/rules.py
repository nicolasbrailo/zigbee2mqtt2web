from dataclasses import dataclass
import logging
log = logging.getLogger(__name__)

# T below this will be assumed to be a reading error
MIN_REASONABLE_T = -5
# T above this will be assumed to be a reading error and ignored
MAX_REASONABLE_T = 45

METRIC_TEMP = 'temperature'

def safe_read_sensor(zmw, sensor):
    try:
        thing = zmw.registry.get_thing(sensor)
    except KeyError as ex:
        log.debug("Sensor %s is not known, ignoring this tick().", sensor)
        return None

    if METRIC_TEMP not in thing.actions:
        log.debug(f"Sensor %s isn't monitoring %s, ignoring this tick()", sensor, METRIC_TEMP)
        return None

    temp = thing.get(METRIC_TEMP)
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


class DefaultOff:
    REASON = "No reason to turn on"
    def __init__(self, zmw, cfg):
        pass
    def apply(self, sched):
        sched.set_now_from_rule(False, DefaultOff.REASON)


class DefaultOn:
    REASON = "Configured always on"
    def __init__(self, zmw, cfg):
        pass
    def apply(self, sched):
        sched.set_now_from_rule(True, DefaultOff.REASON)

class CheckTempsWithinRange:
    """ Failsafe rule: will shut down/turn on if temp sensors are not within a normal range """

    def __init__(self, zmw, cfg):
        self._zmw = zmw
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
            temp = safe_read_sensor(self._zmw, sensor)
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



from datetime import datetime, time

class ScheduledMinTargetTemp:
    @dataclass(frozen=True)
    class SensorTimeSchedule:
        start_time: time
        end_time: time
        days: str
        target_temp: int

        def is_active(self, t):
            if self.start_time <= t.time() <= self.end_time:
                if self.days == 'all':
                    return True
                elif self.days == 'week':
                    return t.weekday() < 5
                elif self.days == 'weekend':
                    return t.weekday() in [5, 6]
                log.error("Unexpected days in schedule: %s", self.days)
                return True
            return False

        @staticmethod
        def guess_days(val):
            supported = ['all', 'week', 'weekend']
            if val in supported:
                return val
            raise ValueError(f"SensorTimeSchedule days '{val}' not supported. Expected: {supported}")

        @staticmethod
        def create_from_json_obj(sensor_name, sched):
            try:
                st = ScheduledMinTargetTemp.SensorTimeSchedule(
                    start_time = datetime.strptime(sched['start'], "%H:%M").time(),
                    end_time = datetime.strptime(sched['end'], "%H:%M").time(),
                    target_temp = float(sched['target_temp']),
                    days = ScheduledMinTargetTemp.SensorTimeSchedule.guess_days(sched['days']))
                if st.target_temp > MAX_REASONABLE_T:
                    raise ValueError(f"Target temperature for sensor %s set to %s, which looks too high for a temperature (max < %s)", sensor_name, st.target_temp, MAX_REASONABLE_T)
                return st
            except (ValueError, TypeError, KeyError):
                log.error("Failed to parse SensorTimeSchedule for sensor %s, ignoring", sensor_name, exc_info=True)
                return None

        @staticmethod
        def create_from_json_obj_arr(sensor_name, scheds):
            time_scheds = []
            for sched in scheds:
                s = ScheduledMinTargetTemp.SensorTimeSchedule.create_from_json_obj(sensor_name, sched)
                if s is not None:
                    time_scheds.append(s)
            return time_scheds

    def __init__(self, zmw, rule, clock=None):
        self._clock = clock
        if self._clock is None:
            self._clock = datetime
        self._zmw = zmw
        self.sensor_schedules = {}
        for sensor in rule['sensors']:
            sensor_name = sensor['name']
            time_scheds = ScheduledMinTargetTemp.SensorTimeSchedule.create_from_json_obj_arr(sensor_name, sensor['schedule'])

            if sensor_name in self.sensor_schedules:
                raise ValueError(f"Found duplicated sensor to monitor: ScheduledMinTargetTemp was asked to monitor sensor {sensor_name} twice")

            if len(time_scheds) != 0:
                self.sensor_schedules[sensor_name] = time_scheds
            else:
                raise ValueError(f"ScheduledMinTargetTemp was asked to monitor sensor {sensor_name}, but its schedule is empty")

    def apply(self, todaysched):
        for sensor_name, scheds in self.sensor_schedules.items():
            for sched in scheds:
                if sched.is_active(self._clock.now()):
                    temp = safe_read_sensor(self._zmw, sensor_name)
                    if temp is not None and temp < sched.target_temp:
                        reason = f"Sensor {sensor_name} reports {temp}C, target is {sched.target_temp}C between {sched.start_time} and {sched.end_time}"
                        todaysched.set_now_from_rule(True, reason)


def create_rules_from_config(zmw, rules_cfg):
    known_rules = [DefaultOff, CheckTempsWithinRange, ScheduledMinTargetTemp]

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
            except Exception as ex:
                raise ValueError(f"Failed to setup heating schedule rule {rule['name']}") from ex
        else:
            raise ValueError(f"Failed to setup heating schedule, requested unknown rule {rule['name']}")
    return rules

