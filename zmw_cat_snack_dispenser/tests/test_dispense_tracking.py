import pytest
from unittest.mock import Mock, MagicMock

from dispense_tracking import DispenseTracking


class TestRequestFeedNow:
    """Tests for request_feed_now method."""

    @pytest.fixture
    def mock_history(self):
        return Mock()

    @pytest.fixture
    def mock_schedule(self):
        return Mock()

    def test_rejects_if_cat_feeder_is_none(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)

        result = tracker.request_feed_now(source="test", cat_feeder=None, serving_size=1)

        assert result is False
        mock_history.register_error.assert_called_once()
        assert "not discovered" in mock_history.register_error.call_args[0][1]

    def test_rejects_if_register_request_returns_false(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        mock_history.register_request.return_value = False
        mock_cat_feeder = Mock()

        result = tracker.request_feed_now(source="test", cat_feeder=mock_cat_feeder, serving_size=1)

        assert result is False
        mock_cat_feeder.set.assert_not_called()

    def test_sets_feed_and_serving_size(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        mock_history.register_request.return_value = True
        mock_cat_feeder = Mock()

        result = tracker.request_feed_now(source="test", cat_feeder=mock_cat_feeder, serving_size=2)

        assert result is True
        mock_cat_feeder.set.assert_any_call("serving_size", 2)
        mock_cat_feeder.set.assert_any_call("feed", "START")

    def test_sets_feed_without_serving_size_when_none(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        mock_history.register_request.return_value = True
        mock_cat_feeder = Mock()
        mock_cat_feeder.name = "test_feeder"

        result = tracker.request_feed_now(source="test", cat_feeder=mock_cat_feeder, serving_size=None)

        assert result is True
        # Should only set "feed", not "serving_size"
        mock_cat_feeder.set.assert_called_once_with("feed", "START")


class TestCheckDispensing:
    """Tests for check_dispensing method."""

    @pytest.fixture
    def mock_history(self):
        return Mock()

    @pytest.fixture
    def mock_schedule(self):
        return Mock()

    def make_cat_feeder(self, portions_per_day=None, weight_per_day=None, feeding_source=None):
        """Helper to create a mock cat_feeder with specified values."""
        mock = Mock()
        mock.name = "test_feeder"
        mock.get = lambda key: {
            'portions_per_day': portions_per_day,
            'weight_per_day': weight_per_day,
            'feeding_source': feeding_source,
        }.get(key)
        return mock

    def test_ignores_message_if_portions_per_day_unset(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        cat_feeder = self.make_cat_feeder(portions_per_day=None, weight_per_day=100)

        tracker.check_dispensing(cat_feeder)

        mock_history.register_zigbee_dispense.assert_not_called()
        mock_history.register_dispense.assert_not_called()
        mock_schedule.register_schedule_triggered.assert_not_called()

    def test_ignores_message_if_weight_per_day_unset(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        cat_feeder = self.make_cat_feeder(portions_per_day=5, weight_per_day=None)

        tracker.check_dispensing(cat_feeder)

        mock_history.register_zigbee_dispense.assert_not_called()
        mock_history.register_dispense.assert_not_called()
        mock_schedule.register_schedule_triggered.assert_not_called()

    def test_initializes_tracking_from_first_message(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        assert tracker._last_portions_per_day is None
        assert tracker._last_weight_per_day is None

        cat_feeder = self.make_cat_feeder(portions_per_day=5, weight_per_day=200)
        tracker.check_dispensing(cat_feeder)

        assert tracker._last_portions_per_day == 5
        assert tracker._last_weight_per_day == 200
        # Should not register any dispense on first message
        mock_history.register_zigbee_dispense.assert_not_called()
        mock_history.register_dispense.assert_not_called()
        mock_schedule.register_schedule_triggered.assert_not_called()

    def test_resets_on_day_change(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        # Simulate end of previous day
        tracker._last_portions_per_day = 10
        tracker._last_weight_per_day = 500

        # New day: portions reset to lower value
        cat_feeder = self.make_cat_feeder(portions_per_day=2, weight_per_day=80)
        tracker.check_dispensing(cat_feeder)

        # Should reset to new values
        assert tracker._last_portions_per_day == 2
        assert tracker._last_weight_per_day == 80
        # Should not register any dispense on day reset
        mock_history.register_zigbee_dispense.assert_not_called()
        mock_history.register_dispense.assert_not_called()
        mock_schedule.register_schedule_triggered.assert_not_called()

    def test_ignores_message_if_portions_unchanged(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        # Same portions as before
        cat_feeder = self.make_cat_feeder(portions_per_day=5, weight_per_day=200)
        tracker.check_dispensing(cat_feeder)

        mock_history.register_zigbee_dispense.assert_not_called()
        mock_history.register_dispense.assert_not_called()
        mock_schedule.register_schedule_triggered.assert_not_called()

    def test_remote_source_calls_register_zigbee_dispense(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        cat_feeder = self.make_cat_feeder(
            portions_per_day=7, weight_per_day=280, feeding_source='remote'
        )
        tracker.check_dispensing(cat_feeder)

        mock_history.register_zigbee_dispense.assert_called_once_with(2, 80)
        mock_schedule.register_schedule_triggered.assert_not_called()
        mock_history.register_dispense.assert_not_called()

    def test_schedule_source_calls_register_schedule_triggered(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        cat_feeder = self.make_cat_feeder(
            portions_per_day=6, weight_per_day=240, feeding_source='schedule'
        )
        tracker.check_dispensing(cat_feeder)

        mock_schedule.register_schedule_triggered.assert_called_once_with(1, 40)
        mock_history.register_zigbee_dispense.assert_not_called()
        mock_history.register_dispense.assert_not_called()

    def test_manual_source_calls_register_dispense(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        cat_feeder = self.make_cat_feeder(
            portions_per_day=8, weight_per_day=320, feeding_source='manual'
        )
        tracker.check_dispensing(cat_feeder)

        mock_history.register_dispense.assert_called_once_with('Unit button', 3, 120)
        mock_history.register_zigbee_dispense.assert_not_called()
        mock_schedule.register_schedule_triggered.assert_not_called()

    def test_unknown_source_calls_register_dispense_with_mystery(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        cat_feeder = self.make_cat_feeder(
            portions_per_day=6, weight_per_day=240, feeding_source='something_weird'
        )
        tracker.check_dispensing(cat_feeder)

        mock_history.register_dispense.assert_called_once_with('Mystery!', 1, 40)
        mock_history.register_zigbee_dispense.assert_not_called()
        mock_schedule.register_schedule_triggered.assert_not_called()

    def test_updates_internal_state_after_dispensing(self, mock_history, mock_schedule):
        tracker = DispenseTracking(mock_history, mock_schedule)
        tracker._last_portions_per_day = 5
        tracker._last_weight_per_day = 200

        cat_feeder = self.make_cat_feeder(
            portions_per_day=7, weight_per_day=280, feeding_source='remote'
        )
        tracker.check_dispensing(cat_feeder)

        assert tracker._last_portions_per_day == 7
        assert tracker._last_weight_per_day == 280
