from datetime import datetime

from zzmw_lib.logs import build_logger

log = build_logger("NotificationManager")


class NotificationManager:
    """Manages Telegram notifications for dispense events with configurable behavior."""

    def __init__(self, cfg, feeder_name, feeding_schedule, scheduler, message_svc_fn):
        self._feeder_name = feeder_name
        self._message_svc = message_svc_fn
        self._scheduler = scheduler

        # Config options
        self._telegram_on_error = cfg["telegram_on_error"]
        self._telegram_on_success = cfg["telegram_on_success"]
        self._telegram_day_summary = cfg["telegram_day_summary"]
        self._summary_delay_minutes = cfg.get("telegram_summary_delay_minutes", 5)

        # Daily tracking
        self._today_dispense_count = 0
        self._today_portions_dispensed = 0
        self._today_errors = 0
        self._today_date = datetime.now().date()
        self._dispense_events = []  # List of (timestamp, portions, error) tuples

        # Schedule daily summary if enabled
        if self._telegram_day_summary and feeding_schedule:
            self._schedule_daily_summary(feeding_schedule)

    def _schedule_daily_summary(self, feeding_schedule):
        """Schedule daily summary to run after the last feeding of the day."""
        # Find the latest scheduled feeding time
        latest_hour = 0
        latest_minute = 0

        for schedule in feeding_schedule:
            sched_time = schedule['hour'] * 60 + schedule['minute']
            latest_time = latest_hour * 60 + latest_minute
            if sched_time > latest_time:
                latest_hour = schedule['hour']
                latest_minute = schedule['minute']

        # Add the configured delay
        total_minutes = latest_hour * 60 + latest_minute + self._summary_delay_minutes
        summary_hour = (total_minutes // 60) % 24
        summary_minute = total_minutes % 60

        log.info("Scheduling daily summary at %02d:%02d (after last feeding at %02d:%02d + %d min delay)",
                 summary_hour, summary_minute, latest_hour, latest_minute, self._summary_delay_minutes)

        self._scheduler.add_job(
            self._send_daily_summary,
            'cron',
            hour=summary_hour,
            minute=summary_minute,
        )

    def _reset_daily_stats_if_needed(self):
        """Reset daily statistics if the date has changed."""
        today = datetime.now().date()
        if today != self._today_date:
            self._today_dispense_count = 0
            self._today_portions_dispensed = 0
            self._today_errors = 0
            self._today_date = today
            self._dispense_events = []

    def notify_dispense_event(self, source, error, portions_dispensed):
        """Handle a dispense event notification."""
        self._reset_daily_stats_if_needed()

        # Track the event
        self._today_dispense_count += 1
        if portions_dispensed is not None:
            self._today_portions_dispensed += portions_dispensed
        if error is not None:
            self._today_errors += 1
        self._dispense_events.append((datetime.now(), portions_dispensed, error))

        # Build the message
        msg = self._build_dispense_message(source, error, portions_dispensed)

        # Determine if we should send based on config
        is_error = error is not None and (portions_dispensed is None or portions_dispensed == 0)
        should_send = False

        if is_error and self._telegram_on_error:
            should_send = True
        elif not is_error and self._telegram_on_success:
            should_send = True

        if should_send:
            self._message_svc("ZmwTelegram", "send_text", {'msg': msg})

    def _build_dispense_message(self, source, error, portions_dispensed):
        """Build the notification message for a dispense event."""
        if error is not None and (portions_dispensed is None or portions_dispensed == 0):
            return f"Error for {source} dispense on {self._feeder_name}: {error}"

        if portions_dispensed is None:
            quantity = "an unknown quantity of snacks"
        elif portions_dispensed == 1:
            quantity = "1 snack"
        else:
            quantity = f"{portions_dispensed} snacks"

        msg = f"{source}: purveying {quantity} on {self._feeder_name}."
        if error is not None:
            msg += f" (Warning: {error})"

        return msg

    def _send_daily_summary(self):
        """Send the daily summary message."""
        self._reset_daily_stats_if_needed()

        if self._today_dispense_count == 0:
            msg = f"Daily summary for {self._feeder_name}: No dispense events today."
        else:
            if self._today_portions_dispensed == 1:
                portion_text = "1 portion"
            else:
                portion_text = f"{self._today_portions_dispensed} portions"

            msg = (f"Daily summary for {self._feeder_name}: "
                   f"{self._today_dispense_count} dispense events, {portion_text} dispensed.")

            if self._today_errors > 0:
                msg += f" ({self._today_errors} error(s) occurred)"

        self._message_svc("ZmwTelegram", "send_text", {'msg': msg})
        log.info("Sent daily summary: %s", msg)
