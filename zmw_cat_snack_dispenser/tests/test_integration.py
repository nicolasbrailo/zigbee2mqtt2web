"""
Integration tests for DispenseTracking with real DispensingHistory and DispensingSchedule.

These tests verify that actions on DispenseTracking are correctly reflected in both
the history and schedule objects.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from dispense_tracking import DispenseTracking
from history import DispensingHistory
from schedule import DispensingSchedule


class IntegrationTestBase:
    """Base class with helpers for integration tests."""

    @pytest.fixture
    def history(self):
        return DispensingHistory("test_feeder", history_len=100, cb_on_dispense=Mock())

    @pytest.fixture
    def schedule_config(self):
        return [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 2}]

    @pytest.fixture
    def schedule(self, history, schedule_config):
        with patch('schedule.BackgroundScheduler') as mock_sched:
            mock_sched.return_value = Mock()
            return DispensingSchedule(
                cat_feeder_name="test_feeder",
                history=history,
                cb_emergency_dispense=Mock(),
                feeding_schedule=schedule_config,
                tolerance_secs=60,
            )

    @pytest.fixture
    def tracker(self, history, schedule):
        return DispenseTracking(history, schedule)

    def make_cat_feeder(self, portions_per_day=None, weight_per_day=None, feeding_source=None):
        mock = Mock()
        mock.name = "test_feeder"
        mock.get = lambda key: {
            'portions_per_day': portions_per_day,
            'weight_per_day': weight_per_day,
            'feeding_source': feeding_source,
        }.get(key)
        return mock


class TestRequestAndAcknowledgment(IntegrationTestBase):
    """Tests for request followed by acknowledgment flow."""

    def test_request_followed_by_remote_dispense_acknowledged(self, tracker, history):
        cat_feeder = self.make_cat_feeder()

        with patch('history.threading.Timer') as mock_timer:
            mock_timer.return_value = Mock()
            result = tracker.request_feed_now("API", cat_feeder, serving_size=2)

        assert result is True

        # Initialize tracking state
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        # Simulate remote dispense response
        cat_feeder_response = self.make_cat_feeder(
            portions_per_day=7, weight_per_day=280, feeding_source='remote'
        )
        tracker.check_dispensing(cat_feeder_response)

        # Verify history
        entries = history.get_history()
        assert len(entries) == 1
        assert entries[0]['unit_acknowledged'] is True
        assert entries[0]['portions_dispensed'] == 2
        assert entries[0]['weight_dispensed'] == 80

    def test_request_timeout_shows_error_in_history(self, tracker, history):
        cat_feeder = self.make_cat_feeder()
        captured_callback = None
        captured_args = None

        with patch('history.threading.Timer') as mock_timer:
            def capture_timer(timeout, callback, args):
                nonlocal captured_callback, captured_args
                captured_callback = callback
                captured_args = args
                return Mock()

            mock_timer.side_effect = capture_timer
            tracker.request_feed_now("API", cat_feeder, serving_size=2)

        # Simulate timeout firing
        captured_callback(*captured_args)

        entries = history.get_history()
        assert len(entries) == 1
        assert entries[0]['error'] is not None
        assert "failed to acknowledge" in entries[0]['error']


class TestRemoteDispense(IntegrationTestBase):
    """Tests for remote dispense scenarios."""

    def test_remote_dispense_without_request_shows_unauthorized(self, tracker, history):
        # Initialize tracking state (no prior request)
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        cat_feeder = self.make_cat_feeder(
            portions_per_day=7, weight_per_day=280, feeding_source='remote'
        )
        tracker.check_dispensing(cat_feeder)

        entries = history.get_history()
        assert len(entries) == 1
        assert entries[0]['source'] == 'Unauthorized Zigbee request'
        assert entries[0]['error'] is not None

    def test_second_request_rejected_when_first_pending(self, tracker, history):
        cat_feeder = self.make_cat_feeder()

        with patch('history.threading.Timer') as mock_timer:
            mock_timer.return_value = Mock()

            # First request succeeds
            result1 = tracker.request_feed_now("API", cat_feeder, serving_size=2)
            assert result1 is True

            # Second request while first pending
            result2 = tracker.request_feed_now("Telegram", cat_feeder, serving_size=1)
            assert result2 is False

        entries = history.get_history()
        assert len(entries) == 2
        assert entries[0]['source'] == "API"
        assert entries[1]['source'] == "Telegram"
        assert entries[1]['error'] is not None
        assert "Unacknowledged" in entries[1]['error']


class TestScheduledDispense(IntegrationTestBase):
    """Tests for scheduled dispense scenarios."""

    def test_scheduled_dispense_on_time_recorded(self, tracker, history, schedule):
        # Initialize tracking state
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        cat_feeder = self.make_cat_feeder(
            portions_per_day=7, weight_per_day=280, feeding_source='schedule'
        )

        # Mock datetime to be within tolerance of 8:00
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 0, 30)
            tracker.check_dispensing(cat_feeder)

        entries = history.get_history()
        assert len(entries) == 1
        assert entries[0]['source'] == 'Schedule, on-time'
        assert entries[0]['portions_dispensed'] == 2
        assert entries[0]['weight_dispensed'] == 80

    def test_scheduled_dispense_unmatched_recorded(self, tracker, history, schedule):
        # Initialize tracking state
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        cat_feeder = self.make_cat_feeder(
            portions_per_day=7, weight_per_day=280, feeding_source='schedule'
        )

        # Mock datetime to be outside tolerance (10:00, not near 8:00)
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
            tracker.check_dispensing(cat_feeder)

        entries = history.get_history()
        assert len(entries) == 1
        assert entries[0]['source'] == 'Not in schedule, reported as scheduled'
        assert entries[0]['error'] is not None


class TestManualDispense(IntegrationTestBase):
    """Tests for manual button press scenarios."""

    def test_manual_button_press_recorded(self, tracker, history):
        # Initialize tracking state
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        cat_feeder = self.make_cat_feeder(
            portions_per_day=6, weight_per_day=240, feeding_source='manual'
        )
        tracker.check_dispensing(cat_feeder)

        entries = history.get_history()
        assert len(entries) == 1
        assert entries[0]['source'] == 'Unit button'
        assert entries[0]['portions_dispensed'] == 1
        assert entries[0]['weight_dispensed'] == 40
        assert entries[0]['unit_acknowledged'] is True


class TestEndToEndCycle(IntegrationTestBase):
    """End-to-end cycle tests."""

    def test_full_request_dispense_cycle(self, tracker, history):
        cat_feeder = self.make_cat_feeder()

        # Step 1: Make request
        with patch('history.threading.Timer') as mock_timer:
            mock_timer.return_value = Mock()
            result = tracker.request_feed_now("Web UI", cat_feeder, serving_size=3)

        assert result is True
        entries = history.get_history()
        assert len(entries) == 1
        assert entries[0]['source'] == "Web UI"
        assert entries[0]['serving_size_requested'] == 3
        assert entries[0]['unit_acknowledged'] is False

        # Step 2: Initialize tracker state and receive dispense confirmation
        tracker._last_portions_per_day = 10
        tracker._last_weight_per_day = 400

        cat_feeder_response = self.make_cat_feeder(
            portions_per_day=13, weight_per_day=520, feeding_source='remote'
        )
        tracker.check_dispensing(cat_feeder_response)

        # Step 3: Verify final state
        entries = history.get_history()
        assert len(entries) == 1  # Same entry, now acknowledged
        assert entries[0]['unit_acknowledged'] is True
        assert entries[0]['portions_dispensed'] == 3
        assert entries[0]['weight_dispensed'] == 120
