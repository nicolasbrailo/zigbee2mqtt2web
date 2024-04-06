import json
import pathlib
import sys
import unittest

sys.path.append(pathlib.Path(__file__).resolve())

from .rules import *
from .schedule import AllowOn
from .schedule_builder import ScheduleBuilder
from .schedule_test import FakeClock, StateChangeSaver, ignore_state_changes
from .schedule_builder_test import get_schedule_all_slots

CFG_TEMP_IN_RANGE = """[
    {"name": "CheckTempsWithinRange", "min_temp": 5, "max_temp": 15, "sensors": ["tempSensor1", "tempSensor2", "tempSensor3"]}
]"""

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
    def registry(self):
        return self.registry


class RulesTest(unittest.TestCase):
    def test_create_empty(self):
        rules = create_rules_from_config(None, [])
        self.assertEqual(len(rules), 0)

    def test_ignore_unknown(self):
        rules = create_rules_from_config(None, json.loads('[{"name":"RuleThatDoesntExist"}]'))
        self.assertEqual(len(rules), 0)

    def test_create_CheckTempsWithinRange(self):
        rules = create_rules_from_config(FakeZmw(), json.loads(CFG_TEMP_IN_RANGE))
        self.assertEqual(len(rules), 1)
        self.assertEqual(type(rules[0]), CheckTempsWithinRange)
        self.assertEqual(rules[0].min_temp, 5)
        self.assertTrue('tempSensor1' in rules[0].sensors_to_monitor)
        self.assertTrue('tempSensor2' in rules[0].sensors_to_monitor)
        self.assertTrue('tempSensor3' in rules[0].sensors_to_monitor)

    def test_failure_setup_CheckTempsWithinRange(self):
        cfg = json.loads(CFG_TEMP_IN_RANGE)
        del cfg[0]['min_temp']
        rules = create_rules_from_config(FakeZmw(), cfg)
        self.assertEqual(len(rules), 0)

        cfg[0]['min_temp'] = 42
        cfg[0]['max_temp'] = 20
        rules = create_rules_from_config(FakeZmw(), cfg)
        self.assertEqual(len(rules), 0)

        cfg[0]['min_temp'] = 20
        cfg[0]['max_temp'] = 21
        rules = create_rules_from_config(FakeZmw(), cfg)
        self.assertEqual(len(rules), 0)

        cfg[0]['sensors'] = ['tempSensor1']
        cfg[0]['min_temp'] = []
        rules = create_rules_from_config(FakeZmw(), cfg)
        self.assertEqual(len(rules), 0)

        cfg[0]['min_temp'] = 0
        rules = create_rules_from_config(FakeZmw(), cfg)
        self.assertEqual(len(rules), 1)

    def test_apply_CheckTempsWithinRange(self):
        state_change_saver = StateChangeSaver()
        zmw = FakeZmw()
        rules = create_rules_from_config(zmw, json.loads(CFG_TEMP_IN_RANGE))
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, rules)

        sut.from_json(get_schedule_all_slots(AllowOn.Rule))
        zmw.registry.get_thing('tempSensor2').temp = -4
        sut.tick()

        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.Rule)
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
        rules = create_rules_from_config(zmw, json.loads(CFG_TEMP_IN_RANGE))
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, rules)
        sut.from_json(get_schedule_all_slots(AllowOn.Rule))
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

if __name__ == '__main__':
    unittest.main()

