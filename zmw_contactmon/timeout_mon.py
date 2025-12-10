""" Monitors if contact sensors are open for too long (eg someone forgot window open) """
from datetime import datetime, timedelta
from zzmw_lib.service_runner import build_logger

log = build_logger("ContactTimeoutMonitor")

class TimeoutMonitor:
    """ Timeout monitor for contact sensors: when a sensor transitions to non-normal state, it will start a countdown.
    When the countdown finishes, it will execute timeout actions for this sensor. """
    def __init__(self, sched, executor, actions_on_sensor_change):
        # There is a global timeout for non-normal transitions (timeout if a door remains open too long)
        # This could be done per sensor, but global works for now
        self._sched = sched
        self._exec = executor
        self._timeout_jobs = {}
        self._actions_on_sensor_change = actions_on_sensor_change

    def notify_change(self, thing, entering_non_normal):
        """ Notify a sensor reported a transition """
        if 'timeout_secs' not in self._actions_on_sensor_change[thing.name]:
            # This sensor has no timeout
            return

        if entering_non_normal and thing.name in self._timeout_jobs:
            log.debug("Sensor %s reports non-normal state, but we are already monitoring its timeout", thing.name)
            return

        if entering_non_normal:
            # schedule timeout to detect if sensor never returns not normal
            timeout_secs = self._actions_on_sensor_change[thing.name]['timeout_secs']
            log.debug("Sensor %s entered non-normal state, monitoring timeout (%d seconds)", thing.name, timeout_secs)
            job = self._sched.add_job(
                    lambda: self._on_sensor_non_normal_timeout(thing.name),
                    'date',
                    run_date=datetime.now() + timedelta(seconds=timeout_secs))
            self._timeout_jobs[thing.name] = job
            return

        # entering_non_normal must be false here
        if thing.name in self._timeout_jobs:
            log.debug("Sensor %s entered normal state, will cancel timeout job", thing.name)
            self._cancel_timeout(thing.name)
        else:
            # If we are here, a sensor reports normal state but we are already not monitoring it. Ignore.
            pass

    def _cancel_timeout(self, thing_name):
        if thing_name not in self._timeout_jobs:
            return
        try:
            self._sched.remove_job(self._timeout_jobs[thing_name].id)
        except Exception:  # pylint: disable=broad-except
            # Job removal can fail if it was already removed (triggered while we were here) or if there was
            # no job (eg getting a closed-report for a sensor that was already closed)
            pass
        del self._timeout_jobs[thing_name]

    def _on_sensor_non_normal_timeout(self, thing_name):
        self._cancel_timeout(thing_name)
        log.info("Sensor %s timed out (remained in non-normal state for more than %d seconds)",
                 thing_name, self._actions_on_sensor_change[thing_name]['timeout_secs'])
        self._exec.on_transition(thing_name, 'timeout')
