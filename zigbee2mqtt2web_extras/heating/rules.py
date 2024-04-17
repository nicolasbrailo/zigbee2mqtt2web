from dataclasses import dataclass
import logging
log = logging.getLogger(__name__)

from .schedule import AllowOn

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
        log.error("Apply rule DefaultOff...")
        sched.set_now_from_rule(False, DefaultOff.REASON)


class DefaultOn:
    REASON = "Configured always on"
    def __init__(self, zmw, cfg):
        pass
    def apply(self, sched):
        log.error("Apply rule DefaultOn...")
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
        log.error("Check rule CheckTempsWithinRange...")
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
            log.info("Request heating off: %s", reason)
            sched.set_now_from_rule(False, reason)
        elif len(less_than_min) > 0:
            reason = f"Sensor below {self.min_temp}C: " + ', '.join([f"{n} ({t})" for n,t in less_than_min])
            log.info("Request heating on: %s", reason)
            sched.set_now_from_rule(True, reason)



from datetime import datetime, time

class ScheduledMinTargetTemp:
    @dataclass(frozen=True)
    class SensorTimeSchedule:
        sensor_name: str
        start_time: time
        end_time: time
        days: str
        target_min_temp: int
        target_max_temp: int

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
                    sensor_name = sensor_name,
                    start_time = datetime.strptime(sched['start'], "%H:%M").time(),
                    end_time = datetime.strptime(sched['end'], "%H:%M").time(),
                    target_min_temp = float(sched['target_min_temp']),
                    target_max_temp = float(sched['target_max_temp']),
                    days = ScheduledMinTargetTemp.SensorTimeSchedule.guess_days(sched['days']))
                if st.target_max_temp > MAX_REASONABLE_T or st.target_max_temp < MIN_REASONABLE_T:
                    raise ValueError(f"target_max_temp max temperature for sensor %s set to %s, which looks out or range for temperature (%s < t < %s)", sensor_name, st.target_max_temp, MIN_REASONABLE_T, MAX_REASONABLE_T)
                if st.target_min_temp > MAX_REASONABLE_T or st.target_min_temp < MIN_REASONABLE_T:
                    raise ValueError(f"target_min_temp for sensor %s set to %s, which looks out or range for temperature (%s < t < %s)", sensor_name, st.target_min_temp, MIN_REASONABLE_T, MAX_REASONABLE_T)
                if st.target_min_temp > st.target_max_temp:
                    raise ValueError(f"target_min_temp is higher than max temp for sensor %s (%s < %s)", sensor_name, st.target_min_temp, st.target_max_temp)
                return st
            except (ValueError, TypeError, KeyError):
                log.error("Failed to parse SensorTimeSchedule for sensor %s", sensor_name, exc_info=True)
                raise

        @staticmethod
        def create_from_json_obj_arr(sensor_name, scheds):
            return [ScheduledMinTargetTemp.SensorTimeSchedule.create_from_json_obj(sensor_name, sched) for sched in scheds]

    def __init__(self, zmw, rule, clock=None):
        self._clock = clock
        if self._clock is None:
            self._clock = datetime
        self._zmw = zmw
        self._active_rule = None
        self.sensor_schedules = {}
        for sensor in rule['sensors']:
            sensor_name = sensor['name']
            if sensor_name in self.sensor_schedules:
                raise ValueError(f"Found duplicated sensor to monitor: ScheduledMinTargetTemp was asked to monitor sensor {sensor_name} twice")

            time_scheds = ScheduledMinTargetTemp.SensorTimeSchedule.create_from_json_obj_arr(sensor_name, sensor['schedule'])
            if len(time_scheds) == 0:
                raise ValueError(f"ScheduledMinTargetTemp was asked to monitor sensor {sensor_name}, but its schedule is empty")

            self.sensor_schedules[sensor_name] = time_scheds

    def apply(self, todaysched):
        log.error("Check rule ScheduledMinTargetTemp...")
        if todaysched.get_now_slot().allow_on != AllowOn.Rule:
            log.error("Now-schedule is not rule based, but we're applying ScheduledMinTargetTemp-rule")
            return

        # There was no active and applicable rule, check if a new rule applies
        for sensor_name, scheds in self.sensor_schedules.items():
            for sched in scheds:
                if not sched.is_active(self._clock.now()):
                    continue

                temp = safe_read_sensor(self._zmw, sensor_name)
                already_active = sched == self._active_rule

                if temp is None and not already_active:
                    # This sensor is not responding, ignore its rules
                    continue
                elif temp is None and already_active:
                    reason = f"Sensor {sensor_name} stopped responding with an active rule. " + \
                             f"Heating will remain on until rule expires at {sched.end_time}, or sensor updtes."
                    log.error(reason)
                    todaysched.set_now_from_rule(True, reason)
                    return

                if temp < sched.target_min_temp or (already_active and temp < sched.target_max_temp):
                    reason = f"Sensor {sensor_name} reports {temp}C, target is {sched.target_max_temp}C between {sched.start_time} and {sched.end_time}"
                    log.info("Request heating on by ScheduledMinTargetTemp: %s", reason)
                    todaysched.set_now_from_rule(True, reason)
                    self._active_rule = sched
                    return

        # If we're here, no rules applied. Check if we had any active rules, and set the off reason to "rule X no longer apply"
        if self._active_rule is not None:
            rule = self._active_rule
            self._active_rule = None
            if todaysched.get_now_slot().request_on:
                # Some other rule is active now, don't update the reason for request off
                return
            if rule.is_active(self._clock.now()):
                reason = f"Sensor {rule.sensor_name} reports above target temperature of {rule.target_max_temp}C"
            else:
                reason = f"Schedule for {rule.sensor_name} finished at {rule.end_time} and is no longer active"
            log.info("ScheduledMinTargetTemp rule stopped applying: %s", reason)
            todaysched.set_now_from_rule(False, reason)


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
                log.info("Heating will use rule %s", rule['name'])
                rules.append(cls(zmw, rule))
            except Exception as ex:
                raise ValueError(f"Failed to setup heating schedule rule {rule['name']}") from ex
        else:
            raise ValueError(f"Failed to setup heating schedule, requested unknown rule {rule['name']}")
    return rules

