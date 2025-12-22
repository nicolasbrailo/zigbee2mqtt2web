import pytest
from unittest.mock import Mock, patch
from datetime import datetime, date

from notification_manager import NotificationManager


def make_cfg(on_error=True, on_success=True, day_summary=False, summary_delay=5):
    """Helper to create a config dict."""
    return {
        "telegram_on_error": on_error,
        "telegram_on_success": on_success,
        "telegram_day_summary": day_summary,
        "telegram_summary_delay_minutes": summary_delay,
    }


class TestNotificationManagerInit:
    """Tests for NotificationManager initialization."""

    def test_init_with_minimal_config(self):
        mock_message_svc = Mock()
        mock_scheduler = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], mock_scheduler, mock_message_svc)

        assert nm._feeder_name == "test_feeder"
        assert nm._telegram_on_error is True
        assert nm._telegram_on_success is True
        assert nm._telegram_day_summary is False

    def test_init_does_not_schedule_summary_when_disabled(self):
        mock_message_svc = Mock()
        mock_scheduler = Mock()
        cfg = make_cfg(day_summary=False)

        NotificationManager(cfg, "test_feeder", [{"hour": 17, "minute": 0}], mock_scheduler, mock_message_svc)

        mock_scheduler.add_job.assert_not_called()

    def test_init_schedules_summary_when_enabled(self):
        mock_message_svc = Mock()
        mock_scheduler = Mock()
        cfg = make_cfg(day_summary=True, summary_delay=30)
        feeding_schedule = [{"hour": 17, "minute": 0}]

        NotificationManager(cfg, "test_feeder", feeding_schedule, mock_scheduler, mock_message_svc)

        mock_scheduler.add_job.assert_called_once()
        call_args = mock_scheduler.add_job.call_args
        assert call_args[0][1] == 'cron'
        assert call_args[1]['hour'] == 17
        assert call_args[1]['minute'] == 30


class TestScheduleDailySummary:
    """Tests for _schedule_daily_summary method."""

    def test_schedules_after_latest_feeding(self):
        mock_message_svc = Mock()
        mock_scheduler = Mock()
        cfg = make_cfg(day_summary=True, summary_delay=15)
        feeding_schedule = [
            {"hour": 8, "minute": 0},
            {"hour": 12, "minute": 30},
            {"hour": 18, "minute": 45},  # Latest
        ]

        NotificationManager(cfg, "test_feeder", feeding_schedule, mock_scheduler, mock_message_svc)

        call_args = mock_scheduler.add_job.call_args
        assert call_args[1]['hour'] == 19
        assert call_args[1]['minute'] == 0  # 18:45 + 15 min = 19:00

    def test_handles_midnight_wrap(self):
        mock_message_svc = Mock()
        mock_scheduler = Mock()
        cfg = make_cfg(day_summary=True, summary_delay=30)
        feeding_schedule = [{"hour": 23, "minute": 45}]

        NotificationManager(cfg, "test_feeder", feeding_schedule, mock_scheduler, mock_message_svc)

        call_args = mock_scheduler.add_job.call_args
        assert call_args[1]['hour'] == 0
        assert call_args[1]['minute'] == 15  # 23:45 + 30 min = 00:15

    def test_does_not_schedule_with_empty_feeding_schedule(self):
        mock_message_svc = Mock()
        mock_scheduler = Mock()
        cfg = make_cfg(day_summary=True)

        NotificationManager(cfg, "test_feeder", [], mock_scheduler, mock_message_svc)

        mock_scheduler.add_job.assert_not_called()


class TestNotifyDispenseEvent:
    """Tests for notify_dispense_event method."""

    def test_sends_message_on_success_when_enabled(self):
        mock_message_svc = Mock()
        cfg = make_cfg(on_success=True)

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm.notify_dispense_event("Manual", None, 2)

        mock_message_svc.assert_called_once()
        call_args = mock_message_svc.call_args
        assert call_args[0][0] == "ZmwTelegram"
        assert call_args[0][1] == "send_text"
        assert "2 snacks" in call_args[0][2]['msg']

    def test_does_not_send_message_on_success_when_disabled(self):
        mock_message_svc = Mock()
        cfg = make_cfg(on_success=False)

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm.notify_dispense_event("Manual", None, 2)

        mock_message_svc.assert_not_called()

    def test_sends_message_on_error_when_enabled(self):
        mock_message_svc = Mock()
        cfg = make_cfg(on_error=True)

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm.notify_dispense_event("Manual", "Something broke", None)

        mock_message_svc.assert_called_once()
        call_args = mock_message_svc.call_args
        assert "Error" in call_args[0][2]['msg']
        assert "Something broke" in call_args[0][2]['msg']

    def test_does_not_send_message_on_error_when_disabled(self):
        mock_message_svc = Mock()
        cfg = make_cfg(on_error=False)

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm.notify_dispense_event("Manual", "Something broke", None)

        mock_message_svc.assert_not_called()

    def test_success_with_warning_sends_when_on_success_enabled(self):
        """When error is not None but portions_dispensed > 0, it's a success with warning."""
        mock_message_svc = Mock()
        cfg = make_cfg(on_success=True, on_error=False)

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm.notify_dispense_event("Manual", "Minor issue", 2)

        mock_message_svc.assert_called_once()
        msg = mock_message_svc.call_args[0][2]['msg']
        assert "Warning" in msg
        assert "Minor issue" in msg

    def test_tracks_dispense_count(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm.notify_dispense_event("Manual", None, 1)
        nm.notify_dispense_event("Schedule", None, 2)
        nm.notify_dispense_event("Telegram", None, 1)

        assert nm._today_dispense_count == 3
        assert nm._today_portions_dispensed == 4

    def test_tracks_error_count(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm.notify_dispense_event("Manual", None, 1)
        nm.notify_dispense_event("Schedule", "Error 1", 0)
        nm.notify_dispense_event("Telegram", "Error 2", None)

        assert nm._today_errors == 2

    def test_tracks_dispense_events(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm.notify_dispense_event("Manual", None, 1)
        nm.notify_dispense_event("Schedule", "Error", 0)

        assert len(nm._dispense_events) == 2
        assert nm._dispense_events[0][1] == 1  # portions
        assert nm._dispense_events[0][2] is None  # error
        assert nm._dispense_events[1][1] == 0
        assert nm._dispense_events[1][2] == "Error"


class TestBuildDispenseMessage:
    """Tests for _build_dispense_message method."""

    def test_error_message_format(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        msg = nm._build_dispense_message("Manual", "Connection failed", None)

        assert msg == "Error for Manual dispense on test_feeder: Connection failed"

    def test_error_message_with_zero_portions(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        msg = nm._build_dispense_message("Manual", "Jam detected", 0)

        assert msg == "Error for Manual dispense on test_feeder: Jam detected"

    def test_success_message_single_portion(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        msg = nm._build_dispense_message("Schedule", None, 1)

        assert msg == "Schedule: purveying 1 snack on test_feeder."

    def test_success_message_multiple_portions(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        msg = nm._build_dispense_message("Manual", None, 3)

        assert msg == "Manual: purveying 3 snacks on test_feeder."

    def test_success_message_unknown_portions(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        msg = nm._build_dispense_message("Button", None, None)

        assert msg == "Button: purveying an unknown quantity of snacks on test_feeder."

    def test_success_with_warning(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        msg = nm._build_dispense_message("Manual", "Minor calibration issue", 2)

        assert "2 snacks" in msg
        assert "(Warning: Minor calibration issue)" in msg


class TestResetDailyStats:
    """Tests for _reset_daily_stats_if_needed method."""

    def test_resets_stats_on_new_day(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm._today_dispense_count = 5
        nm._today_portions_dispensed = 10
        nm._today_errors = 2
        nm._dispense_events = [("event1",), ("event2",)]
        nm._today_date = date(2024, 1, 1)  # Old date

        nm._reset_daily_stats_if_needed()

        assert nm._today_dispense_count == 0
        assert nm._today_portions_dispensed == 0
        assert nm._today_errors == 0
        assert nm._dispense_events == []
        assert nm._today_date == datetime.now().date()

    def test_does_not_reset_on_same_day(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm._today_dispense_count = 5
        nm._today_portions_dispensed = 10
        nm._today_date = datetime.now().date()  # Today

        nm._reset_daily_stats_if_needed()

        assert nm._today_dispense_count == 5
        assert nm._today_portions_dispensed == 10


class TestSendDailySummary:
    """Tests for _send_daily_summary method."""

    def test_sends_no_events_message_when_empty(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm._send_daily_summary()

        mock_message_svc.assert_called_once()
        msg = mock_message_svc.call_args[0][2]['msg']
        assert "No dispense events today" in msg
        assert "test_feeder" in msg

    def test_sends_summary_with_events(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm._today_dispense_count = 3
        nm._today_portions_dispensed = 5

        nm._send_daily_summary()

        msg = mock_message_svc.call_args[0][2]['msg']
        assert "3 dispense events" in msg
        assert "5 portions" in msg

    def test_sends_summary_single_portion(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm._today_dispense_count = 1
        nm._today_portions_dispensed = 1

        nm._send_daily_summary()

        msg = mock_message_svc.call_args[0][2]['msg']
        assert "1 dispense events" in msg
        assert "1 portion" in msg
        assert "portions" not in msg or "1 portion" in msg

    def test_includes_error_count_when_present(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm._today_dispense_count = 5
        nm._today_portions_dispensed = 8
        nm._today_errors = 2

        nm._send_daily_summary()

        msg = mock_message_svc.call_args[0][2]['msg']
        assert "2 error(s)" in msg

    def test_no_error_count_when_zero(self):
        mock_message_svc = Mock()
        cfg = make_cfg()

        nm = NotificationManager(cfg, "test_feeder", [], Mock(), mock_message_svc)
        nm._today_dispense_count = 3
        nm._today_portions_dispensed = 3
        nm._today_errors = 0

        nm._send_daily_summary()

        msg = mock_message_svc.call_args[0][2]['msg']
        assert "error" not in msg.lower()
