from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import copy

from zzmw_lib.service_runner import build_logger
log = build_logger("HeatingSchedule")

class AllowOn(str, Enum):
    ALWAYS = 'Always'
    NEVER = 'Never'
    RULE = 'Rule'

    @staticmethod
    def guess_value(allow_on):
        if isinstance(allow_on, AllowOn):
            return allow_on
        if isinstance(allow_on, str):
            if allow_on.lower() in ['on', 'always']:
                return AllowOn.ALWAYS
            if allow_on.lower() in ['off', 'never']:
                return AllowOn.NEVER
            if allow_on.lower() in ['rule']:
                return AllowOn.RULE
        if isinstance(allow_on, bool):
            if allow_on:
                return AllowOn.ALWAYS
            return AllowOn.NEVER

        return AllowOn.NEVER

@dataclass(frozen=False)
class ScheduleSlot:
    hour: int
    minute: int
    allow_on: AllowOn = AllowOn.NEVER
    request_on: bool = False
    reason: str = "Default"

    def dictify(self):
        return asdict(self)

    def different_from(self, o):
        return o is None or \
                self.allow_on != o.allow_on or \
                self.request_on != o.request_on or \
                self.reason != o.reason

    def reset(self):
        self.allow_on = AllowOn.NEVER
        self.request_on = False
        self.reason = "Default"

    def set_policy(self, allow_on, reason):
        self.allow_on = AllowOn.guess_value(allow_on)
        self.reason = reason
        if self.allow_on == AllowOn.ALWAYS:
            self.request_on = True
        elif self.allow_on == AllowOn.NEVER:
            self.request_on = False
        else:
            pass

    def set_from_rule(self, request_on, reason):
        if self.allow_on != AllowOn.RULE:
            return
        self.request_on = request_on
        self.reason = reason

    def toggle(self, reason):
        if self.allow_on == AllowOn.RULE:
            if self.request_on:
                self.set_policy(AllowOn.NEVER, reason)
            else:
                self.set_policy(AllowOn.ALWAYS, reason)
        elif self.allow_on == AllowOn.ALWAYS:
            self.set_policy(AllowOn.NEVER, reason)
        else:
            self.set_policy(AllowOn.ALWAYS, reason)

def _hr_mn_to_slot_idx(hour, minute):
    hour = int(hour)
    minute = int(minute)
    if hour > 23 or hour < 0:
        raise ValueError(f"Hour must be 0..23, not {hour}")
    if minute > 59 or hour < 0:
        raise ValueError(f"Minute must be 0..59, not {minute}")
    return 4*hour + int(minute / 15)

def _t_obj_to_slot_idx(t):
    return _hr_mn_to_slot_idx(t.hour, t.minute)

def _slot_to_hour(i):
    return int(i / 4)

def _slot_to_minute(i):
    return (i % 4) * 15

def hr_mn_to_slot_t(hr, mn):
    return f'{hr:02}:{mn:02}'

def slot_t_to_hr_mn(slot_t):
    """ Get hour and minute from a slot format. Slot may be 'HH:MM', bur 'H:M' will
    also be accepted """
    if ':' not in slot_t:
        raise ValueError(f"Can't parse slot format {slot_t}, expected 'HH:MM'")

    hour, minute = slot_t.split(':')
    if not hour.isdigit() or not minute.isdigit():
        raise ValueError(f"Can't parse slot format {slot_t}, expected 'HH:MM' - HH or MM aren't digits")

    hour, minute = int(hour), int(minute)
    if hour > 23 or hour < 0 or minute > 59 or minute < 0:
        raise ValueError(f"Can't parse slot format {slot_t}, expected 'HH:MM' - H or M not in range")

    return hour, minute

class Schedule:
    def __init__(self, on_state_change_cb, clock=None):
        self._clock = clock
        if self._clock is None:
            self._clock = datetime

        self._sched = [ScheduleSlot(hour=_slot_to_hour(i), minute=_slot_to_minute(i)) for i in range(24 * 4)]
        self._active_slot_idx = _t_obj_to_slot_idx(self._clock.now())
        self._applied_slot = None
        self._ignore_state_changes = False
        self.tick_skipped_errors = 0
        self._on_state_change_cb = on_state_change_cb

        self._on_state_may_change()

    def get_slot_change_time(self):
        next_slot = (self._active_slot_idx + 1) % len(self._sched)
        next_slot_hour = _slot_to_hour(next_slot)
        next_slot_minute = _slot_to_minute(next_slot)

        exp_t = self._clock.now()
        exp_t = exp_t.replace(hour=next_slot_hour)
        exp_t = exp_t.replace(minute=next_slot_minute)
        if next_slot == 0:
            exp_t = exp_t + timedelta(days=1)
        return exp_t

    def tick(self):
        """ Returns the number of advanced slots """
        now_slot = _t_obj_to_slot_idx(self._clock.now())
        if now_slot == self._active_slot_idx:
            return 0

        if now_slot == self._active_slot_idx + 1:
            self._sched[self._active_slot_idx].reset()
            self._active_slot_idx = now_slot
            self._on_state_may_change()
            return 1

        if now_slot == 0 and self._active_slot_idx == len(self._sched) - 1:
            self._sched[self._active_slot_idx].reset()
            self._active_slot_idx = now_slot
            self._on_state_may_change()
            return 1

        idx = self._active_slot_idx
        advanced_slots = 0
        # Reset all the slots we missed
        while idx != now_slot:
            self._sched[idx].reset()
            idx = (idx + 1) % len(self._sched)
            advanced_slots = advanced_slots + 1

        log.error("tick() wasn't called for %s slots. This shouldn't happen.", advanced_slots-1)
        self.tick_skipped_errors += advanced_slots-1
        self._active_slot_idx = now_slot
        self._on_state_may_change()
        return advanced_slots

    def _on_state_may_change(self):
        if self._ignore_state_changes:
            return
        active = self._sched[self._active_slot_idx]
        applied = self._applied_slot
        if active.different_from(applied):
            log.debug("State changed old=%s new=%s", applied, active)
            self._on_state_change_cb(new=active, old=applied)
            self._applied_slot = copy.copy(active)

    def set_slot(self, hour, minute, allow_on=AllowOn.NEVER, reason="User set"):
        i = _hr_mn_to_slot_idx(hour, minute)
        self._sched[i].set_policy(allow_on, reason)
        self._on_state_may_change()

    def set_now_from_rule(self, request_on, reason):
        self._sched[self._active_slot_idx].set_from_rule(request_on, reason)
        self._on_state_may_change()

    def applying_rules(self, working_through_rules):
        self._ignore_state_changes = working_through_rules
        if not working_through_rules:
            self._on_state_may_change()

    def get_now_slot(self):
        """ Returns whatever this schedule thinks now is, which may not necessarily match a wallclock """
        return self._sched[self._active_slot_idx]

    def get_slot(self, hour, minute):
        i = _hr_mn_to_slot_idx(hour, minute)
        return self._sched[i]

    def get_last_slot_hr_mn(self):
        if self._active_slot_idx == 0:
            idx = len(self._sched) - 1
        else:
            idx = self._active_slot_idx - 1
        return _slot_to_hour(idx), _slot_to_minute(idx)

    def toggle_slot(self, hour, minute, reason="User set"):
        self.get_slot(hour, minute).toggle(reason)
        self._on_state_may_change()

    def toggle_slot_by_name(self, slot_nm, reason="User set"):
        self.toggle_slot(*slot_t_to_hr_mn(slot_nm), reason)

    def boost(self, hours):
        hours = int(hours)
        if hours > 12 or hours < 0:
            raise ValueError(f"Hour must be 0..12, not {hours}")

        start_slot = self._active_slot_idx
        for i in range(hours * 4):
            j = (start_slot + i) % len(self._sched)
            if self._sched[j].allow_on != AllowOn.ALWAYS:
                self._sched[j].set_policy(AllowOn.ALWAYS, "User boost")
        self._on_state_may_change()

    OFF_NOW_MAX_HOURS = 5
    OFF_NOW_MAX_SLOTS = 4 * OFF_NOW_MAX_HOURS
    def off_now(self):
        slot = self._active_slot_idx
        turned_off = 0
        while self._sched[slot].allow_on != AllowOn.NEVER and turned_off < self.OFF_NOW_MAX_SLOTS:
            self._sched[slot].set_policy(AllowOn.NEVER, "User requested off")
            slot = (slot + 1) % len(self._sched)
            turned_off += 1
        self._on_state_may_change()

    def as_jsonifyable_dict(self):
        """ Return schedule as a list, starting with the current hour:minute slot, in a format
        that's usable to call json.dumps """
        start_slot = self._active_slot_idx
        sched = []
        for i in range(len(self._sched)):
            j = (i + start_slot) % len(self._sched)
            sched.append(self._sched[j])
        return list(map(lambda o: o.dictify(), sched))
