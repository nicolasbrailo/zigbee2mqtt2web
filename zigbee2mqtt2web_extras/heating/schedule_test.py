import unittest
from datetime import datetime

from schedule import Schedule, hr_mn_to_slot_t

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

class TestStringMethods(unittest.TestCase):
    def test_fake_clock(self):
        clock = FakeClock(hour=12, minute=0)
        self.assertEqual(clock.now().hour, 12)
        self.assertEqual(clock.now().minute, 0)

    def test_schedule_defaults_off(self):
        sut = Schedule(ignore_state_changes)
        for hr in range(24):
            for mn in range(4):
                self.assertEqual(sut.get_slot(hr, 15*mn).should_be_on, False)

    def test_schedule_fails_bad_time(self):
        sut = Schedule(ignore_state_changes)
        self.assertRaises(ValueError, sut.set_slot, 25, 15)
        self.assertRaises(ValueError, sut.set_slot, 22, 65)
        sut.set_slot(12, 12) # Test no raise

    def test_schedule_saves_on(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(12, 15, should_be_on=True, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.should_be_on, True)
        self.assertEqual(slot.reason, "Test")

    def test_schedule_saves_on_off(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(12, 15, should_be_on=True, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.should_be_on, True)
        self.assertEqual(slot.reason, "Test")
        sut.set_slot(12, 15, should_be_on=False, reason="Test 2")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.should_be_on, False)
        self.assertEqual(slot.reason, "Test 2")
        sut.set_slot(12, 18, should_be_on=True, reason="Test 2")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.should_be_on, True)
        self.assertEqual(slot.reason, "Test 2")

    def test_schedule_saves_toggle(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(12, 15, should_be_on=True, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.should_be_on, True)
        self.assertEqual(slot.reason, "Test")
        sut.toggle_slot(12, 15, reason="Toggle")
        self.assertEqual(slot.should_be_on, False)
        self.assertEqual(slot.reason, "Toggle")
        sut.toggle_slot(12, 15, reason="Toggle 2")
        self.assertEqual(slot.should_be_on, True)
        self.assertEqual(slot.reason, "Toggle 2")

    def test_schedule_saves_toggle_by_name(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(12, 15, should_be_on=True, reason="Test")
        slot = sut.get_slot(12, 15)
        self.assertEqual(slot.should_be_on, True)
        self.assertEqual(slot.reason, "Test")
        sut.toggle_slot_by_name("12:15", reason="Toggle")
        self.assertEqual(slot.should_be_on, False)
        sut.toggle_slot_by_name(hr_mn_to_slot_t(12, 15), reason="Toggle")
        self.assertEqual(slot.should_be_on, True)

        sut.toggle_slot_by_name('1:1', reason="Toggle")
        slot = sut.get_slot(1, 0)
        self.assertEqual(slot.should_be_on, True)

    def test_schedule_maps_to_quarter(self):
        sut = Schedule(ignore_state_changes)
        sut.set_slot(0, 0, should_be_on=True, reason="Test")
        self.assertEqual(sut.get_slot(0, 0).should_be_on, True)
        self.assertEqual(sut.get_slot(0, 0).reason, "Test")
        self.assertEqual(sut.get_slot(0, 1).reason, "Test")
        self.assertEqual(sut.get_slot(0, 5).reason, "Test")
        self.assertEqual(sut.get_slot(0, 8).reason, "Test")

        sut.set_slot(1, 3, should_be_on=True, reason="Test")
        self.assertEqual(sut.get_slot(1, 0).should_be_on, True)
        self.assertEqual(sut.get_slot(1, 0).reason, "Test")
        self.assertEqual(sut.get_slot(1, 15).should_be_on, False)

        sut.set_slot(2, 7, should_be_on=True, reason="Test")
        self.assertEqual(sut.get_slot(2, 0).should_be_on, True)
        self.assertEqual(sut.get_slot(2, 0).reason, "Test")
        self.assertEqual(sut.get_slot(2, 15).should_be_on, False)

        sut.set_slot(3, 12, should_be_on=True, reason="Test")
        self.assertEqual(sut.get_slot(3, 0).should_be_on, True)
        self.assertEqual(sut.get_slot(3, 0).reason, "Test")
        self.assertEqual(sut.get_slot(3, 15).should_be_on, False)

        sut.set_slot(4, 14, should_be_on=True, reason="Test")
        self.assertEqual(sut.get_slot(4, 0).should_be_on, True)
        self.assertEqual(sut.get_slot(4, 0).reason, "Test")
        self.assertEqual(sut.get_slot(4, 15).should_be_on, False)

    def test_schedule_maps_to_quarter_exahustive(self):
        sut = Schedule(ignore_state_changes)
        for i in range(15):
            sut.set_slot(i, i, should_be_on=True, reason="Test")

        for hr in range(15):
            for mn in range(15):
                slot = sut.get_slot(hr, mn)
                self.assertEqual(slot.should_be_on, True)
                self.assertEqual(slot.reason, "Test")
            for mn in range(45):
                slot = sut.get_slot(hr, 15+mn)
                self.assertEqual(slot.should_be_on, False)
                self.assertEqual(slot.reason, "Default")

    def test_schedule_saves_all_quarters_hour_schedule(self):
        sut = Schedule(ignore_state_changes)
        slot = sut.set_slot(12, 0, True)
        slot = sut.set_slot(12, 15, True)
        slot = sut.set_slot(12, 30, True)
        slot = sut.set_slot(12, 45, True)
        for hr in range(24):
            for mn in range(4):
                if hr == 12:
                    slot = sut.get_slot(hr, 15*mn)
                    self.assertEqual(slot.should_be_on, True)
                else:
                    self.assertEqual(sut.get_slot(hr, 15*mn).should_be_on, False)

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
                    self.assertEqual(slot.should_be_on, True, f"Expected slot {hr}:{15*mn} to be active")
                    self.assertEqual(slot.reason, "User boost")
                else:
                    self.assertEqual(sut.get_slot(hr, 15*mn).should_be_on, False, f"Expected slot {hr}:{15*mn} to be not active")

    def test_slot_set_moves_forward(self):
        clock = FakeClock(10, 20)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(10, 20, should_be_on=True, reason="Test")
        self.assertEqual(sut.get_slot(10, 15).should_be_on, True)

        clock.set_t(10, 30)
        self.assertEqual(sut.tick(), True)
        self.assertEqual(sut.get_slot(10, 15).should_be_on, False)

    def test_slot_ticks_are_idempotent(self):
        clock = FakeClock(10, 20)
        sut = Schedule(ignore_state_changes, clock)
        clock.set_t(10, 30)
        self.assertEqual(sut.tick(), True)
        self.assertEqual(sut.tick(), False)

    def test_slot_set_moves_forward_wraparound(self):
        clock = FakeClock(23, 50)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(23, 55, should_be_on=True, reason="Test")
        self.assertEqual(sut.get_slot(23, 45).should_be_on, True)

        clock.set_t(0, 0)
        sut.tick()
        self.assertEqual(sut.get_slot(23, 55).should_be_on, False)

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
        sut.set_slot(10, 15, should_be_on=True, reason="Test")
        sut.set_slot(10, 30, should_be_on=True, reason="Test")
        sut.set_slot(10, 45, should_be_on=True, reason="Test")

        clock.set_t(11, 30)
        sut.tick()
        self.assertEqual(sut.tick_skipped_errors, 4)
        self.assertEqual(sut.get_slot(10, 15).should_be_on, False)
        self.assertEqual(sut.get_slot(10, 30).should_be_on, False)
        self.assertEqual(sut.get_slot(10, 45).should_be_on, False)

    def test_slot_set_moves_forward_wraparound_preserves(self):
        clock = FakeClock(23, 50)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(23, 55, should_be_on=True, reason="Test")
        sut.set_slot(0, 0, should_be_on=True, reason="Test")
        sut.set_slot(0, 15, should_be_on=True, reason="Test")
        sut.set_slot(0, 30, should_be_on=True, reason="Test")
        self.assertEqual(sut.get_slot(23, 45).should_be_on, True)
        self.assertEqual(sut.get_slot(0, 0).should_be_on, True)
        self.assertEqual(sut.get_slot(0, 15).should_be_on, True)
        self.assertEqual(sut.get_slot(0, 30).should_be_on, True)

        clock.set_t(0, 0)
        sut.tick()
        self.assertEqual(sut.get_slot(23, 45).should_be_on, False)
        self.assertEqual(sut.get_slot(0, 0).should_be_on, True)
        self.assertEqual(sut.get_slot(0, 15).should_be_on, True)
        self.assertEqual(sut.get_slot(0, 30).should_be_on, True)

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
                    self.assertEqual(slot.should_be_on, True, f"Expected slot {hr}:{15*mn} to be active")
                    self.assertEqual(slot.reason, "User boost")
                else:
                    self.assertEqual(sut.get_slot(hr, 15*mn).should_be_on, False, f"Expected slot {hr}:{15*mn} to be not active")

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
                    self.assertEqual(slot.should_be_on, True, f"Expected slot {hr}:{15*mn} to be active")
                    self.assertEqual(slot.reason, "User boost")
                else:
                    self.assertEqual(sut.get_slot(hr, 15*mn).should_be_on, False, f"Expected slot {hr}:{15*mn} to be not active")

    def test_off_now(self):
        clock = FakeClock(16, 0)
        sut = Schedule(ignore_state_changes, clock)
        sut.boost(hours=1)
        sut.set_slot(17, 15, should_be_on=True, reason="Test")
        self.assertEqual(sut.get_slot(16, 0).should_be_on, True)
        self.assertEqual(sut.get_slot(16, 15).should_be_on, True)
        self.assertEqual(sut.get_slot(16, 30).should_be_on, True)
        self.assertEqual(sut.get_slot(16, 45).should_be_on, True)
        self.assertEqual(sut.get_slot(17, 15).should_be_on, True)
        sut.off_now()
        self.assertEqual(sut.get_slot(16, 0).should_be_on, False)
        self.assertEqual(sut.get_slot(16, 0).reason, "User requested off")
        self.assertEqual(sut.get_slot(16, 15).should_be_on, False)
        self.assertEqual(sut.get_slot(16, 15).reason, "User requested off")
        self.assertEqual(sut.get_slot(16, 30).should_be_on, False)
        self.assertEqual(sut.get_slot(16, 30).reason, "User requested off")
        self.assertEqual(sut.get_slot(16, 45).should_be_on, False)
        self.assertEqual(sut.get_slot(16, 45).reason, "User requested off")
        # Disjoint slots shouldn't change
        self.assertEqual(sut.get_slot(17, 15).should_be_on, True)
        self.assertEqual(sut.get_slot(17, 15).reason, "Test")

    def test_off_now_wraps(self):
        clock = FakeClock(23, 30)
        sut = Schedule(ignore_state_changes, clock)
        sut.boost(hours=1)
        self.assertEqual(sut.get_slot(23, 30).should_be_on, True)
        self.assertEqual(sut.get_slot(23, 45).should_be_on, True)
        self.assertEqual(sut.get_slot(0, 0).should_be_on, True)
        self.assertEqual(sut.get_slot(0, 15).should_be_on, True)
        sut.off_now()
        self.assertEqual(sut.get_slot(23, 30).should_be_on, False)
        self.assertEqual(sut.get_slot(23, 30).reason, "User requested off")
        self.assertEqual(sut.get_slot(23, 45).should_be_on, False)
        self.assertEqual(sut.get_slot(23, 45).reason, "User requested off")
        self.assertEqual(sut.get_slot(0, 0).should_be_on, False)
        self.assertEqual(sut.get_slot(0, 0).reason, "User requested off")
        self.assertEqual(sut.get_slot(0, 15).should_be_on, False)
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

    def test_schedule_as_table(self):
        clock = FakeClock(15, 0)
        sut = Schedule(ignore_state_changes, clock)
        sut.set_slot(16, 10, should_be_on=True, reason="Test")
        sut.set_slot(17, 30, should_be_on=True, reason="Test")
        t = sut.as_table()
        self.assertEqual(list(t.items())[0][0], '15:00')
        self.assertEqual(t['15:00'].should_be_on, False)
        self.assertEqual(t['16:00'].should_be_on, True)
        self.assertEqual(t['17:30'].should_be_on, True)

    def test_notifies_state_changes(self):
        saved_new = None
        saved_old = None
        count = 0
        def save_state_changes(new, old):
            nonlocal count
            nonlocal saved_new
            nonlocal saved_old
            saved_new = new
            saved_old = old
            count += 1

        clock = FakeClock(15, 0)
        sut = Schedule(save_state_changes, clock)
        sut.set_slot(15, 30, should_be_on=True, reason="Test")

        clock.set_t(15, 15)
        sut.tick()
        self.assertEqual(count, 1)

        clock.set_t(15, 30)
        sut.tick()
        self.assertEqual(count, 2)
        self.assertEqual(saved_old.should_be_on, False)
        self.assertEqual(saved_new.should_be_on, True)
        self.assertEqual(saved_new.reason, "Test")

        for i in range(14):
            clock.set_t(15, 30+i)
            sut.tick()
            self.assertEqual(count, 2)

        clock.set_t(15, 45)
        sut.tick()
        self.assertEqual(count, 3)
        self.assertEqual(saved_new.should_be_on, False)
        self.assertEqual(saved_old.should_be_on, True)
        self.assertEqual(saved_old.reason, "Test")

    def test_notifies_on_object_ctr(self):
        saved_new = None
        saved_old = None
        count = 0
        def save_state_changes(new, old):
            nonlocal count
            nonlocal saved_new
            nonlocal saved_old
            saved_new = new
            saved_old = old
            count += 1

        clock = FakeClock(15, 0)
        sut = Schedule(save_state_changes, clock)
        self.assertEqual(count, 1)
        self.assertEqual(saved_old, None)
        self.assertEqual(saved_new.should_be_on, False)
        self.assertEqual(saved_new.reason, "Default")


    def test_notifies_when_changing_current_slot(self):
        saved_new = None
        saved_old = None
        count = 0
        def save_state_changes(new, old):
            nonlocal count
            nonlocal saved_new
            nonlocal saved_old
            saved_new = new
            saved_old = old
            count += 1

        clock = FakeClock(15, 0)
        sut = Schedule(save_state_changes, clock)

        # Changing non active slot doesn't notify
        start_count = count
        sut.set_slot(16, 5, should_be_on=True, reason="Test")
        self.assertEqual(count, start_count)

        # Changing active slot does notify
        sut.set_slot(15, 5, should_be_on=True, reason="Test")
        self.assertEqual(count, start_count+1)
        self.assertEqual(saved_old.should_be_on, False)
        self.assertEqual(saved_new.should_be_on, True)
        self.assertEqual(saved_new.reason, "Test")

        # Changing only reason on active slot notifies too
        sut.set_slot(15, 1, should_be_on=True, reason="Test 2")
        self.assertEqual(count, start_count+2)
        self.assertEqual(saved_old.should_be_on, True)
        self.assertEqual(saved_new.should_be_on, True)
        self.assertEqual(saved_new.reason, "Test 2")

        # Moving out of slot notifies again
        clock.set_t(15, 15)
        sut.tick()
        self.assertEqual(count, start_count+3)
        self.assertEqual(saved_new.should_be_on, False)
        self.assertEqual(saved_old.should_be_on, True)
        self.assertEqual(saved_old.reason, "Test 2")

    def test_notifies_on_boost(self):
        saved_new = None
        saved_old = None
        count = 0
        def save_state_changes(new, old):
            nonlocal count
            nonlocal saved_new
            nonlocal saved_old
            saved_new = new
            saved_old = old
            count += 1

        clock = FakeClock(15, 0)
        sut = Schedule(save_state_changes, clock)
        start_count = count

        sut.boost(hours=1)
        self.assertEqual(count, start_count+1)
        self.assertEqual(saved_new.should_be_on, True)
        self.assertEqual(saved_new.reason, "User boost")

        # No notify while boost is active
        for i in range(1, 59):
            clock.set_t(15, 15)
            sut.tick()
            self.assertEqual(count, start_count+1)

        clock.set_t(16, 0)
        sut.tick()
        self.assertEqual(count, start_count+2)
        self.assertEqual(saved_new.should_be_on, False)
        self.assertEqual(saved_old.should_be_on, True)
        self.assertEqual(saved_old.reason, "User boost")

    def test_notifies_on_wraparound(self):
        saved_new = None
        saved_old = None
        count = 0
        def save_state_changes(new, old):
            nonlocal count
            nonlocal saved_new
            nonlocal saved_old
            saved_new = new
            saved_old = old
            count += 1

        clock = FakeClock(23, 45)
        sut = Schedule(save_state_changes, clock)
        start_count = count

        sut.set_slot(23, 45, should_be_on=True, reason="Test")
        sut.set_slot(0, 0, should_be_on=True, reason="Test")
        sut.set_slot(0, 15, should_be_on=True, reason="Test 2")
        sut.set_slot(0, 30, should_be_on=True, reason="Test 2")

        self.assertEqual(count, start_count+1)
        clock.set_t(0, 0)
        sut.tick()
        self.assertEqual(count, start_count+1)
        clock.set_t(0, 15)
        sut.tick()
        self.assertEqual(count, start_count+2)
        self.assertEqual(saved_old.reason, "Test")
        self.assertEqual(saved_new.reason, "Test 2")
        clock.set_t(0, 30)
        sut.tick()
        self.assertEqual(count, start_count+2)
        clock.set_t(0, 45)
        sut.tick()
        self.assertEqual(count, start_count+3)
        self.assertEqual(saved_old.should_be_on, True)
        self.assertEqual(saved_new.should_be_on, False)


    def test_notifies_works_on_time_skip(self):
        saved_new = None
        saved_old = None
        count = 0
        def save_state_changes(new, old):
            nonlocal count
            nonlocal saved_new
            nonlocal saved_old
            saved_new = new
            saved_old = old
            count += 1

        clock = FakeClock(10, 0)
        sut = Schedule(save_state_changes, clock)
        self.assertEqual(sut.tick_skipped_errors, 0)
        start_count = count

        sut.boost(hours=1)
        self.assertEqual(count, start_count+1)
        self.assertEqual(saved_new.should_be_on, True)

        clock.set_t(12, 0)
        sut.tick()
        self.assertTrue(sut.tick_skipped_errors > 0)

        # Shouldn't miss notifications even if time skips
        self.assertEqual(saved_old.should_be_on, True)
        self.assertEqual(saved_new.should_be_on, False)


    def test_notifies_on_user_off(self):
        saved_new = None
        saved_old = None
        count = 0
        def save_state_changes(new, old):
            nonlocal count
            nonlocal saved_new
            nonlocal saved_old
            saved_new = new
            saved_old = old
            count += 1

        clock = FakeClock(10, 0)
        sut = Schedule(save_state_changes, clock)
        start_count = count

        sut.boost(hours=1)
        self.assertEqual(count, start_count+1)
        self.assertEqual(saved_new.should_be_on, True)

        clock.set_t(10, 15)
        sut.tick()
        self.assertEqual(count, start_count+1)

        sut.off_now()
        self.assertEqual(count, start_count+2)
        self.assertEqual(saved_old.should_be_on, True)
        self.assertEqual(saved_new.should_be_on, False)


if __name__ == '__main__':
    unittest.main()
