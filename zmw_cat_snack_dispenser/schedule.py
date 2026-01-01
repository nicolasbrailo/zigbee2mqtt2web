from datetime import datetime
import threading

from zzmw_lib.logs import build_logger

log = build_logger("DispensingSchedule")

_VALID_DAYS = ['everyday', 'workdays', 'weekend', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun',
               'mon-wed-fri-sun', 'tue-thu-sat']

def _days_to_apscheduler(days):
    """Convert Z2M schedule days format to APScheduler day_of_week format. Config will be in Z2M format. """
    if days not in _VALID_DAYS:
        raise ValueError(f"Invalid days value '{days}', must be one of: {_VALID_DAYS}")
    if days == 'everyday':
        return None
    if days == 'workdays':
        return 'mon-fri'
    if days == 'weekend':
        return 'sat,sun'
    if days == 'mon-wed-fri-sun':
        return 'mon,wed,fri,sun'
    if days == 'tue-thu-sat':
        return 'tue,thu,sat'
    # Single day values (mon, tue, wed, thu, fri, sat, sun) map directly
    return days


def validate_schedule_config(feeding_schedule, tolerance_secs):
    """Validate the feeding schedule configuration."""
    if not isinstance(feeding_schedule, list):
        raise ValueError("feeding_schedule must be a list")

    required_keys = {'days', 'hour', 'minute', 'serving_size'}
    for i, schedule in enumerate(feeding_schedule):
        if not isinstance(schedule, dict):
            raise ValueError(f"Schedule entry {i} must be a dictionary")

        missing_keys = required_keys - set(schedule.keys())
        if missing_keys:
            raise ValueError(f"Schedule entry {i} missing required keys: {missing_keys}")

        if schedule['days'] not in _VALID_DAYS:
            raise ValueError(f"Schedule entry {i} has invalid days value '{schedule['days']}', "
                             f"must be one of: {_VALID_DAYS}")

        hour = schedule['hour']
        if not isinstance(hour, int) or hour < 0 or hour > 23:
            raise ValueError(f"Schedule entry {i} has invalid hour '{hour}', must be an integer 0-23")

        minute = schedule['minute']
        if not isinstance(minute, int) or minute < 0 or minute > 59:
            raise ValueError(f"Schedule entry {i} has invalid minute '{minute}', must be an integer 0-59")

    # Check that no two schedules are within tolerance_secs of each other
    for i, sched_a in enumerate(feeding_schedule):
        time_a_secs = sched_a['hour'] * 3600 + sched_a['minute'] * 60
        for j, sched_b in enumerate(feeding_schedule):
            if i >= j:
                continue
            time_b_secs = sched_b['hour'] * 3600 + sched_b['minute'] * 60
            diff_secs = abs(time_a_secs - time_b_secs)
            if diff_secs <= tolerance_secs:
                raise ValueError(
                    f"Schedule entries {i} ({sched_a['hour']:02d}:{sched_a['minute']:02d}) and "
                    f"{j} ({sched_b['hour']:02d}:{sched_b['minute']:02d}) are within "
                    f"{tolerance_secs}s tolerance of each other ({diff_secs}s apart)"
                )

class DispensingSchedule:
    """ We don't want to control the unit from this service: instead, we want the unit to trigger on its own schedule,
    and we want to monitor it from here. That is so that if this service dies, the unit will continue to dispense
    food. To do this, we expect this object to be called when a dispense event is triggered. If the dispense event
    fails to trigger, a timeout will expire on this service, and we will try to force a dispense event. """
    def __init__(self, cat_feeder_name, history, cb_emergency_dispense, feeding_schedule, tolerance_secs, scheduler):
        validate_schedule_config(feeding_schedule, tolerance_secs)

        self._cat_feeder_name = cat_feeder_name
        self._snack_history = history
        self._cb_emergency_dispense = cb_emergency_dispense
        self._feeding_schedule = feeding_schedule
        self._tolerance_secs = tolerance_secs
        self._pending_check_timers = {}  # key: (hour, minute), value: Timer or None (sentinel for pre-fulfilled)
        self._timers_lock = threading.Lock()

        self._scheduler = scheduler
        for schedule in self._feeding_schedule:
            day_of_week = _days_to_apscheduler(schedule['days'])
            sched_hour = schedule['hour']
            sched_minute = schedule['minute']
            serving_size = schedule['serving_size']
            self._scheduler.add_job(
                lambda h=sched_hour, m=sched_minute, ss=serving_size: self._start_fulfillment_check(h, m, ss),
                'cron',
                day_of_week=day_of_week,
                hour=sched_hour,
                minute=sched_minute,
            )

    def get_schedule(self):
        return self._feeding_schedule

    def _start_fulfillment_check(self, scheduled_hour, scheduled_minute, serving_size):
        """ Called at the exact scheduled time. Starts a timer that will check if the event
        was fulfilled after tolerance_secs. """
        key = (scheduled_hour, scheduled_minute)

        with self._timers_lock:
            if key in self._pending_check_timers:
                if self._pending_check_timers[key] is None:
                    # Sentinel: event was already fulfilled before scheduled time (early trigger)
                    # This can happen if there are small differences in clock between the unit and the server
                    del self._pending_check_timers[key]
                    return
                # Cancel any existing timer for this slot (shouldn't happen, but just in case)
                self._pending_check_timers[key].cancel()

            self._pending_check_timers[key] = threading.Timer(
                self._tolerance_secs,
                self._ensure_dispense_registered,
                args=[scheduled_hour, scheduled_minute, serving_size]
            )
            self._pending_check_timers[key].start()

    def register_schedule_triggered(self, portions_dispensed, weight_dispensed):
        """ Called when the unit reports a dispensing event that triggered on schedule.
        Find the closest scheduled event within tolerance and mark it as fulfilled. """
        now = datetime.now()
        closest_schedule = None
        closest_diff_secs = None

        for schedule in self._feeding_schedule:
            # Calculate difference to event that just triggered (can be negative if we're before scheduled time)
            scheduled_today = now.replace(hour=schedule['hour'], minute=schedule['minute'], second=0, microsecond=0)
            diff_secs = abs((now - scheduled_today).total_seconds())

            # Check if within tolerance (before or after)
            if diff_secs <= self._tolerance_secs:
                if closest_diff_secs is not None and closest_schedule is not None:
                    log.error("Ambiguous match: event matches both %02d:%02d and %02d:%02d. "
                              "Config validation should have prevented this. There is a bug in this service.",
                              closest_schedule['hour'], closest_schedule['minute'],
                              schedule['hour'], schedule['minute'])
                if closest_diff_secs is None or diff_secs < closest_diff_secs:
                    closest_diff_secs = diff_secs
                    closest_schedule = schedule

        if closest_schedule is None:
            # We can't match this dispense event to any known schedule
            self._snack_history.register_unmatched_scheduled_dispense(portions_dispensed, weight_dispensed)
        else:
            # Cancel pending check timer since event was fulfilled
            key = (closest_schedule['hour'], closest_schedule['minute'])
            with self._timers_lock:
                if key in self._pending_check_timers:
                    timer = self._pending_check_timers[key]
                    if timer is not None:
                        timer.cancel()
                    del self._pending_check_timers[key]
                else:
                    # No timer yet - event triggered before scheduled time
                    # Set sentinel so _start_fulfillment_check knows to skip
                    self._pending_check_timers[key] = None
            self._snack_history.register_scheduled_dispense_on_time(portions_dispensed, weight_dispensed)

    def _ensure_dispense_registered(self, scheduled_hour, scheduled_minute, serving_size):
        """ This will be triggered $tolerance_seconds after the scheduled dispense event should fire.
        If the event was fulfilled, the timer would have been cancelled and this won't run.
        If we get here, the event was NOT fulfilled. """
        key = (scheduled_hour, scheduled_minute)

        # Clean up the timer reference (it has already fired)
        with self._timers_lock:
            if key in self._pending_check_timers:
                del self._pending_check_timers[key]

        # Event was not fulfilled
        self._snack_history.register_missed_scheduled_dispense(scheduled_hour, scheduled_minute, self._tolerance_secs)
        self._cb_emergency_dispense(source="Forced by missed schedule", serving_size=serving_size)
