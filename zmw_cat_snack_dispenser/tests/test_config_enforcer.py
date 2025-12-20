import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from config_enforcer import ConfigEnforcer, _ensure_feeding_mode, _ensure_schedule


class TestEnsureFeedingMode:
    """Tests for _ensure_feeding_mode function."""

    def test_does_nothing_if_mode_is_schedule(self):
        cat_feeder = Mock()
        cat_feeder.get.return_value = 'schedule'

        _ensure_feeding_mode(cat_feeder, correct_if_bad=True)

        cat_feeder.set.assert_not_called()

    def test_sets_mode_to_schedule_if_incorrect(self):
        cat_feeder = Mock()
        cat_feeder.get.return_value = 'manual'

        _ensure_feeding_mode(cat_feeder, correct_if_bad=True)

        cat_feeder.set.assert_called_once_with('mode', 'schedule')

    def test_sets_mode_to_schedule_if_none(self):
        cat_feeder = Mock()
        cat_feeder.get.return_value = None

        _ensure_feeding_mode(cat_feeder, correct_if_bad=True)

        cat_feeder.set.assert_called_once_with('mode', 'schedule')

    def test_does_nothing_if_correct_if_bad_false_and_mode_wrong(self):
        cat_feeder = Mock()
        cat_feeder.name = "test_feeder"
        cat_feeder.get.return_value = 'manual'

        _ensure_feeding_mode(cat_feeder, correct_if_bad=False)

        cat_feeder.set.assert_not_called()

    def test_does_nothing_if_correct_if_bad_false_and_mode_none(self):
        cat_feeder = Mock()
        cat_feeder.name = "test_feeder"
        cat_feeder.get.return_value = None

        _ensure_feeding_mode(cat_feeder, correct_if_bad=False)

        cat_feeder.set.assert_not_called()


class TestEnsureSchedule:
    """Tests for _ensure_schedule function."""

    def test_does_nothing_if_schedule_matches(self):
        cat_feeder = Mock()
        cat_feeder.get.return_value = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'size': 2},
        ]
        target_schedule = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 2},
        ]

        _ensure_schedule(cat_feeder, target_schedule, correct_if_bad=True)

        cat_feeder.set.assert_not_called()

    def test_sets_schedule_if_different(self):
        cat_feeder = Mock()
        cat_feeder.get.return_value = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'size': 1},
        ]
        target_schedule = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 2},
        ]

        _ensure_schedule(cat_feeder, target_schedule, correct_if_bad=True)

        cat_feeder.set.assert_called_once_with('schedule', [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'size': 2},
        ])

    def test_sets_schedule_if_none(self):
        cat_feeder = Mock()
        cat_feeder.get.return_value = None
        target_schedule = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 2},
        ]

        _ensure_schedule(cat_feeder, target_schedule, correct_if_bad=True)

        cat_feeder.set.assert_called_once_with('schedule', [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'size': 2},
        ])

    def test_does_nothing_if_correct_if_bad_false_and_schedule_wrong(self):
        cat_feeder = Mock()
        cat_feeder.name = "test_feeder"
        cat_feeder.get.return_value = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'size': 1},
        ]
        target_schedule = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 2},
        ]

        _ensure_schedule(cat_feeder, target_schedule, correct_if_bad=False)

        cat_feeder.set.assert_not_called()

    def test_does_nothing_if_correct_if_bad_false_and_schedule_none(self):
        cat_feeder = Mock()
        cat_feeder.name = "test_feeder"
        cat_feeder.get.return_value = None
        target_schedule = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 2},
        ]

        _ensure_schedule(cat_feeder, target_schedule, correct_if_bad=False)

        cat_feeder.set.assert_not_called()


class TestConfigEnforcer:
    """Tests for ConfigEnforcer class."""

    @pytest.fixture
    def mock_schedule(self):
        mock = Mock()
        mock.get_schedule.return_value = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 2},
        ]
        return mock

    def test_skips_action_within_backoff_threshold(self, mock_schedule):
        enforcer = ConfigEnforcer(backoff_secs=60, schedule=mock_schedule)
        cat_feeder = Mock()
        cat_feeder.get.return_value = 'manual'  # Would normally trigger correction

        # First call should run
        enforcer.ensure_config(cat_feeder, correct_if_bad=True)
        assert cat_feeder.set.call_count == 2  # mode and schedule

        cat_feeder.reset_mock()

        # Second call within backoff should be skipped
        enforcer.ensure_config(cat_feeder, correct_if_bad=True)
        cat_feeder.set.assert_not_called()

    def test_runs_after_backoff_expires(self, mock_schedule):
        enforcer = ConfigEnforcer(backoff_secs=60, schedule=mock_schedule)
        cat_feeder = Mock()
        cat_feeder.get.return_value = 'manual'

        # First call
        enforcer.ensure_config(cat_feeder, correct_if_bad=True)
        cat_feeder.reset_mock()

        # Simulate time passing beyond backoff
        enforcer._ensure_config_last_run = datetime.now() - timedelta(seconds=61)

        # Should run again
        enforcer.ensure_config(cat_feeder, correct_if_bad=True)
        assert cat_feeder.set.call_count == 2

    def test_calls_ensure_methods_when_not_in_backoff(self, mock_schedule):
        enforcer = ConfigEnforcer(backoff_secs=60, schedule=mock_schedule)
        cat_feeder = Mock()
        cat_feeder.get.return_value = None  # Both mode and schedule are None

        with patch('config_enforcer._ensure_feeding_mode') as mock_feeding_mode, \
             patch('config_enforcer._ensure_schedule') as mock_ensure_schedule:

            enforcer.ensure_config(cat_feeder, correct_if_bad=True)

            mock_feeding_mode.assert_called_once_with(cat_feeder, True)
            mock_ensure_schedule.assert_called_once_with(
                cat_feeder, mock_schedule.get_schedule(), True
            )

    def test_passes_correct_if_bad_false_to_ensure_methods(self, mock_schedule):
        enforcer = ConfigEnforcer(backoff_secs=60, schedule=mock_schedule)
        cat_feeder = Mock()

        with patch('config_enforcer._ensure_feeding_mode') as mock_feeding_mode, \
             patch('config_enforcer._ensure_schedule') as mock_ensure_schedule:

            enforcer.ensure_config(cat_feeder, correct_if_bad=False)

            mock_feeding_mode.assert_called_once_with(cat_feeder, False)
            mock_ensure_schedule.assert_called_once_with(
                cat_feeder, mock_schedule.get_schedule(), False
            )
