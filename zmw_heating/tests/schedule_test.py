import unittest
from datetime import datetime

import copy
import os

from schedule import Schedule, ScheduleSlot, hr_mn_to_slot_t, AllowOn

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

class StateChangeSaver:
    def __init__(self):
        self.saved_new = None
        self.saved_old = None
        self.count = 0

    def save_state_changes(self, new, old):
        self.saved_new = copy.copy(new)
        self.saved_old = copy.copy(old)
        self.count += 1


class ScheduleTest(unittest.TestCase):
    def test_fake_clock(self):
        clock = FakeClock(hour=12, minute=0)
        self.assertEqual(clock.now().hour, 12)
        self.assertEqual(clock.now().minute, 0)

    def test_schedule_defaults_off(self):
        sut = Schedule(ignore_state_changes)
        for hr in range(24):
            for mn in range(4):
                self.assertEqual(sut.get_slot(hr, 15*mn).request_on, False)
                self.assertEqual(sut.get_slot(hr, 15*mn).allow_on, AllowOn.NEVER)

    def test_schedule_fails_bad_time(self):
        sut = Schedule(ignore_state_changes)
        self.assertRaises(ValueError, sut.set_slot, 25, 15)
        self.assertRaises(ValueError, sut.set_slot, 22, 65)
        sut.set_slot(12, 12) # Test no raise

    def test_schedule_saves_on(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(12, 15, allow_on=AllowOn.ALWAYS, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.allow_on, AllowOn.ALWAYS)
        self.assertEqual(slot.request_on, True)
        self.assertEqual(slot.reason, "Test")

    def test_schedule_saves_on_off(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(12, 15, allow_on=AllowOn.ALWAYS, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.allow_on, AllowOn.ALWAYS)
        self.assertEqual(slot.request_on, True)
        self.assertEqual(slot.reason, "Test")
        sut.set_slot(12, 15, allow_on=AllowOn.NEVER, reason="Test 2")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.allow_on, AllowOn.NEVER)
        self.assertEqual(slot.request_on, False)
        self.assertEqual(slot.reason, "Test 2")
        sut.set_slot(12, 18, allow_on=AllowOn.ALWAYS, reason="Test 2")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.allow_on, AllowOn.ALWAYS)
        self.assertEqual(slot.request_on, True)
        self.assertEqual(slot.reason, "Test 2")

    def test_schedule_saves_toggle(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(12, 15, allow_on=AllowOn.ALWAYS, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.allow_on, AllowOn.ALWAYS)
        self.assertEqual(slot.request_on, True)
        self.assertEqual(slot.reason, "Test")
        sut.toggle_slot(12, 15, reason="Toggle")
        self.assertEqual(slot.allow_on, AllowOn.NEVER)
        self.assertEqual(slot.request_on, False)
        self.assertEqual(slot.reason, "Toggle")
        sut.toggle_slot(12, 15, reason="Toggle 2")
        self.assertEqual(slot.allow_on, AllowOn.ALWAYS)
        self.assertEqual(slot.request_on, True)
        self.assertEqual(slot.reason, "Toggle 2")

    def test_schedule_on_off_overrides_rule(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(12, 15, allow_on=AllowOn.ALWAYS, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.allow_on, AllowOn.ALWAYS)
        self.assertEqual(slot.request_on, True)
        self.assertEqual(slot.reason, "Test")

        sut.set_slot(12, 15, allow_on=AllowOn.RULE, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.allow_on, AllowOn.RULE)
        self.assertEqual(slot.request_on, True)
        self.assertEqual(slot.reason, "Test")

        sut.set_slot(12, 15, allow_on=AllowOn.NEVER, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.allow_on, AllowOn.NEVER)
        self.assertEqual(slot.request_on, False)
        self.assertEqual(slot.reason, "Test")

        sut.set_slot(12, 15, allow_on=AllowOn.RULE, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.allow_on, AllowOn.RULE)
        self.assertEqual(slot.request_on, False)
        self.assertEqual(slot.reason, "Test")

    def test_schedule_toggle_overrides_rule(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(12, 15, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(sut.get_slot(12, 15).request_on, True)

        sut.set_slot(12, 15, allow_on=AllowOn.RULE, reason="Test")
        self.assertEqual(sut.get_slot(12, 15).request_on, True)

        sut.toggle_slot(12, 15, reason="Toggle")
        self.assertEqual(sut.get_slot(12, 15).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(12, 15).request_on, False)
        self.assertEqual(sut.get_slot(12, 15).reason, "Toggle")

        sut.set_slot(12, 15, allow_on=AllowOn.RULE, reason="Test 2")
        self.assertEqual(sut.get_slot(12, 15).request_on, False)
        self.assertEqual(sut.get_slot(12, 15).reason, "Test 2")

        sut.toggle_slot(12, 15, reason="Toggle2")
        self.assertEqual(sut.get_slot(12, 15).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(12, 15).request_on, True)
        self.assertEqual(sut.get_slot(12, 15).reason, "Toggle2")


    def test_schedule_saves_toggle_by_name(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(12, 15, allow_on=AllowOn.ALWAYS, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.allow_on, AllowOn.ALWAYS)
        self.assertEqual(slot.reason, "Test")
        sut.toggle_slot_by_name("12:15", reason="Toggle")
        self.assertEqual(slot.allow_on, AllowOn.NEVER)
        sut.toggle_slot_by_name(hr_mn_to_slot_t(12, 15), reason="Toggle")
        self.assertEqual(slot.allow_on, AllowOn.ALWAYS)

        sut.toggle_slot_by_name('1:1', reason="Toggle")
        slot = sut.get_slot(1, 0)
        self.assertEqual(slot.allow_on, AllowOn.ALWAYS)

    def test_schedule_maps_to_quarter(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(0, 0, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(sut.get_slot(0, 0).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(0, 0).reason, "Test")
        self.assertEqual(sut.get_slot(0, 1).reason, "Test")
        self.assertEqual(sut.get_slot(0, 5).reason, "Test")
        self.assertEqual(sut.get_slot(0, 8).reason, "Test")

        sut.set_slot(1, 3, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(sut.get_slot(1, 0).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(1, 0).reason, "Test")
        self.assertEqual(sut.get_slot(1, 15).allow_on, AllowOn.NEVER)

        sut.set_slot(2, 7, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(sut.get_slot(2, 0).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(2, 0).reason, "Test")
        self.assertEqual(sut.get_slot(2, 15).allow_on, AllowOn.NEVER)

        sut.set_slot(3, 12, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(sut.get_slot(3, 0).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(3, 0).reason, "Test")
        self.assertEqual(sut.get_slot(3, 15).allow_on, AllowOn.NEVER)

        sut.set_slot(4, 14, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(sut.get_slot(4, 0).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(4, 0).reason, "Test")
        self.assertEqual(sut.get_slot(4, 15).allow_on, AllowOn.NEVER)

    def test_schedule_maps_to_quarter_exahustive(self):
        sut = Schedule(ignore_state_changes)
        for i in range(15):
            sut.set_slot(i, i, allow_on=AllowOn.ALWAYS, reason="Test")

        for hr in range(15):
            for mn in range(15):
                slot = sut.get_slot(hr, mn)
                self.assertEqual(slot.allow_on, AllowOn.ALWAYS)
                self.assertEqual(slot.reason, "Test")
            for mn in range(45):
                slot = sut.get_slot(hr, 15+mn)
                self.assertEqual(slot.allow_on, AllowOn.NEVER)
                self.assertEqual(slot.reason, "Default")

    def test_schedule_saves_all_quarters_hour_schedule(self):
        sut = Schedule(ignore_state_changes)
        slot = sut.set_slot(12, 0, AllowOn.ALWAYS)
        slot = sut.set_slot(12, 15, AllowOn.ALWAYS)
        slot = sut.set_slot(12, 30, AllowOn.ALWAYS)
        slot = sut.set_slot(12, 45, AllowOn.ALWAYS)
        for hr in range(24):
            for mn in range(4):
                if hr == 12:
                    slot = sut.get_slot(hr, 15*mn)
                    self.assertEqual(slot.allow_on, AllowOn.ALWAYS)
                else:
                    self.assertEqual(sut.get_slot(hr, 15*mn).allow_on, AllowOn.NEVER)

    def test_boost_fails(self):
        sut = Schedule(ignore_state_changes)
        self.assertRaises(ValueError, sut.boost, 200)
        self.assertRaises(ValueError, sut.boost, -1)

    def test_boost_hours(self):
        clock = FakeClock(16, 20)
        sut = Schedule(ignore_state_changes, clock)
        sut.boost(hours=2)
        for hr in range(24):
            for mn in range(4):
                if hr == 16 and mn == 1 or \
                   hr == 16 and mn == 2 or \
                   hr == 16 and mn == 3 or \
                   hr == 17 or \
                   hr == 18 and mn == 0:
                    slot = sut.get_slot(hr, 15*mn)
                    self.assertEqual(slot.allow_on, AllowOn.ALWAYS, f"Expected slot {hr}:{15*mn} to be active")
                    self.assertEqual(slot.request_on, True, f"Expected slot {hr}:{15*mn} to be on")
                    self.assertEqual(slot.reason, "User boost")
                else:
                    self.assertEqual(sut.get_slot(hr, 15*mn).allow_on, AllowOn.NEVER, f"Expected slot {hr}:{15*mn} to be not active")
                    self.assertEqual(sut.get_slot(hr, 15*mn).request_on, False, f"Expected slot {hr}:{15*mn} to be off")

    def test_boost_overrides_rules(self):
        clock = FakeClock(16, 0)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(16, 0, allow_on=AllowOn.RULE, reason="Test")
        sut.set_slot(16, 15, allow_on=AllowOn.NEVER, reason="Test")
        sut.set_slot(16, 30, allow_on=AllowOn.RULE, reason="Test")
        sut.set_slot(16, 45, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(17, 0, allow_on=AllowOn.RULE, reason="Test")
        sut.boost(hours=1)
        self.assertEqual(sut.get_slot(16, 0).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(16, 0).request_on, True)
        self.assertEqual(sut.get_slot(16, 15).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(16, 15).request_on, True)
        self.assertEqual(sut.get_slot(16, 30).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(16, 45).request_on, True)
        self.assertEqual(sut.get_slot(16, 45).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(17, 0).allow_on, AllowOn.RULE)

    def test_slot_set_moves_forward(self):
        clock = FakeClock(10, 20)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(10, 20, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(sut.get_slot(10, 15).allow_on, AllowOn.ALWAYS)

        clock.set_t(10, 30)
        self.assertEqual(sut.tick(), 1)
        self.assertEqual(sut.get_slot(10, 15).allow_on, AllowOn.NEVER)

    def test_slot_ticks_are_idempotent(self):
        clock = FakeClock(10, 20)
        sut = Schedule(ignore_state_changes, clock)
        clock.set_t(10, 30)
        self.assertEqual(sut.tick(), 1)
        self.assertEqual(sut.tick(), 0)

    def test_get_last_slot(self):
        clock = FakeClock(10, 20)
        sut = Schedule(ignore_state_changes, clock)
        self.assertEqual(sut.get_last_slot_hr_mn(), (10, 0))
        clock.set_t(10, 30)
        sut.tick()
        self.assertEqual(sut.get_last_slot_hr_mn(), (10, 15))
        clock.set_t(0, 0)
        sut.tick()
        self.assertEqual(sut.get_last_slot_hr_mn(), (23, 45))
        clock.set_t(0, 10)
        sut.tick()
        self.assertEqual(sut.get_last_slot_hr_mn(), (23, 45))
        clock.set_t(0, 20)
        sut.tick()
        self.assertEqual(sut.get_last_slot_hr_mn(), (0, 0))

    def test_tick_counts_advanced_slots(self):
        clock = FakeClock(10, 0)
        sut = Schedule(ignore_state_changes, clock)
        clock.set_t(11, 0)
        self.assertEqual(sut.tick(), 4)
        clock.set_t(23, 0)
        self.assertEqual(sut.tick(), 4*12)

    def test_slot_set_moves_forward_wraparound(self):
        clock = FakeClock(23, 50)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(23, 55, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(sut.get_slot(23, 45).allow_on, AllowOn.ALWAYS)

        clock.set_t(0, 0)
        sut.tick()
        self.assertEqual(sut.get_slot(23, 55).allow_on, AllowOn.NEVER)

    def test_detect_skip_slots(self):
        clock = FakeClock(10, 0)
        sut = Schedule(ignore_state_changes, clock)
        self.assertEqual(sut.tick_skipped_errors, 0)
        clock.set_t(10, 16)
        sut.tick()
        self.assertEqual(sut.tick_skipped_errors, 0)
        clock.set_t(10, 45)
        sut.tick()
        self.assertEqual(sut.tick_skipped_errors, 1)

    def test_skip_slots_wraparound(self):
        clock = FakeClock(23, 45)
        sut = Schedule(ignore_state_changes, clock)
        self.assertEqual(sut.tick_skipped_errors, 0)
        clock.set_t(0, 0)
        sut.tick()
        self.assertEqual(sut.tick_skipped_errors, 0)

    def test_detect_skip_slots_wraparound(self):
        clock = FakeClock(23, 45)
        sut = Schedule(ignore_state_changes, clock)
        self.assertEqual(sut.tick_skipped_errors, 0)
        clock.set_t(0, 15)
        sut.tick()
        self.assertEqual(sut.tick_skipped_errors, 1)

    def test_skipped_slots_reset(self):
        clock = FakeClock(10, 20)
        sut = Schedule(ignore_state_changes, clock)
        self.assertEqual(sut.tick_skipped_errors, 0)
        sut.set_slot(10, 15, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(10, 30, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(10, 45, allow_on=AllowOn.ALWAYS, reason="Test")

        clock.set_t(11, 30)
        sut.tick()
        self.assertEqual(sut.tick_skipped_errors, 4)
        self.assertEqual(sut.get_slot(10, 15).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(10, 15).request_on, False)
        self.assertEqual(sut.get_slot(10, 30).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(10, 30).request_on, False)
        self.assertEqual(sut.get_slot(10, 45).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(10, 45).request_on, False)

    def test_slot_set_moves_forward_wraparound_preserves(self):
        clock = FakeClock(23, 50)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(23, 55, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(0, 0, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(0, 15, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(0, 30, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(sut.get_slot(23, 45).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(23, 45).request_on, True)
        self.assertEqual(sut.get_slot(0, 0).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(0, 0).request_on, True)
        self.assertEqual(sut.get_slot(0, 15).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(0, 15).request_on, True)
        self.assertEqual(sut.get_slot(0, 30).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(0, 30).request_on, True)

        clock.set_t(0, 0)
        sut.tick()
        self.assertEqual(sut.get_slot(23, 45).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(23, 45).request_on, False)
        self.assertEqual(sut.get_slot(0, 0).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(0, 0).request_on, True)
        self.assertEqual(sut.get_slot(0, 15).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(0, 15).request_on, True)
        self.assertEqual(sut.get_slot(0, 30).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(0, 30).request_on, True)

    def test_boost_wraparound(self):
        clock = FakeClock(23, 50)
        sut = Schedule(ignore_state_changes, clock)
        sut.boost(hours=2)
        for hr in range(24):
            for mn in range(4):
                if hr == 23 and mn == 3 or \
                   hr == 0 and mn == 0 or \
                   hr == 0 and mn == 1 or \
                   hr == 0 and mn == 2 or \
                   hr == 0 and mn == 3 or \
                   hr == 1 and mn == 0 or \
                   hr == 1 and mn == 1 or \
                   hr == 1 and mn == 2:
                    slot = sut.get_slot(hr, 15*mn)
                    self.assertEqual(slot.allow_on, AllowOn.ALWAYS, f"Expected slot {hr}:{15*mn} to be active")
                    self.assertEqual(slot.reason, "User boost")
                else:
                    self.assertEqual(sut.get_slot(hr, 15*mn).allow_on, AllowOn.NEVER, f"Expected slot {hr}:{15*mn} to be not active")

        clock.set_t(0, 30)
        sut.tick()
        for hr in range(24):
            for mn in range(4):
                if hr == 0 and mn == 2 or \
                   hr == 0 and mn == 3 or \
                   hr == 1 and mn == 0 or \
                   hr == 1 and mn == 1 or \
                   hr == 1 and mn == 2:
                    slot = sut.get_slot(hr, 15*mn)
                    self.assertEqual(slot.allow_on, AllowOn.ALWAYS, f"Expected slot {hr}:{15*mn} to be active")
                    self.assertEqual(slot.reason, "User boost")
                else:
                    self.assertEqual(sut.get_slot(hr, 15*mn).allow_on, AllowOn.NEVER, f"Expected slot {hr}:{15*mn} to be not active")

    def test_off_now(self):
        clock = FakeClock(16, 0)
        sut = Schedule(ignore_state_changes, clock)
        sut.boost(hours=1)
        sut.set_slot(17, 15, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(sut.get_slot(16, 0).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(16, 15).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(16, 30).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(16, 45).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(17, 15).allow_on, AllowOn.ALWAYS)
        sut.off_now()
        self.assertEqual(sut.get_slot(16, 0).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(16, 0).reason, "User requested off")
        self.assertEqual(sut.get_slot(16, 15).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(16, 15).reason, "User requested off")
        self.assertEqual(sut.get_slot(16, 30).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(16, 30).reason, "User requested off")
        self.assertEqual(sut.get_slot(16, 45).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(16, 45).reason, "User requested off")
        # Disjoint slots shouldn't change
        self.assertEqual(sut.get_slot(17, 15).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(17, 15).reason, "Test")

    def test_off_has_maximum(self):
        sut = Schedule(ignore_state_changes, FakeClock(10, 0))
        for hr in range(24):
            for mn in range(0, 60, 15):
                # Force everything on, then switch to rule based
                sut.set_slot(hr, mn, AllowOn.ALWAYS)
                sut.set_slot(hr, mn, AllowOn.RULE)
                self.assertEqual(sut.get_slot(hr, mn).request_on, True)

        sut.off_now()
        for hr in range(sut.OFF_NOW_MAX_HOURS):
            for mn in range(0, 60, 15):
                self.assertEqual(sut.get_slot(10+hr, 0).allow_on, AllowOn.NEVER)
                self.assertEqual(sut.get_slot(10+hr, 0).request_on, False)
        for hr in range(sut.OFF_NOW_MAX_HOURS, 10):
            for mn in range(0, 60, 15):
                self.assertEqual(sut.get_slot(10+hr, 0).allow_on, AllowOn.RULE)
                self.assertEqual(sut.get_slot(10+hr, 0).request_on, True)

    def test_off_overrides_rules(self):
        clock = FakeClock(16, 0)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(16, 0, allow_on=AllowOn.RULE, reason="Test")
        sut.set_slot(16, 15, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(16, 30, allow_on=AllowOn.RULE, reason="Test")
        sut.set_slot(16, 45, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(17, 0, allow_on=AllowOn.RULE, reason="Test")
        sut.off_now()
        self.assertEqual(sut.get_slot(16, 0).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(16, 0).request_on, False)
        self.assertEqual(sut.get_slot(16, 15).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(16, 15).request_on, False)
        self.assertEqual(sut.get_slot(16, 30).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(16, 45).request_on, False)
        self.assertEqual(sut.get_slot(16, 45).allow_on, AllowOn.NEVER)


    def test_off_now_wraps(self):
        clock = FakeClock(23, 30)
        sut = Schedule(ignore_state_changes, clock)
        sut.boost(hours=1)
        self.assertEqual(sut.get_slot(23, 30).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(23, 45).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(0, 0).allow_on, AllowOn.ALWAYS)
        self.assertEqual(sut.get_slot(0, 15).allow_on, AllowOn.ALWAYS)
        sut.off_now()
        self.assertEqual(sut.get_slot(23, 30).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(23, 30).reason, "User requested off")
        self.assertEqual(sut.get_slot(23, 45).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(23, 45).reason, "User requested off")
        self.assertEqual(sut.get_slot(0, 0).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(0, 0).reason, "User requested off")
        self.assertEqual(sut.get_slot(0, 15).allow_on, AllowOn.NEVER)
        self.assertEqual(sut.get_slot(0, 15).reason, "User requested off")

    def test_slot_change_time(self):
        clock = FakeClock(16, 20)
        sut = Schedule(ignore_state_changes, clock)
        self.assertEqual(sut.get_slot_change_time().hour, 16)
        self.assertEqual(sut.get_slot_change_time().minute, 30)

    def test_slot_change_time_wraparound(self):
        clock = FakeClock(23, 55, day=20)
        sut = Schedule(ignore_state_changes, clock)
        self.assertEqual(sut.get_slot_change_time().hour, 0)
        self.assertEqual(sut.get_slot_change_time().minute, 0)
        self.assertEqual(sut.get_slot_change_time().day, 21)

    def test_schedule_as_jsonifyable_dict(self):
        clock = FakeClock(15, 0)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(16, 10, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(17, 30, allow_on=AllowOn.ALWAYS, reason="Test")
        t = sut.as_jsonifyable_dict()
        self.assertEqual(t[0]['hour'], 15)
        self.assertEqual(t[0]['minute'], 0)
        self.assertEqual(t[0]['allow_on'], AllowOn.NEVER)
        # Verify offset: delta from time start, + qr
        self.assertEqual(t[(16-15) * 4]['hour'], 16)
        self.assertEqual(t[(16-15) * 4]['minute'], 0)
        self.assertEqual(t[(16-15) * 4]['allow_on'], AllowOn.ALWAYS)
        self.assertEqual(t[((17-15) * 4) + 2]['hour'], 17)
        self.assertEqual(t[((17-15) * 4) + 2]['minute'], 30)
        self.assertEqual(t[((17-15) * 4) + 2]['allow_on'], AllowOn.ALWAYS)

    def test_notifies_state_changes(self):
        clock = FakeClock(15, 0)
        state_change_saver = StateChangeSaver()
        sut = Schedule(state_change_saver.save_state_changes, clock)
        sut.set_slot(15, 30, allow_on=AllowOn.ALWAYS, reason="Test")

        clock.set_t(15, 15)
        sut.tick()
        self.assertEqual(state_change_saver.count, 1)

        clock.set_t(15, 30)
        sut.tick()
        self.assertEqual(state_change_saver.count, 2)
        self.assertEqual(state_change_saver.saved_old.allow_on, AllowOn.NEVER)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_new.reason, "Test")

        for i in range(14):
            clock.set_t(15, 30+i)
            sut.tick()
            self.assertEqual(state_change_saver.count, 2)

        clock.set_t(15, 45)
        sut.tick()
        self.assertEqual(state_change_saver.count, 3)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.NEVER)
        self.assertEqual(state_change_saver.saved_old.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_old.reason, "Test")

    def test_notifies_on_object_ctr(self):
        clock = FakeClock(15, 0)
        state_change_saver = StateChangeSaver()
        sut = Schedule(state_change_saver.save_state_changes, clock)
        self.assertEqual(state_change_saver.count, 1)
        self.assertEqual(state_change_saver.saved_old, None)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.NEVER)
        self.assertEqual(state_change_saver.saved_new.reason, "Default")


    def test_notifies_when_changing_current_slot(self):
        clock = FakeClock(15, 0)
        state_change_saver = StateChangeSaver()
        sut = Schedule(state_change_saver.save_state_changes, clock)

        # Changing non active slot doesn't notify
        start_count = state_change_saver.count
        sut.set_slot(16, 5, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(state_change_saver.count, start_count)

        # Changing active slot does notify
        sut.set_slot(15, 5, allow_on=AllowOn.ALWAYS, reason="Test")
        self.assertEqual(state_change_saver.count, start_count+1)
        self.assertEqual(state_change_saver.saved_old.allow_on, AllowOn.NEVER)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_new.reason, "Test")

        # Changing only reason on active slot notifies too
        sut.set_slot(15, 1, allow_on=AllowOn.ALWAYS, reason="Test 2")
        self.assertEqual(state_change_saver.count, start_count+2)
        self.assertEqual(state_change_saver.saved_old.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_new.reason, "Test 2")

        # Moving out of slot notifies again
        clock.set_t(15, 15)
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count+3)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.NEVER)
        self.assertEqual(state_change_saver.saved_old.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_old.reason, "Test 2")

    def test_notifies_on_boost(self):
        clock = FakeClock(15, 0)
        state_change_saver = StateChangeSaver()
        sut = Schedule(state_change_saver.save_state_changes, clock)
        start_count = state_change_saver.count

        sut.boost(hours=1)
        self.assertEqual(state_change_saver.count, start_count+1)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_new.reason, "User boost")

        # No notify while boost is active
        for i in range(1, 59):
            clock.set_t(15, 15)
            sut.tick()
            self.assertEqual(state_change_saver.count, start_count+1)

        clock.set_t(16, 0)
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count+2)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.NEVER)
        self.assertEqual(state_change_saver.saved_old.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_old.reason, "User boost")

    def test_notifies_on_toggle(self):
        clock = FakeClock(15, 0)
        state_change_saver = StateChangeSaver()
        sut = Schedule(state_change_saver.save_state_changes, clock)
        start_count = state_change_saver.count

        sut.toggle_slot(hour=15, minute=0)
        self.assertEqual(state_change_saver.count, start_count+1)

        sut.toggle_slot(hour=15, minute=0)
        self.assertEqual(state_change_saver.count, start_count+2)

        sut.toggle_slot_by_name('15:00')
        self.assertEqual(state_change_saver.count, start_count+3, "Toggle by name didn't notify")
        sut.toggle_slot_by_name('15:0')
        self.assertEqual(state_change_saver.count, start_count+4, "Toggle by name 2 didn't notify")

    def test_notifies_on_wraparound(self):
        clock = FakeClock(23, 45)
        state_change_saver = StateChangeSaver()
        sut = Schedule(state_change_saver.save_state_changes, clock)
        start_count = state_change_saver.count

        sut.set_slot(23, 45, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(0, 0, allow_on=AllowOn.ALWAYS, reason="Test")
        sut.set_slot(0, 15, allow_on=AllowOn.ALWAYS, reason="Test 2")
        sut.set_slot(0, 30, allow_on=AllowOn.ALWAYS, reason="Test 2")

        self.assertEqual(state_change_saver.count, start_count+1)
        clock.set_t(0, 0)
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count+1)
        clock.set_t(0, 15)
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count+2)
        self.assertEqual(state_change_saver.saved_old.reason, "Test")
        self.assertEqual(state_change_saver.saved_new.reason, "Test 2")
        clock.set_t(0, 30)
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count+2)
        clock.set_t(0, 45)
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count+3)
        self.assertEqual(state_change_saver.saved_old.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.NEVER)


    def test_notifies_works_on_time_skip(self):
        clock = FakeClock(10, 0)
        state_change_saver = StateChangeSaver()
        sut = Schedule(state_change_saver.save_state_changes, clock)
        self.assertEqual(sut.tick_skipped_errors, 0)
        start_count = state_change_saver.count

        sut.boost(hours=1)
        self.assertEqual(state_change_saver.count, start_count+1)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.ALWAYS)

        clock.set_t(12, 0)
        sut.tick()
        self.assertTrue(sut.tick_skipped_errors > 0)

        # Shouldn't miss notifications even if time skips
        self.assertEqual(state_change_saver.saved_old.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.NEVER)


    def test_notifies_on_user_off(self):
        clock = FakeClock(10, 0)
        state_change_saver = StateChangeSaver()
        sut = Schedule(state_change_saver.save_state_changes, clock)
        start_count = state_change_saver.count

        sut.boost(hours=1)
        self.assertEqual(state_change_saver.count, start_count+1)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.ALWAYS)

        clock.set_t(10, 15)
        sut.tick()
        self.assertEqual(state_change_saver.count, start_count+1)

        sut.off_now()
        self.assertEqual(state_change_saver.count, start_count+2)
        self.assertEqual(state_change_saver.saved_old.allow_on, AllowOn.ALWAYS)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.NEVER)


    def test_set_now_from_rule(self):
        clock = FakeClock(11, 0)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(11, 0, allow_on=AllowOn.ALWAYS, reason="TestAlwaysOn")
        sut.set_slot(11, 15, allow_on=AllowOn.NEVER, reason="TestAlwaysOff")
        sut.set_slot(11, 30, allow_on=AllowOn.RULE, reason="TestRule")
        self.assertFalse(sut.get_slot(11, 0) .different_from(ScheduleSlot(hour=0, minute=0, allow_on=AllowOn.ALWAYS, request_on=True, reason="TestAlwaysOn")))
        self.assertFalse(sut.get_slot(11, 15).different_from(ScheduleSlot(hour=0, minute=0, allow_on=AllowOn.NEVER, request_on=False, reason="TestAlwaysOff")))
        self.assertFalse(sut.get_slot(11, 30).different_from(ScheduleSlot(hour=0, minute=0, allow_on=AllowOn.RULE, request_on=False, reason="TestRule")))

        sut.set_now_from_rule(request_on=False, reason="Test")
        self.assertFalse(sut.get_slot(11, 0) .different_from(ScheduleSlot(hour=0, minute=0, allow_on=AllowOn.ALWAYS, request_on=True, reason="TestAlwaysOn")))

        clock.set_t(11, 15)
        sut.tick()
        sut.set_now_from_rule(request_on=True, reason="Test")
        self.assertFalse(sut.get_slot(11, 15).different_from(ScheduleSlot(hour=0, minute=0, allow_on=AllowOn.NEVER, request_on=False, reason="TestAlwaysOff")))

        clock.set_t(11, 30)
        sut.tick()
        sut.set_now_from_rule(request_on=True, reason="Test")
        self.assertFalse(sut.get_slot(11, 30).different_from(ScheduleSlot(hour=0, minute=0, allow_on=AllowOn.RULE, request_on=True, reason="Test")))
        sut.set_now_from_rule(request_on=False, reason="Test2")
        self.assertFalse(sut.get_slot(11, 30).different_from(ScheduleSlot(hour=0, minute=0, allow_on=AllowOn.RULE, request_on=False, reason="Test2")))

    def test_set_now_from_rule_notifies(self):
        clock = FakeClock(11, 0)
        state_change_saver = StateChangeSaver()
        sut = Schedule(state_change_saver.save_state_changes, clock)
        start_count = state_change_saver.count

        sut.set_slot(11, 0, allow_on=AllowOn.RULE, reason="Test")
        self.assertEqual(state_change_saver.count, start_count+1)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, False)
        self.assertEqual(state_change_saver.saved_new.reason, "Test")

        sut.set_now_from_rule(request_on=True, reason="Rule")
        self.assertEqual(state_change_saver.count, start_count+2)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, True)
        self.assertEqual(state_change_saver.saved_new.reason, "Rule")

        sut.set_now_from_rule(request_on=False, reason="Rule")
        self.assertEqual(state_change_saver.count, start_count+3)
        self.assertEqual(state_change_saver.saved_new.request_on, False)

        sut.set_now_from_rule(request_on=False, reason="Rule")
        self.assertEqual(state_change_saver.count, start_count+3)

    def test_set_now_from_rule_notifies_only_once(self):
        clock = FakeClock(11, 0)
        state_change_saver = StateChangeSaver()
        sut = Schedule(state_change_saver.save_state_changes, clock)
        start_count = state_change_saver.count

        sut.set_slot(11, 0, allow_on=AllowOn.RULE, reason="Test")
        self.assertEqual(state_change_saver.count, start_count+1)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, False)
        self.assertEqual(state_change_saver.saved_new.reason, "Test")

        sut.applying_rules(True)
        sut.set_now_from_rule(request_on=True, reason="Rule")
        self.assertEqual(state_change_saver.count, start_count+1)

        sut.set_now_from_rule(request_on=False, reason="Rule2")
        self.assertEqual(state_change_saver.count, start_count+1)

        sut.set_now_from_rule(request_on=True, reason="Rule3")
        self.assertEqual(state_change_saver.count, start_count+1)

        sut.set_now_from_rule(request_on=False, reason="Rule4")
        self.assertEqual(state_change_saver.count, start_count+1)

        sut.applying_rules(False)
        self.assertEqual(state_change_saver.count, start_count+2)
        self.assertEqual(state_change_saver.saved_new.allow_on, AllowOn.RULE)
        self.assertEqual(state_change_saver.saved_new.request_on, False)
        self.assertEqual(state_change_saver.saved_new.reason, "Rule4")




if __name__ == '__main__':
    unittest.main()
