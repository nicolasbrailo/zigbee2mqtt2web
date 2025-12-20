from datetime import datetime

from zzmw_lib.logs import build_logger

log = build_logger("DispenseTracking")

def _ensure_feeding_mode(cat_feeder, correct_if_bad):
    curr_mode = cat_feeder.get('mode')
    if curr_mode == 'schedule':
        # Happy path
        return

    if not correct_if_bad:
        # Bad config, but we weren't asked to fix
        log.error("Food dispenser '%s' not following schedule, feeding source is '%s': "
                  "if this service breaks, your cat will be hangry", cat_feeder.name, curr_mode)
        return

    if curr_mode is None:
        # Likely service boot-up, and we just didn't know this value. Very likely benign.
        log.info("Configuring '%s' for schedule-based dispensing", cat_feeder.name)
    else:
        # This may be a problem: something else could have set the mode, which is bad
        log.info("Food dispenser '%s' was configured to not follow a schedule (feeding source was '%s'). "
                 "If you see this message often, something else may be controling this unit.",
                 cat_feeder.name, curr_mode)

    # Ensure setting
    cat_feeder.set('mode', 'schedule')

def _ensure_schedule(cat_feeder, target_schedule, correct_if_bad):
    def _normalize_schedule(schedule):
        """ Normalize schedule entries: we need to use 'serving_size' to set the value, unit reports back 'size'."""
        normalized = []
        for entry in schedule:
            norm_entry = {
                'days': entry['days'],
                'hour': entry['hour'],
                'minute': entry['minute'],
                'size': entry.get('size', entry.get('serving_size')),
            }
            normalized.append(norm_entry)
        return normalized

    curr_schedule = cat_feeder.get('schedule')
    normalized_target = _normalize_schedule(target_schedule)

    if curr_schedule == normalized_target:
        # Happy path
        return

    if not correct_if_bad:
        # Bad config, but we weren't asked to fix
        log.error("Food dispenser '%s' has unexpected schedule, your cat will be fed following multiple schedules\n"
                  " * Schedule here: %s \n"
                  " * Schedule in the unit: %s",
                  cat_feeder.name, normalized_target, curr_schedule)
        return

    if curr_schedule is None:
        log.info("Configuring '%s' feeding schedule", cat_feeder.name)
    else:
        log.info("Updating food dispenser '%s' schedule", cat_feeder.name)

    cat_feeder.set('schedule', normalized_target)

class ConfigEnforcer:
    def __init__(self, backoff_secs, schedule):
        self._ensure_config_backoff_secs = backoff_secs
        self._ensure_config_last_run = None
        self._schedule = schedule

    def ensure_config(self, cat_feeder, correct_if_bad=False):
        # Check if we ran ensure_config recently: when we set the config, the unit will reply with messages back that
        # may contain partial config states, or other config that we have yet to set. Skipping messages here for a 
        # small time will prevent message loops and log noise.
        now = datetime.now()
        if self._ensure_config_last_run is not None:
            elapsed = (now - self._ensure_config_last_run).total_seconds()
            if elapsed < self._ensure_config_backoff_secs:
                return
        self._ensure_config_last_run = now

        _ensure_feeding_mode(cat_feeder, correct_if_bad)
        _ensure_schedule(cat_feeder, self._schedule.get_schedule(), correct_if_bad)
