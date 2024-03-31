from datetime import datetime
import json
import unittest

from schedule import Schedule
from schedule_builder import ScheduleBuilder

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
    sut = ScheduleBuilder(ignore_state_changes, clock)
    for hr in range(0, 24):
        for qr in range(0, 4):
            sut.set_slot(hr, qr*15, should_be_on=True, reason="Sertest")
    return sut.as_json()


class ScheduleBuilderTest(unittest.TestCase):
    def test_default_schedule_off(self):
        sut = ScheduleBuilder(ignore_state_changes)
        for hr in range(0, 24):
            for qr in range(0,4):
                slot = sut.active().get_slot(hr, qr*15)
                self.assertEqual(slot.should_be_on, False)

    def test_jsonifies(self):
        sut = ScheduleBuilder(ignore_state_changes)
        sut.active().set_slot(21, 45, should_be_on=True, reason="Serialization test")
        self.assertTrue('"Serialization test"' in sut.as_json())
        json.loads(sut.as_json()) # Throw on invalid json

    def test_load_template_bad_json(self):
        sut = ScheduleBuilder(ignore_state_changes)
        sut.from_json("{aasd")

    def test_serdeser(self):
        sut = ScheduleBuilder(ignore_state_changes)
        sut.active().set_slot(21, 45, should_be_on=True, reason="Sertest")
        sut2 = ScheduleBuilder(ignore_state_changes)
        sut2.from_json(sut.as_json())
        slot = sut.active().get_slot(21, 45)
        self.assertEqual(slot.should_be_on, True)
        self.assertEqual(slot.reason, "Sertest")

    def test_deser_sched_only(self):
        sut = ScheduleBuilder(ignore_state_changes)
        sut.from_json('{"active": [{"hour": 23, "minute": 30, "should_be_on": true, "reason": "Sertest"}]}')
        for hr in range(0, 24):
            for qr in range(0,4):
                slot = sut.active().get_slot(hr, qr*15)
                if hr == 23 and qr == 2:
                    self.assertEqual(slot.should_be_on, True)
                    self.assertEqual(slot.reason, "Sertest")
                else:
                    self.assertEqual(slot.should_be_on, False)

    def test_deser_tmpl_only(self):
        sut = ScheduleBuilder(ignore_state_changes)
        sut.from_json('{"template": [{"hour": 23, "minute": 30, "should_be_on": true, "reason": "Sertest"}]}')
        for hr in range(0, 24):
            for qr in range(0,4):
                slot = sut.get_slot(hr, qr*15)
                if hr == 23 and qr == 2:
                    self.assertEqual(slot.should_be_on, True)
                    self.assertEqual(slot.reason, "Sertest")
                else:
                    self.assertEqual(slot.should_be_on, False)

    def test_deser_tmpl_only_doesnt_affect_active(self):
        clock = FakeClock(15, 10)
        sut = ScheduleBuilder(ignore_state_changes, clock)
        sut.from_json(get_all_on_schedule())
        for hr in range(0, 24):
            for mn in range(0, 60):
                self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, False, f"Failed slot {hr}:{mn}")
                self.assertEqual(sut.get_slot(hr, mn).should_be_on, True, f"Failed template slot {hr}:{mn}")
                self.assertEqual(sut.get_slot(hr, mn).reason, "Sertest", f"Failed template slot {hr}:{mn}")

    def test_tick_applies_template(self):
        clock = FakeClock(15, 10)
        sut = ScheduleBuilder(ignore_state_changes, clock)
        self.assertEqual(sut.active().get_slot(15, 0).should_be_on, False)
        sut.set_slot(15, 0, should_be_on=True, reason="Sertest")
        clock.set_t(15, 20)
        sut.tick()
        self.assertEqual(sut.active().get_slot(15, 0).should_be_on, True)
        self.assertEqual(sut.active().get_slot(15, 0).reason, "Sertest")

    def test_tick_applies_template_to_next_day(self):
        clock = FakeClock(0, 0)
        sut = ScheduleBuilder(ignore_state_changes, clock)
        sut.from_json(get_all_on_schedule())
        # Pass one: current schedule should be the default one, as template is only applied to next day
        for hr in range(0, 24):
            for mn in range(0, 60):
                clock.set_t(hr, mn)
                sut.tick()
                self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, False, f"Failed slot {hr}:{mn}")
                self.assertEqual(sut.get_slot(hr, mn).should_be_on, True, f"Failed template slot {hr}:{mn}")
                self.assertEqual(sut.get_slot(hr, mn).reason, "Sertest", f"Failed template slot {hr}:{mn}")
        # Second loop: the template should have been applied to all next day (and subsequent days)
        for hr in range(0, 48):
            for mn in range(0, 60):
                hr = hr % 24
                clock.set_t(hr, mn)
                sut.tick()
                self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, True, f"Failed template slot {hr}:{mn}")
                self.assertEqual(sut.active().get_slot(hr, mn).reason, "Sertest", f"Failed template slot {hr}:{mn}")

    def test_apply_template_on_user_ask(self):
        clock = FakeClock(0, 0)
        sut = ScheduleBuilder(ignore_state_changes, clock)
        sut.from_json(get_all_on_schedule())
        sut.apply_template_to_today()
        for hr in range(0, 23):
            for mn in range(0, 60):
                self.assertEqual(sut.active().get_slot(hr, mn).should_be_on, True, f"Failed template slot {hr}:{mn}")
                self.assertEqual(sut.active().get_slot(hr, mn).reason, "Sertest", f"Failed template slot {hr}:{mn}")


if __name__ == '__main__':
    unittest.main()
