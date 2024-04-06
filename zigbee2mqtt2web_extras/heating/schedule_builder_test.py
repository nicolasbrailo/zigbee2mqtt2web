from datetime import datetime
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.append(pathlib.Path(__file__).resolve())

from .schedule import Schedule, ShouldBeOn
from .schedule_builder import ScheduleBuilder

class FakeClock:
    def __init__(self, hour, minute, day=None):
        self._now = None
        self.set_t(hour, minute, day)
    def set_t(self, hour, minute, day=None):
        self._now = datetime.now()
        self._now = self._now.replace(hour=hour)
        self._now = self._now.replace(minute=minute)
        if day is not None:
            self._now = self._now.replace(day=day)
    def now(self):
        return self._now


def ignore_state_changes(new, old):
    pass

def get_all_on_schedule():
    clock = FakeClock(0, 0)
    sut = ScheduleBuilder(ignore_state_changes, None, clock)
    for hr in range(0, 24):
        for qr in range(0, 4):
            sut.set_slot(hr, qr*15, should_be_on=ShouldBeOn.Always)
    return sut.as_json()


class ScheduleBuilderTest(unittest.TestCase):
    def test_default_schedule_off(self):
        sut = ScheduleBuilder(ignore_state_changes, None)
        for hr in range(0, 24):
            for qr in range(0,4):
                slot = sut.active().get_slot(hr, qr*15)
                self.assertEqual(slot.should_be_on, ShouldBeOn.Never)

    def test_jsonifies(self):
        sut = ScheduleBuilder(ignore_state_changes, None)
        sut.active().set_slot(21, 45, should_be_on=ShouldBeOn.Always, reason="Serialization test")
        self.assertTrue('"Serialization test"' in sut.as_json())
        json.loads(sut.as_json()) # Throw on invalid json

    def test_load_template_bad_json(self):
        sut = ScheduleBuilder(ignore_state_changes, None)
        sut.from_json("{aasd")

    def test_serdeser(self):
        sut = ScheduleBuilder(ignore_state_changes, None)
        sut.active().set_slot(21, 45, should_be_on=ShouldBeOn.Always, reason="Sertest")
        sut2 = ScheduleBuilder(ignore_state_changes, None)
        sut2.from_json(sut.as_json())
        slot = sut.active().get_slot(21, 45)
        self.assertEqual(slot.should_be_on, ShouldBeOn.Always)
        self.assertEqual(slot.reason, "Sertest")

    def test_deser_sched_only(self):
        sut = ScheduleBuilder(ignore_state_changes, None)
        sut.from_json('{"active": [{"hour": 23, "minute": 30, "should_be_on": "Always", "reason": "Sertest"}]}')
        for hr in range(0, 24):
            for qr in range(0,4):
                slot = sut.active().get_slot(hr, qr*15)
                if hr == 23 and qr == 2:
                    self.assertEqual(slot.should_be_on, ShouldBeOn.Always)
                    self.assertEqual(slot.reason, "Sertest")
                else:
                    self.assertEqual(slot.should_be_on, ShouldBeOn.Never)

    def test_deser_tmpl_only(self):
        sut = ScheduleBuilder(ignore_state_changes, None)
        sut.from_json('{"template": [{"hour": 23, "minute": 30, "should_be_on": "Always", "reason": "Sertest"}]}')
        for hr in range(0, 24):
            for qr in range(0,4):
                slot = sut.get_slot(hr, qr*15)
                if hr == 23 and qr == 2:
                    self.assertEqual(slot.should_be_on, ShouldBeOn.Always)
                    self.assertEqual(slot.reason, "Sertest")
                else:
                    self.assertEqual(slot.should_be_on, ShouldBeOn.Never)

    def test_deser_tmpl_only_doesnt_affect_active(self):
        clock = FakeClock(15, 10)
        sut = ScheduleBuilder(ignore_state_changes, None, clock)
        sut.from_json(get_all_on_schedule())
        for hr in range(0, 24):
            for mn in range(0, 60):
                self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, ShouldBeOn.Never, f"Failed slot {hr}:{mn}")
                self.assertEqual(sut.get_slot(hr, mn).should_be_on, ShouldBeOn.Always, f"Failed template slot {hr}:{mn}")

    def test_creates_state_file(self):
        fname = None
        with tempfile.NamedTemporaryFile(delete=True) as temp_file:
            fname = temp_file.name
        self.assertFalse(os.path.exists(fname))
        sut = ScheduleBuilder(ignore_state_changes, fname)
        self.assertTrue(os.path.isfile(fname))
        os.remove(fname)

    def test_reads_state_file(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as temp_file:
            temp_file.write(get_all_on_schedule())
            sut = ScheduleBuilder(ignore_state_changes, temp_file.name)
            for hr in range(0, 24):
                for mn in range(0, 60):
                    self.assertEqual(sut.get_slot(hr, mn).should_be_on, ShouldBeOn.Always, f"Failed template slot {hr}:{mn}")

    def test_default_tmpl_all_of(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            os.remove(temp_file.name)
            sut = ScheduleBuilder(ignore_state_changes, temp_file.name)
            for hr in range(0, 24):
                for mn in range(0, 60):
                    self.assertEqual(sut.get_slot(hr, mn).should_be_on, ShouldBeOn.Never, f"Failed template slot {hr}:{mn}")
                    self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, ShouldBeOn.Never, f"Failed template slot {hr}:{mn}")

    def test_survives_wrong_ser_file(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as temp_file:
            temp_file.write('random garbage')
            sut = ScheduleBuilder(ignore_state_changes, temp_file.name)

    def test_serializes_state_on_tick(self):
        fname = None
        with tempfile.NamedTemporaryFile(delete=True) as temp_file:
            fname = temp_file.name
        sut = ScheduleBuilder(ignore_state_changes, fname)
        self.assertTrue(os.path.isfile(fname))
        os.remove(fname)
        self.assertFalse(os.path.exists(fname))
        sut.tick()
        self.assertTrue(os.path.isfile(fname))
        os.remove(fname)

    def test_serializes_state(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as temp_file:
            sut = ScheduleBuilder(ignore_state_changes, temp_file.name)
            sut.set_slot(15, 30, should_be_on=ShouldBeOn.Always, reason="Hola")
            sut.active().set_slot(18, 45, should_be_on=ShouldBeOn.Always, reason="Hola")
            sut.save_state()
            with open(temp_file.name, "r") as fp:
                saved_state = json.loads(fp.read())
                found = False
                for slot in saved_state['template']:
                    if slot['hour'] == 15 and slot['minute'] == 30:
                        found = True
                        self.assertEqual(slot['should_be_on'], ShouldBeOn.Always)
                        self.assertEqual(slot['reason'], "Hola")
                        break
                found = False
                for slot in saved_state['active']:
                    print(slot)
                    if slot['hour'] == 18 and slot['minute'] == 45:
                        found = True
                        self.assertEqual(slot['should_be_on'], ShouldBeOn.Always)
                        self.assertEqual(slot['reason'], "Hola")
                        break
                self.assertTrue(found)

    def test_tick_applies_template(self):
        clock = FakeClock(15, 10)
        sut = ScheduleBuilder(ignore_state_changes, None, clock)
        self.assertEqual(sut.active().get_slot(15, 0).should_be_on, ShouldBeOn.Never)
        sut.set_slot(15, 0, should_be_on=ShouldBeOn.Always)
        clock.set_t(15, 20)
        sut.tick()
        self.assertEqual(sut.active().get_slot(15, 0).should_be_on, ShouldBeOn.Always)

    def test_tick_applies_template_to_next_day(self):
        clock = FakeClock(0, 0)
        sut = ScheduleBuilder(ignore_state_changes, None, clock)
        sut.from_json(get_all_on_schedule())
        # Pass one: current schedule should be the default one, as template is only applied to next day
        for hr in range(0, 24):
            for mn in range(0, 60):
                clock.set_t(hr, mn)
                sut.tick()
                self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, ShouldBeOn.Never, f"Failed slot {hr}:{mn}")
                self.assertEqual(sut.get_slot(hr, mn).should_be_on, ShouldBeOn.Always, f"Failed template slot {hr}:{mn}")
        # Second loop: the template should have been applied to all next day (and subsequent days)
        for hr in range(0, 48):
            for mn in range(0, 60):
                hr = hr % 24
                clock.set_t(hr, mn)
                sut.tick()
                self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, ShouldBeOn.Always, f"Failed template slot {hr}:{mn}")

    def test_apply_template_on_user_ask(self):
        clock = FakeClock(0, 0)
        sut = ScheduleBuilder(ignore_state_changes, None, clock)
        sut.from_json(get_all_on_schedule())
        sut.apply_template_to_today()
        for hr in range(0, 24):
            for mn in range(0, 60):
                self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, ShouldBeOn.Always, f"Failed template slot {hr}:{mn}")

    def test_reset_tmpl(self):
        clock = FakeClock(15, 10)
        sut = ScheduleBuilder(ignore_state_changes, None, clock)
        sut.from_json(get_all_on_schedule())
        sut.apply_template_to_today()
        sut.reset_template(ShouldBeOn.Never)
        for hr in range(0, 24):
            for mn in range(0, 60, 15):
                self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, ShouldBeOn.Always, f"Failed slot {hr}:{mn}")
                self.assertEqual(sut.get_slot(hr, mn).should_be_on, ShouldBeOn.Never, f"Failed template slot {hr}:{mn}")
        sut.apply_template_to_today()
        sut.reset_template(ShouldBeOn.Rule)
        for hr in range(0, 24):
            for mn in range(0, 60, 15):
                self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, ShouldBeOn.Never, f"Failed slot {hr}:{mn}")
                self.assertEqual(sut.get_slot(hr, mn).should_be_on, ShouldBeOn.Rule, f"Failed template slot {hr}:{mn}")


if __name__ == '__main__':
    unittest.main()
