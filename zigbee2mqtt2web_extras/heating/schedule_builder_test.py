from datetime import datetime
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.append(pathlib.Path(__file__).resolve())

from .schedule import Schedule, AllowOn
from .schedule_builder import ScheduleBuilder
from .schedule_test import FakeClock, StateChangeSaver, ignore_state_changes

NO_RULES = []

def get_schedule_all_slots(policy):
    clock = FakeClock(0, 0)
    sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES, clock)
    for hr in range(0, 24):
        for qr in range(0, 4):
            sut.set_slot(hr, qr*15, allow_on=policy)
    sut.apply_template_to_today()
    return sut.as_json()


class ScheduleBuilderTest(unittest.TestCase):
    def test_default_schedule_off(self):
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES)
        for hr in range(0, 24):
            for qr in range(0,4):
                slot = sut.active().get_slot(hr, qr*15)
                self.assertEqual(slot.allow_on, AllowOn.Never)

    def test_jsonifies(self):
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES)
        sut.active().set_slot(21, 45, allow_on=AllowOn.Always, reason="Serialization test")
        self.assertTrue('"Serialization test"' in sut.as_json())
        json.loads(sut.as_json()) # Throw on invalid json

    def test_load_template_bad_json(self):
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES)
        sut.from_json("{aasd")

    def test_serdeser(self):
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES)
        sut.active().set_slot(21, 45, allow_on=AllowOn.Always, reason="Sertest")
        sut2 = ScheduleBuilder(ignore_state_changes, None, NO_RULES)
        sut2.from_json(sut.as_json())
        slot = sut.active().get_slot(21, 45)
        self.assertEqual(slot.allow_on, AllowOn.Always)
        self.assertEqual(slot.reason, "Sertest")

    def test_deser_sched_only(self):
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES)
        sut.from_json('{"active": [{"hour": 23, "minute": 30, "allow_on": "Always", "reason": "Sertest"}]}')
        for hr in range(0, 24):
            for qr in range(0,4):
                slot = sut.active().get_slot(hr, qr*15)
                if hr == 23 and qr == 2:
                    self.assertEqual(slot.allow_on, AllowOn.Always)
                    self.assertEqual(slot.reason, "Sertest")
                else:
                    self.assertEqual(slot.allow_on, AllowOn.Never)

    def test_deser_tmpl_only(self):
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES)
        sut.from_json('{"template": [{"hour": 23, "minute": 30, "allow_on": "Always", "reason": "Sertest"}]}')
        for hr in range(0, 24):
            for qr in range(0,4):
                slot = sut.get_slot(hr, qr*15)
                if hr == 23 and qr == 2:
                    self.assertEqual(slot.allow_on, AllowOn.Always)
                    self.assertEqual(slot.reason, "Sertest")
                else:
                    self.assertEqual(slot.allow_on, AllowOn.Never)

    def test_creates_state_file(self):
        fname = None
        with tempfile.NamedTemporaryFile(delete=True) as temp_file:
            fname = temp_file.name
        self.assertFalse(os.path.exists(fname))
        sut = ScheduleBuilder(ignore_state_changes, fname, NO_RULES)
        self.assertTrue(os.path.isfile(fname))
        os.remove(fname)

    def test_reads_state_file(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as temp_file:
            temp_file.write(get_schedule_all_slots(AllowOn.Always))
            sut = ScheduleBuilder(ignore_state_changes, temp_file.name, NO_RULES)
            for hr in range(0, 24):
                for mn in range(0, 60):
                    self.assertEqual(sut.get_slot(hr, mn).allow_on, AllowOn.Always, f"Failed template slot {hr}:{mn}")

    def test_default_tmpl_all_of(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            os.remove(temp_file.name)
            sut = ScheduleBuilder(ignore_state_changes, temp_file.name, NO_RULES)
            for hr in range(0, 24):
                for mn in range(0, 60):
                    self.assertEqual(sut.get_slot(hr, mn).allow_on, AllowOn.Never, f"Failed template slot {hr}:{mn}")
                    self.assertEqual(sut.active().get_slot(hr, mn).allow_on, AllowOn.Never, f"Failed template slot {hr}:{mn}")

    def test_survives_wrong_ser_file(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as temp_file:
            temp_file.write('random garbage')
            sut = ScheduleBuilder(ignore_state_changes, temp_file.name, NO_RULES)

    def test_serializes_state_on_tick(self):
        fname = None
        with tempfile.NamedTemporaryFile(delete=True) as temp_file:
            fname = temp_file.name
        sut = ScheduleBuilder(ignore_state_changes, fname, NO_RULES)
        self.assertTrue(os.path.isfile(fname))
        os.remove(fname)
        self.assertFalse(os.path.exists(fname))
        sut.tick()
        self.assertTrue(os.path.isfile(fname))
        os.remove(fname)

    def test_serializes_state(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as temp_file:
            sut = ScheduleBuilder(ignore_state_changes, temp_file.name, NO_RULES)
            sut.set_slot(15, 30, allow_on=AllowOn.Always, reason="Hola")
            sut.active().set_slot(18, 45, allow_on=AllowOn.Always, reason="Hola")
            sut.save_state()
            with open(temp_file.name, "r") as fp:
                saved_state = json.loads(fp.read())
                found = False
                for slot in saved_state['template']:
                    if slot['hour'] == 15 and slot['minute'] == 30:
                        found = True
                        self.assertEqual(slot['allow_on'], AllowOn.Always)
                        self.assertEqual(slot['reason'], "Hola")
                        break
                found = False
                for slot in saved_state['active']:
                    print(slot)
                    if slot['hour'] == 18 and slot['minute'] == 45:
                        found = True
                        self.assertEqual(slot['allow_on'], AllowOn.Always)
                        self.assertEqual(slot['reason'], "Hola")
                        break
                self.assertTrue(found)

    def test_tick_applies_template(self):
        clock = FakeClock(15, 10)
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES, clock)
        self.assertEqual(sut.active().get_slot(15, 0).allow_on, AllowOn.Never)
        sut.set_slot(15, 0, allow_on=AllowOn.Always)
        clock.set_t(15, 20)
        sut.tick()
        self.assertEqual(sut.active().get_slot(15, 0).allow_on, AllowOn.Always)

    def test_set_slot_resets_boiler_state_off(self):
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES)
        sut.set_slot(15, 0, allow_on=AllowOn.Always)
        self.assertEqual(sut.get_slot(15, 0).request_on, True)
        self.assertEqual(sut.get_slot(15, 0).allow_on, AllowOn.Always)
        sut.set_slot(15, 0, allow_on=AllowOn.Rule)
        self.assertEqual(sut.get_slot(15, 0).request_on, False)
        self.assertEqual(sut.get_slot(15, 0).allow_on, AllowOn.Rule)

    def test_tick_applies_template_to_next_day(self):
        clock = FakeClock(0, 0)
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES, clock)
        sut.from_json(get_schedule_all_slots(AllowOn.Always))
        # Pass one: set current schedule off, ensure template is on so it applies to next day
        for hr in range(0, 24):
            for mn in range(0, 60):
                clock.set_t(hr, mn)
                sut.tick()
                sut.active().set_slot(hr, mn, AllowOn.Never)
                self.assertEqual(sut.get_slot(hr, mn).allow_on, AllowOn.Always, f"Failed template slot {hr}:{mn}")
        # Second loop: the template should have been applied to all next day (and subsequent days)
        for hr in range(0, 48):
            for mn in range(0, 60):
                hr = hr % 24
                clock.set_t(hr, mn)
                sut.tick()
                self.assertEqual(sut.active().get_slot(hr, mn).allow_on, AllowOn.Always, f"Failed template slot {hr}:{mn}")

    def test_apply_template_on_user_ask(self):
        clock = FakeClock(0, 0)
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES, clock)
        sut.from_json(get_schedule_all_slots(AllowOn.Always))
        for hr in range(0, 24):
            for mn in range(0, 60):
                self.assertEqual(sut.active().get_slot(hr, mn).allow_on, AllowOn.Always, f"Failed template slot {hr}:{mn}")

    def test_reset_tmpl(self):
        clock = FakeClock(15, 10)
        sut = ScheduleBuilder(ignore_state_changes, None, NO_RULES, clock)
        sut.from_json(get_schedule_all_slots(AllowOn.Always))
        sut.apply_template_to_today()
        sut.reset_template(AllowOn.Never)
        for hr in range(0, 24):
            for mn in range(0, 60, 15):
                self.assertEqual(sut.active().get_slot(hr, mn).allow_on, AllowOn.Always, f"Failed slot {hr}:{mn}")
                self.assertEqual(sut.get_slot(hr, mn).allow_on, AllowOn.Never, f"Failed template slot {hr}:{mn}")
        sut.apply_template_to_today()
        sut.reset_template(AllowOn.Rule)
        for hr in range(0, 24):
            for mn in range(0, 60, 15):
                self.assertEqual(sut.active().get_slot(hr, mn).allow_on, AllowOn.Never, f"Failed slot {hr}:{mn}")
                self.assertEqual(sut.get_slot(hr, mn).allow_on, AllowOn.Rule, f"Failed template slot {hr}:{mn}")

    def test_apply_rules(self):
        def foo(sched):
            sched.set_now_from_rule(False, "Rule")
        clock = FakeClock(15, 30)
        sut = ScheduleBuilder(ignore_state_changes, None, [foo], clock)
        sut.from_json(get_schedule_all_slots(AllowOn.Always))
        sut.active().set_slot(15, 30, allow_on=AllowOn.Rule)

        self.assertEqual(sut.active().get_slot(15, 30).allow_on, AllowOn.Rule)
        self.assertEqual(sut.active().get_slot(15, 30).request_on, True)
        sut.tick()
        self.assertEqual(sut.active().get_slot(15, 30).allow_on, AllowOn.Rule)
        self.assertEqual(sut.active().get_slot(15, 30).reason, "Rule")
        self.assertEqual(sut.active().get_slot(15, 30).request_on, False)

    def test_apply_rules_in_order(self):
        def r1(sched):
            sched.set_now_from_rule(True, "Rule1")
        def r2(sched):
            sched.set_now_from_rule(False, "Rule2")
        clock = FakeClock(15, 30)
        sut = ScheduleBuilder(ignore_state_changes, None, [r1, r2], clock)
        sut.from_json(get_schedule_all_slots(AllowOn.Always))
        sut.active().set_slot(15, 30, allow_on=AllowOn.Rule)
        sut.tick()
        self.assertEqual(sut.active().get_slot(15, 30).reason, "Rule2")
        self.assertEqual(sut.active().get_slot(15, 30).request_on, False)

    def test_apply_multiple_rules_notify_last(self):
        def r1(sched):
            sched.set_now_from_rule(True, "Rule1")
        def r2(sched):
            sched.set_now_from_rule(False, "Rule2")
        def r3(sched):
            sched.set_now_from_rule(True, "Rule3")
        clock = FakeClock(15, 30)
        state_change_saver = StateChangeSaver()
        sut = ScheduleBuilder(state_change_saver.save_state_changes, None, [r1, r2, r3], clock)

        sut.from_json(get_schedule_all_slots(AllowOn.Always))
        sut.active().set_slot(15, 30, allow_on=AllowOn.Rule)
        sut.tick()

        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.Rule)
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        self.assertEqual(state_change_saver.saved_new.reason, "Rule3")



if __name__ == '__main__':
    unittest.main()
