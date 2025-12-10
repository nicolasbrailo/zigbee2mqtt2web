"""Systemd journal monitoring for service errors."""
import os
import signal
import threading
from datetime import datetime

from dateutil import parser
from systemd import journal

from zzmw_lib.service_runner import build_logger

log = build_logger("JournalMonitor")

class JournalMonitor:
    """Monitors systemd journal for warnings and errors from specified services"""

    def __init__(self, max_errors, on_error_logged, own_service_name,
                 rate_limit_window_mins=5, on_rate_limit=None):
        """
        Initialize the journal monitor.

        Args:
            max_errors: Maximum number of recent errors to store
            on_error_logged: Callback function called when a warning or error log is found.
            own_service_name: Name of this service to exclude from monitoring (prevents error loops).
            rate_limit_window_mins: If oldest error in FIFO is younger than this, enter rate limiting for
                                    rate_limit_window_mins.
            on_rate_limit: callback when rate limiting is triggered.
        """
        self._recent_errors = []
        self._recent_errors_lock = threading.RLock()  # Protects _recent_errors from concurrent access
        self._max_errors = max_errors
        self._journal_thread = None
        self._journal_stop_event = threading.Event()
        self._monitored_services = set()  # Services currently being monitored by journal thread
        self._journal_restart_timer = None  # Timer for delayed restart
        self._on_error_log_callback = on_error_logged
        self._own_service_name = own_service_name

        # Rate limiting
        self._rate_limit_window_mins = rate_limit_window_mins
        self._rate_limit_pause_mins = rate_limit_window_mins
        self._on_rate_limit_callback = on_rate_limit
        self._rate_limiting_active = False
        self._rate_limit_resume_timer = None

    def get_recent_errors(self):
        """
        Get list of recent errors from monitored services.

        Thread-safe method that returns a copy of the error list to avoid
        concurrent modification issues.

        Returns:
            List of error event dicts with keys: service, priority, priority_name,
            message, timestamp
        """
        with self._recent_errors_lock:
            return self._recent_errors.copy()

    def monitor_unit(self, service_name):
        """
        Schedule adding a service to monitoring. If the service is already being monitored,
        this is a no-op. Otherwise, schedules a journal monitor restart after a delay.
        """
        if service_name == self._own_service_name:
            # Skip monitoring our own service to prevent error loops
            return

        if service_name in self._monitored_services:
            # Already monitoring
            return

        self._monitored_services.add(service_name)

        # Cancel any existing pending restart
        if self._journal_restart_timer is not None:
            self._journal_restart_timer.cancel()
            log.debug("Cancelled pending journal monitor restart, rescheduling...")

        restart_delay_secs = 3
        self._journal_restart_timer = threading.Timer(restart_delay_secs, self._restart_monitor)
        self._journal_restart_timer.daemon = True
        self._journal_restart_timer.start()
        log.info("Service %s up, journal monitor will restart in %d seconds...", service_name, restart_delay_secs)

    def _restart_monitor(self):
        # Stop existing thread if running
        if self._journal_thread and self._journal_thread.is_alive():
            log.info("Journal monitor is restarting...")
            self._journal_stop_event.set()
            self._journal_thread.join(timeout=5) # Timeout must be higher than wait time in journal loop
            if self._journal_thread.is_alive():
                log.critical("Journal monitor thread did not stop within timeout. Killing process to restart service.")
                os.kill(os.getpid(), signal.SIGTERM)
                return

        # Update the set of monitored services
        self._journal_stop_event.clear()
        self._journal_thread = threading.Thread(target=self._monitor_journal_loop, daemon=True)
        self._journal_thread.start()
        log.info("Started journal monitoring for %d services: %s",
                    len(self._monitored_services), ', '.join(self._monitored_services))

    def stop(self):
        """
        Stop the journal monitor thread gracefully.
        """
        log.info("Stopping journal monitor...")

        if self._journal_restart_timer is not None:
            self._journal_restart_timer.cancel()
            self._journal_restart_timer = None

        if self._rate_limit_resume_timer is not None:
            self._rate_limit_resume_timer.cancel()
            self._rate_limit_resume_timer = None

        if self._journal_thread and self._journal_thread.is_alive():
            self._journal_stop_event.set()
            self._journal_thread.join(timeout=5)
            if self._journal_thread.is_alive():
                log.warning("Journal monitor thread did not stop gracefully")


    def _monitor_journal_loop(self):
        """Main loop that monitors the systemd journal for errors"""
        try:
            if len(self._monitored_services) == 0:
                log.info("No service to monitor yet, journal monitor exiting")
                return

            try:
                j = journal.Reader()
                j.this_boot()
                j.log_level(journal.LOG_WARNING)  # WARNING and above (WARNING, ERR, CRIT, ALERT, EMERG)
            except (OSError, RuntimeError):
                log.error(
                    "Failed to initialize journal reader. Check permissions and systemd-journal installation.",
                    exc_info=True
                )
                return

            # Add filters for each service
            for service_name in self._monitored_services:
                j.add_match(_SYSTEMD_UNIT=f"{service_name}.service")
                log.info("Monitoring journal for %s ", service_name)

            j.seek_tail()
            j.get_previous()  # Skip to end, only monitor new entries

            log.info("Now monitoring Journal")
            # Use wait() with timeout to allow checking stop event
            while not self._journal_stop_event.is_set():
                if j.wait(4):  # Wait up to 4 seconds for new entries
                    for entry in j:
                        self._handle_log(entry)

            log.info("Journal monitor stopped")
        except BaseException: # pylint: disable=broad-exception-caught
            # This may be a bug (eg journal package changed interface?) so we odn't want to restart
            # the thread (or the service) here, as it may lead to a crash loop
            log.critical("Journal monitoring thread crashed, won't restart", exc_info=True)

    def _handle_log(self, entry):
        """Process a warning or error log entry from the journal"""
        if self._rate_limiting_active:
            return

        # Extract timestamp from journal entry (falls back to current time if not available)
        # Journal timestamps are datetime objects when retrieved via python-systemd
        journal_timestamp = entry.get('__REALTIME_TIMESTAMP', entry.get('_SOURCE_REALTIME_TIMESTAMP'))
        if journal_timestamp and isinstance(journal_timestamp, datetime):
            timestamp = journal_timestamp.isoformat()
        else:
            timestamp = datetime.now().isoformat()

        priority = entry.get('PRIORITY', 5)

        error_event = {
            'service': entry.get('_SYSTEMD_UNIT', 'unknown').replace('.service', ''),
            'priority': entry.get('PRIORITY'),
            'priority_name': ['EMERG', 'ALERT', 'CRIT', 'ERR', 'WARNING'][min(priority, 4)],
            'message': entry.get('MESSAGE', ''),
            'timestamp': timestamp,
        }

        # Store in memory (keep last N errors) - thread-safe
        with self._recent_errors_lock:
            self._recent_errors.append(error_event)
            if len(self._recent_errors) > self._max_errors:
                oldest_error = self._recent_errors.pop(0)
                if self._should_throttle_logs(oldest_error):
                    return

        # Skip our own service logs to prevent error loops
        if error_event['service'] == self._own_service_name:
            return

        # Filter for warning and above: WARNING(4), ERR(3), CRIT(2), ALERT(1), EMERG(0)
        if priority is not None and priority <= 4:
            try:
                self._on_error_log_callback(error_event)
            except BaseException: # pylint: disable=broad-exception-caught
                log.error("Error in critical log callback", exc_info=True)

    def _should_throttle_logs(self, oldest_error):
        """ If we are getting error-spammed, keeping the newest error is probably not useful.
        If this happens, ignore new errors for a few minutes """
        if self._rate_limiting_active:
            log.error(
                "Rate limit checking when rate limiting already active. "
                "We shouldn't be checking logs while ratelimiting"
            )
            return True

        try:
            oldest_timestamp = parser.isoparse(oldest_error['timestamp'])
            age_minutes = (datetime.now(oldest_timestamp.tzinfo) - oldest_timestamp).total_seconds() / 60
        except (ValueError, TypeError):
            log.error("Error checking rate limit, last log entry has invalid date", exc_info=True)
            return False

        if age_minutes > self._rate_limit_window_mins:
            # Oldest entry was more than rate limit window, no need to rate limit
            return False

        # Gather stats on which services are generating errors
        service_error_counts = {}
        with self._recent_errors_lock:
            for error in self._recent_errors:
                service = error.get('service', 'unknown')
                service_error_counts[service] = service_error_counts.get(service, 0) + 1

        # Sort by count descending, skip services with no errors
        sorted_services = sorted(service_error_counts.items(), key=lambda x: x[1], reverse=True)
        stats_str = ', '.join([f"{service}={count}" for service, count in sorted_services if count > 0])

        err_msg = (
            f"Error buffer filled in {age_minutes:.1f} minutes "
            f"(expected at least {self._rate_limit_window_mins}). "
            f"There may be a service error-looping. "
            f"Error capturing paused for {self._rate_limit_pause_mins} minutes. "
            f"Errors per service: {stats_str}"
        )

        self._rate_limiting_active = True
        log.critical(err_msg)

        with self._recent_errors_lock:
            self._recent_errors.append({
                'service': self._own_service_name,
                'priority': 3,
                'priority_name': 'CRIT',
                'message': err_msg,
                'timestamp': datetime.now().isoformat(),
            })

        # Schedule unthrottling of logs
        self._rate_limit_resume_timer = threading.Timer(
            self._rate_limit_pause_mins * 60,
            self._unthrottle_errors
        )
        self._rate_limit_resume_timer.daemon = True
        self._rate_limit_resume_timer.start()

        if self._on_rate_limit_callback:
            try:
                self._on_rate_limit_callback(service_error_counts)
            except BaseException: # pylint: disable=broad-exception-caught
                log.error("Error in rate limit callback", exc_info=True)
        return True


    def _unthrottle_errors(self):
        """Resume error capturing after rate limit pause"""
        self._rate_limiting_active = False
        self._rate_limit_resume_timer = None
        log.info("Rate limiting deactivated, resuming error capture")
