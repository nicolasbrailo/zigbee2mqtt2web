import json
import unittest

from rules import *
from schedule import AllowOn
from schedule_builder import ScheduleBuilder
from schedule_test import FakeClock, StateChangeSaver, ignore_state_changes
from schedule_builder_test import get_schedule_all_slots

CFG_TEMP_IN_RANGE = """[
    {"name": "CheckTempsWithinRange", "min_temp": 5, "max_temp": 15, "sensors": ["tempSensor1", "tempSensor2", "tempSensor3"], "metric": "temperature"}
]"""

SCHED_MIN_TEMP_CFG = """[{{
    "name": "ScheduledMinTargetTemp",
    "sensor": "sensorName",
    "metric": "temperature",
    {}
}}]"""

class FakeTempSensor:
    def __init__(self, temp):
        self.temp = temp
        self.actions = ['temperature']
    def get(self, _):
        return self.temp

class FakeRegistry:
    def __init__(self):
        self.map_of_things = {}
        self.map_of_things['tempSensor1'] = FakeTempSensor(10)
        self.map_of_things['tempSensor2'] = FakeTempSensor(10)
        self.map_of_things['tempSensor3'] = FakeTempSensor(10)

    def get_thing(self, name):
        return self.map_of_things[name]

class FakeZmw:
    def __init__(self):
        self.registry = FakeRegistry()
    def get_thing(self, name):
        return self.registry.get_thing(name)


class RulesTest(unittest.TestCase):
    def test_create_empty(self):
        rules = create_rules_from_config([])
        self.assertEqual(len(rules), 0)

    def test_ignore_unknown(self):
        self.assertRaises(ValueError, create_rules_from_config, json.loads('[{"name":"RuleThatDoesntExist"}]'))

    def test_rules_applied_in_order(self):
        state_change_saver1 = StateChangeSaver()
        sut1 = ScheduleBuilder(state_change_saver1.save_state_changes, None, [DefaultOff({}), DefaultOn({})], None)
        sut1.from_json(get_schedule_all_slots(AllowOn.RULE))

        state_change_saver2 = StateChangeSaver()
        sut2 = ScheduleBuilder(state_change_saver2.save_state_changes, None, [DefaultOn({}), DefaultOff({})], None)
        sut2.from_json(get_schedule_all_slots(AllowOn.RULE))

        sut1.tick()
        sut2.tick()

        self.assertTrue(state_change_saver1.saved_new.reason, DefaultOff.REASON)
        self.assertTrue(state_change_saver2.saved_new.reason, DefaultOn.REASON)


    def test_create_CheckTempsWithinRange(self):
        zmw = FakeZmw()
        rules = create_rules_from_config(json.loads(CFG_TEMP_IN_RANGE))
        for rule in rules:
            rule.set_z2m(zmw)
        self.assertEqual(len(rules), 1)
        self.assertEqual(type(rules[0]), CheckTempsWithinRange)
        self.assertEqual(rules[0].min_temp, 5)
        self.assertTrue('tempSensor1' in rules[0].sensors_to_monitor)
        self.assertTrue('tempSensor2' in rules[0].sensors_to_monitor)
        self.assertTrue('tempSensor3' in rules[0].sensors_to_monitor)

    def test_failure_setup_CheckTempsWithinRange(self):
        cfg = json.loads(CFG_TEMP_IN_RANGE)
        del cfg[0]['min_temp']
        self.assertRaises(ValueError, create_rules_from_config, cfg)

        cfg[0]['min_temp'] = 42
        cfg[0]['max_temp'] = 20
        self.assertRaises(ValueError, create_rules_from_config, cfg)

        cfg[0]['min_temp'] = 20
        cfg[0]['max_temp'] = 21
        self.assertRaises(ValueError, create_rules_from_config, cfg)

        cfg[0]['sensors'] = ['tempSensor1']
        cfg[0]['min_temp'] = []
        self.assertRaises(ValueError, create_rules_from_config, cfg)

        # Should build
        cfg[0]['min_temp'] = 0
        rules = create_rules_from_config(cfg)
        self.assertEqual(len(rules), 1)

    def test_apply_CheckTempsWithinRange(self):
        state_change_saver = StateChangeSaver()
        zmw = FakeZmw()
        rules = create_rules_from_config(json.loads(CFG_TEMP_IN_RANGE))
        for rule in rules:
            rule.set_z2m(zmw)
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, rules)

        sut.from_json(get_schedule_all_slots(AllowOn.RULE))
        zmw.registry.get_thing('tempSensor2').temp = -4
        sut.tick()

        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        self.assertTrue('tempSensor2' in state_change_saver.saved_new.reason)
        self.assertTrue('-4' in state_change_saver.saved_new.reason)

        # While sensors are in nominal range, state shouldn't change (neither on nor off)
        zmw.registry.get_thing('tempSensor2').temp = 10
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        zmw.registry.get_thing('tempSensor2').temp = 31
        zmw.registry.get_thing('tempSensor3').temp = 32
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)
        self.assertTrue('tempSensor2' in state_change_saver.saved_new.reason)
        self.assertTrue('tempSensor3' in state_change_saver.saved_new.reason)
        self.assertTrue('31' in state_change_saver.saved_new.reason)
        self.assertTrue('32' in state_change_saver.saved_new.reason)

        zmw.registry.get_thing('tempSensor2').temp = 10
        zmw.registry.get_thing('tempSensor3').temp = 15
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Floats are OK
        zmw.registry.get_thing('tempSensor1').temp = 10
        zmw.registry.get_thing('tempSensor2').temp = 10
        zmw.registry.get_thing('tempSensor3').temp = -2.123
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        zmw.registry.get_thing('tempSensor3').temp = 42.123
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)
        zmw.registry.get_thing('tempSensor3').temp = "-2.123"
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        zmw.registry.get_thing('tempSensor3').temp = "42.123"
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)


    def test_sensor_error_CheckTempsWithinRange(self):
        state_change_saver = StateChangeSaver()
        zmw = FakeZmw()
        rules = create_rules_from_config(json.loads(CFG_TEMP_IN_RANGE))
        for rule in rules:
            rule.set_z2m(zmw)
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, rules)
        sut.from_json(get_schedule_all_slots(AllowOn.RULE))
        zmw.registry.get_thing('tempSensor1').temp = -4
        zmw.registry.get_thing('tempSensor2').temp = -4
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        # Ignore absurdely high temp readings
        zmw.registry.get_thing('tempSensor1').temp = 100
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        # Ignore absurdely low temp readings
        zmw.registry.get_thing('tempSensor1').temp = 30
        zmw.registry.get_thing('tempSensor2').temp = 30
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)
        zmw.registry.get_thing('tempSensor2').temp = -30
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Ignore NaNs
        zmw.registry.get_thing('tempSensor1').temp = -1
        zmw.registry.get_thing('tempSensor2').temp = None
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        # Ignore cycles with sensors both below min and above max
        zmw.registry.get_thing('tempSensor1').temp = -1
        zmw.registry.get_thing('tempSensor2').temp = 30
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        # Ignore cycles with sensors both below min and above max
        zmw.registry.get_thing('tempSensor1').temp = 30
        zmw.registry.get_thing('tempSensor2').temp = 30
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)
        zmw.registry.get_thing('tempSensor1').temp = -1
        zmw.registry.get_thing('tempSensor2').temp = 30
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)

    def test_create_ScheduledMinTargetTemp(self):
        cfg = """[{"name": "ScheduledMinTargetTemp", "sensor": "testSensor", "metric": "temperature",
                   "start": "10:00", "end": "11:00", "target_max_temp": 25, "target_min_temp": 20, "days": "all"}]"""
        rules = create_rules_from_config(json.loads(cfg))
        self.assertEqual(len(rules), 1)
        self.assertEqual(type(rules[0]), ScheduledMinTargetTemp)
        self.assertEqual(rules[0].sensor_name, "testSensor")

    def test_fails_create_ScheduledMinTargetTemp(self):
        # Missing sensor key
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": 25, "target_min_temp": 20, "days": "all"}]"""))

        # Absurd temperature fails
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": -40, "target_min_temp": 23, "days": "all"}]"""))
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": 23, "target_min_temp": -40, "days": "all"}]"""))
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": 123, "target_min_temp": 23, "days": "all"}]"""))
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": 23, "target_min_temp": 123, "days": "all"}]"""))
        # min > max
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": 20, "target_min_temp": 25, "days": "all"}]"""))

        # Check missing keys
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "Xstart": "10:00", "end": "11:00", "target_max_temp": 25, "target_min_temp": 20, "days": "all"}]"""))
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "10:00", "Xend": "11:00", "target_max_temp": 25, "target_min_temp": 20, "days": "all"}]"""))
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "10:00", "end": "11:00", "Xtarget_max_temp": 25, "target_min_temp": 20, "days": "all"}]"""))
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": 25, "target_min_temp": 20, "Xdays": "all"}]"""))

        # Fail time format
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "99:00", "end": "11:00", "target_max_temp": 25, "target_min_temp": 20, "days": "all"}]"""))
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": ":00", "end": "11:00", "target_max_temp": 25, "target_min_temp": 20, "days": "all"}]"""))
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "1212", "end": "11:00", "target_max_temp": 25, "target_min_temp": 20, "days": "all"}]"""))
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "12:12", "end": "1100", "target_max_temp": 25, "target_min_temp": 20, "days": "all"}]"""))
        self.assertRaises(ValueError, create_rules_from_config, json.loads(
            """[{"name": "ScheduledMinTargetTemp", "sensor": "S1", "metric": "temperature", "start": "12:12", "end": "11:00", "target_max_temp": 25, "target_min_temp": 20, "days": "xX"}]"""))

        # Valid config should work
        rules = create_rules_from_config(json.loads(SCHED_MIN_TEMP_CFG.format(
            """"start": "10:00", "end": "11:00", "target_max_temp": 25, "target_min_temp": 20, "days": "all" """)))
        self.assertEqual(rules[0].sensor_name, "sensorName")

    def test_apply_ScheduledMinTargetTemp(self):
        SCHED1 = {"sensor": "tempSensor1", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": 20, "target_min_temp": 20, "days": "all"}
        SCHED2 = {"sensor": "tempSensor1", "metric": "temperature", "start": "11:00", "end": "11:30", "target_max_temp": 25, "target_min_temp": 25, "days": "all"}

        clock = FakeClock(9, 0)
        zmw = FakeZmw()
        rules = [DefaultOff({}), ScheduledMinTargetTemp(SCHED1, clock), ScheduledMinTargetTemp(SCHED2, clock)]
        for rule in rules:
            rule.set_z2m(zmw)

        state_change_saver = StateChangeSaver()
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, rules, clock)
        sut.from_json(get_schedule_all_slots(AllowOn.RULE))

        sut.tick()
        start_count = state_change_saver.count
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        clock.set_t(9, 55)
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Temp start high, shouldn't trigger rule
        clock.set_t(10, 0)
        zmw.registry.get_thing('tempSensor1').temp = 30
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Temp dips, should trigger rule
        clock.set_t(10, 1)
        zmw.registry.get_thing('tempSensor1').temp = 10
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count + 1)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        self.assertTrue('tempSensor1' in state_change_saver.saved_new.reason)
        self.assertTrue('10' in state_change_saver.saved_new.reason, f'Expected reason to contain sensor temperature of 10. Reason: {state_change_saver.saved_new.reason}')
        self.assertTrue('20' in state_change_saver.saved_new.reason, f'Expected reason to contain target temperature of 20. Reason: {state_change_saver.saved_new.reason}')

        # Temp restores, should switch off
        clock.set_t(10, 0)
        zmw.registry.get_thing('tempSensor1').temp = 20
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count + 2)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, False)
        self.assertTrue(state_change_saver.saved_new.reason, DefaultOff.REASON)

        # Advance clock, rule should still apply
        clock.set_t(10, 55)
        zmw.registry.get_thing('tempSensor1').temp = 20
        sut.tick()
        start_count = state_change_saver.count  # Reset count, this may or may not notify
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Advance clock, rule should still apply and catch temp dip
        clock.set_t(10, 55)
        zmw.registry.get_thing('tempSensor1').temp = 19
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count + 1)
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        # Temp recovers
        clock.set_t(10, 55)
        zmw.registry.get_thing('tempSensor1').temp = 21
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count + 2)
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Advance time, new slot should demand higher temp
        clock.set_t(11, 5)
        zmw.registry.get_thing('tempSensor1').temp = 21
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count + 3)
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        # Temp recovers again
        clock.set_t(11, 15)
        zmw.registry.get_thing('tempSensor1').temp = 26
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count + 4)
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # No rule applies anymore
        clock.set_t(12, 0)
        zmw.registry.get_thing('tempSensor1').temp = 10
        sut.tick()
        start_count = state_change_saver.count  # Reset count, this may or may not notify
        self.assertEqual(state_change_saver.saved_new.request_on, False)

    def test_apply_multiple_sensors_same_time_ScheduledMinTargetTemp(self):
        SCHED1 = {"sensor": "tempSensor1", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": 20, "target_min_temp": 20, "days": "all"}
        SCHED2 = {"sensor": "tempSensor2", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": 20, "target_min_temp": 20, "days": "all"}

        clock = FakeClock(8, 0)
        zmw = FakeZmw()
        rules = [DefaultOff({}), ScheduledMinTargetTemp(SCHED1, clock), ScheduledMinTargetTemp(SCHED2, clock)]
        for rule in rules:
            rule.set_z2m(zmw)

        state_change_saver = StateChangeSaver()
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, rules, clock)
        sut.from_json(get_schedule_all_slots(AllowOn.RULE))

        sut.tick()
        start_count = state_change_saver.count
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Temp start high, shouldn't trigger rule
        zmw.registry.get_thing('tempSensor1').temp = 30
        zmw.registry.get_thing('tempSensor2').temp = 30
        clock.set_t(10, 15)
        sut.tick()
        start_count = state_change_saver.count  # Reset count, this may or may not notify
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Temp1 dips, should fire
        zmw.registry.get_thing('tempSensor1').temp = 10
        zmw.registry.get_thing('tempSensor2').temp = 30
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        self.assertTrue('tempSensor1' in state_change_saver.saved_new.reason)
        self.assertEqual(state_change_saver.count, start_count+1)

        # Temp2 dips, shouldn't change state (but may notify, as the order of the sensor isn't guaranteed)
        zmw.registry.get_thing('tempSensor1').temp = 10
        zmw.registry.get_thing('tempSensor2').temp = 10
        sut.tick()
        start_count = state_change_saver.count # Reset count in case it notified
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        self.assertTrue('tempSensor1' in state_change_saver.saved_new.reason or 'tempSensor2' in state_change_saver.saved_new.reason)

        # Temp1 recovers, shouldn't change state (but may notify, as the order of the sensor isn't guaranteed)
        zmw.registry.get_thing('tempSensor1').temp = 30
        zmw.registry.get_thing('tempSensor2').temp = 10
        sut.tick()
        start_count = state_change_saver.count # Reset count in case it notified
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        self.assertTrue('tempSensor2' in state_change_saver.saved_new.reason)

        # Both temps recover, should be off
        zmw.registry.get_thing('tempSensor1').temp = 30
        zmw.registry.get_thing('tempSensor2').temp = 30
        sut.tick()
        start_count = state_change_saver.count # Reset count in case it notified
        self.assertEqual(state_change_saver.saved_new.request_on, False)

    def test_apply_multiple_sensors_diff_time_ScheduledMinTargetTemp(self):
        SCHED1 = {"sensor": "tempSensor1", "metric": "temperature", "start": "10:00", "end": "11:00", "target_max_temp": 20, "target_min_temp": 20, "days": "all"}
        SCHED2 = {"sensor": "tempSensor2", "metric": "temperature", "start": "11:00", "end": "12:00", "target_max_temp": 20, "target_min_temp": 20, "days": "all"}

        clock = FakeClock(10, 0)
        zmw = FakeZmw()
        rules = [DefaultOff({}), ScheduledMinTargetTemp(SCHED1, clock), ScheduledMinTargetTemp(SCHED2, clock)]
        for rule in rules:
            rule.set_z2m(zmw)

        state_change_saver = StateChangeSaver()
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, rules, clock)
        sut.from_json(get_schedule_all_slots(AllowOn.RULE))

        # Only monitor t1 in this slot
        zmw.registry.get_thing('tempSensor1').temp = 30
        zmw.registry.get_thing('tempSensor2').temp = 10
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        zmw.registry.get_thing('tempSensor1').temp = 10
        zmw.registry.get_thing('tempSensor2').temp = 10
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        zmw.registry.get_thing('tempSensor1').temp = 30
        zmw.registry.get_thing('tempSensor2').temp = 10
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Change sensor
        clock.set_t(11, 0)
        zmw.registry.get_thing('tempSensor1').temp = 30
        zmw.registry.get_thing('tempSensor2').temp = 10
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        clock.set_t(11, 0)
        zmw.registry.get_thing('tempSensor1').temp = 10
        zmw.registry.get_thing('tempSensor2').temp = 30
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)


    def test_rule_deactive_has_reason_ScheduledMinTargetTemp(self):
        SCHED1 = {"sensor": "tempSensor1", "metric": "temperature", "target_max_temp": 21, "target_min_temp": 21, "start": "06:00", "end": "07:30", "days": "all"}
        SCHED2 = {"sensor": "tempSensor2", "metric": "temperature", "target_max_temp": 30, "target_min_temp": 30, "start": "22:22", "end": "22:22", "days": "all"}

        clock = FakeClock(6, 15)
        zmw = FakeZmw()
        rules = [DefaultOff({}), ScheduledMinTargetTemp(SCHED1, clock), ScheduledMinTargetTemp(SCHED2, clock)]
        for rule in rules:
            rule.set_z2m(zmw)

        state_change_saver = StateChangeSaver()
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, rules, clock)
        sut.from_json(get_schedule_all_slots(AllowOn.RULE))

        # Only monitor t1 in this slot
        zmw.registry.get_thing('tempSensor1').temp = 19
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        zmw.registry.get_thing('tempSensor1').temp = 21
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)
        self.assertTrue('tempSensor1' in state_change_saver.saved_new.reason and 'above target' in state_change_saver.saved_new.reason,
                        f"Failed message: {state_change_saver.saved_new.reason}")

    def test_rule_ScheduledMinTargetTemp_ignore_non_responding_sensors(self):
        SCHED = {"sensor": "tempSensor1", "metric": "temperature", "target_max_temp": 25, "target_min_temp": 20, "start": "06:00", "end": "07:30", "days": "all"}

        clock = FakeClock(6, 15)
        zmw = FakeZmw()
        rules = [DefaultOff({}), ScheduledMinTargetTemp(SCHED, clock)]
        for rule in rules:
            rule.set_z2m(zmw)

        state_change_saver = StateChangeSaver()
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, rules, clock)
        sut.from_json(get_schedule_all_slots(AllowOn.RULE))

        # "Broken" sensor, rule shouldn't trigger
        zmw.registry.get_thing('tempSensor1').temp = None
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Rule triggers
        zmw.registry.get_thing('tempSensor1').temp = 10
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        self.assertTrue('tempSensor1' in state_change_saver.saved_new.reason, f"Failed message: {state_change_saver.saved_new.reason}")

        # Sensor breaks, rule shouldn't change state
        zmw.registry.get_thing('tempSensor1').temp = None
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        self.assertTrue('tempSensor1' in state_change_saver.saved_new.reason, f"Failed message: {state_change_saver.saved_new.reason}")

    def test_rule_ScheduledMinTargetTemp_hysteresis(self):
        SCHED = {"sensor": "tempSensor1", "metric": "temperature", "target_max_temp": 25, "target_min_temp": 20, "start": "06:00", "end": "07:30", "days": "all"}

        clock = FakeClock(6, 15)
        zmw = FakeZmw()
        rules = [DefaultOff({}), ScheduledMinTargetTemp(SCHED, clock)]
        for rule in rules:
            rule.set_z2m(zmw)

        state_change_saver = StateChangeSaver()
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, rules, clock)
        sut.from_json(get_schedule_all_slots(AllowOn.RULE))

        # Start with high temp, should be off
        zmw.registry.get_thing('tempSensor1').temp = 25
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Temp dips below max target, but not below min. Should stay off.
        zmw.registry.get_thing('tempSensor1').temp = 22
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Temp dips below min target, turn on
        zmw.registry.get_thing('tempSensor1').temp = 19
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        # Temp above min, but below target
        zmw.registry.get_thing('tempSensor1').temp = 22
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)

        # Temp recovers
        zmw.registry.get_thing('tempSensor1').temp = 25
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Temp falls but not below min
        zmw.registry.get_thing('tempSensor1').temp = 22
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        # Temp falls below min
        zmw.registry.get_thing('tempSensor1').temp = 10
        sut.tick()
        self.assertEqual(state_change_saver.saved_new.request_on, True)





if __name__ == '__main__':
    unittest.main()

