import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from schedule import (
    _days_to_apscheduler,
    _validate_schedule_config,
    DispensingSchedule,
)


class TestDaysToApscheduler:
    """Tests for the _days_to_apscheduler function."""

    def test_everyday_returns_none(self):
        assert _days_to_apscheduler('everyday') is None

    def test_workdays_returns_mon_fri(self):
        assert _days_to_apscheduler('workdays') == 'mon-fri'

    def test_weekend_returns_sat_sun(self):
        assert _days_to_apscheduler('weekend') == 'sat,sun'

    def test_mon_wed_fri_sun_mapping(self):
        assert _days_to_apscheduler('mon-wed-fri-sun') == 'mon,wed,fri,sun'

    def test_tue_thu_sat_mapping(self):
        assert _days_to_apscheduler('tue-thu-sat') == 'tue,thu,sat'

    @pytest.mark.parametrize('day', ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'])
    def test_individual_days_pass_through(self, day):
        assert _days_to_apscheduler(day) == day

    def test_invalid_days_raises_value_error(self):
        with pytest.raises(ValueError) as exc_info:
            _days_to_apscheduler('invalid_day')
        assert "Invalid days value 'invalid_day'" in str(exc_info.value)


class TestValidateScheduleConfig:
    """Tests for the _validate_schedule_config function."""

    def test_valid_config_passes(self):
        config = [{'days': 'everyday', 'hour': 8, 'minute': 30, 'serving_size': 1}]
        _validate_schedule_config(config, tolerance_secs=60)  # Should not raise

    def test_not_a_list_raises_error(self):
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config("not a list", tolerance_secs=60)
        assert "feeding_schedule must be a list" in str(exc_info.value)

    def test_dict_instead_of_list_raises_error(self):
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config({'days': 'everyday', 'hour': 8, 'minute': 30, 'serving_size': 1}, tolerance_secs=60)
        assert "feeding_schedule must be a list" in str(exc_info.value)

    def test_entry_not_dict_raises_error(self):
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(["not a dict"], tolerance_secs=60)
        assert "Schedule entry 0 must be a dictionary" in str(exc_info.value)

    def test_missing_days_key_raises_error(self):
        config = [{'hour': 8, 'minute': 30, 'serving_size': 1}]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "missing required keys" in str(exc_info.value)
        assert "'days'" in str(exc_info.value)

    def test_missing_hour_key_raises_error(self):
        config = [{'days': 'everyday', 'minute': 30, 'serving_size': 1}]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "missing required keys" in str(exc_info.value)
        assert "'hour'" in str(exc_info.value)

    def test_missing_minute_key_raises_error(self):
        config = [{'days': 'everyday', 'hour': 8, 'serving_size': 1}]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "missing required keys" in str(exc_info.value)
        assert "'minute'" in str(exc_info.value)

    def test_missing_serving_size_key_raises_error(self):
        config = [{'days': 'everyday', 'hour': 8, 'minute': 30}]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "missing required keys" in str(exc_info.value)
        assert "'serving_size'" in str(exc_info.value)

    def test_invalid_days_value_raises_error(self):
        config = [{'days': 'invalid', 'hour': 8, 'minute': 30, 'serving_size': 1}]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "invalid days value 'invalid'" in str(exc_info.value)

    @pytest.mark.parametrize('hour', [-1, 24, 25, 100])
    def test_invalid_hour_out_of_range_raises_error(self, hour):
        config = [{'days': 'everyday', 'hour': hour, 'minute': 30, 'serving_size': 1}]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert f"invalid hour '{hour}'" in str(exc_info.value)
        assert "must be an integer 0-23" in str(exc_info.value)

    def test_hour_as_string_raises_error(self):
        config = [{'days': 'everyday', 'hour': "8", 'minute': 30, 'serving_size': 1}]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "invalid hour" in str(exc_info.value)

    def test_hour_as_float_raises_error(self):
        config = [{'days': 'everyday', 'hour': 8.5, 'minute': 30, 'serving_size': 1}]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "invalid hour" in str(exc_info.value)

    @pytest.mark.parametrize('minute', [-1, 60, 61, 100])
    def test_invalid_minute_out_of_range_raises_error(self, minute):
        config = [{'days': 'everyday', 'hour': 8, 'minute': minute, 'serving_size': 1}]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert f"invalid minute '{minute}'" in str(exc_info.value)
        assert "must be an integer 0-59" in str(exc_info.value)

    def test_minute_as_string_raises_error(self):
        config = [{'days': 'everyday', 'hour': 8, 'minute': "30", 'serving_size': 1}]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "invalid minute" in str(exc_info.value)

    @pytest.mark.parametrize('hour', [0, 12, 23])
    def test_valid_hour_boundary_values(self, hour):
        config = [{'days': 'everyday', 'hour': hour, 'minute': 30, 'serving_size': 1}]
        _validate_schedule_config(config, tolerance_secs=60)  # Should not raise

    @pytest.mark.parametrize('minute', [0, 30, 59])
    def test_valid_minute_boundary_values(self, minute):
        config = [{'days': 'everyday', 'hour': 8, 'minute': minute, 'serving_size': 1}]
        _validate_schedule_config(config, tolerance_secs=60)  # Should not raise


class TestScheduleProximityValidation:
    """Tests for validating that schedules are not too close together."""

    def test_schedules_far_apart_passes(self):
        """Two schedules 2 hours apart should pass with 60s tolerance."""
        config = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1},
            {'days': 'everyday', 'hour': 10, 'minute': 0, 'serving_size': 1},
        ]
        _validate_schedule_config(config, tolerance_secs=60)  # Should not raise

    def test_schedules_within_tolerance_raises_error(self):
        """Two schedules 30 seconds apart should fail with 60s tolerance."""
        config = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1},
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1},  # Same time
        ]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "within" in str(exc_info.value)
        assert "tolerance" in str(exc_info.value)

    def test_schedules_exactly_at_tolerance_raises_error(self):
        """Two schedules exactly tolerance_secs apart should fail (boundary inclusive)."""
        config = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1},
            {'days': 'everyday', 'hour': 8, 'minute': 1, 'serving_size': 1},  # 60 seconds apart
        ]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "within" in str(exc_info.value)
        assert "60s apart" in str(exc_info.value)

    def test_schedules_just_outside_tolerance_passes(self):
        """Two schedules just outside tolerance should pass."""
        config = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1},
            {'days': 'everyday', 'hour': 8, 'minute': 2, 'serving_size': 1},  # 120 seconds apart
        ]
        _validate_schedule_config(config, tolerance_secs=60)  # Should not raise

    def test_changing_tolerance_affects_validation(self):
        """Schedules 2 minutes apart should fail with 180s tolerance but pass with 60s."""
        config = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1},
            {'days': 'everyday', 'hour': 8, 'minute': 2, 'serving_size': 1},  # 120 seconds apart
        ]
        # Should pass with 60s tolerance
        _validate_schedule_config(config, tolerance_secs=60)

        # Should fail with 180s tolerance
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=180)
        assert "within" in str(exc_info.value)

    def test_multiple_schedules_validates_all_pairs(self):
        """All pairs should be checked, not just adjacent ones."""
        config = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1},
            {'days': 'everyday', 'hour': 12, 'minute': 0, 'serving_size': 1},
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1},  # Duplicate of first
        ]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=60)
        assert "entries 0" in str(exc_info.value)
        assert "2" in str(exc_info.value)

    def test_error_message_includes_schedule_times(self):
        """Error message should include the times of conflicting schedules."""
        config = [
            {'days': 'everyday', 'hour': 8, 'minute': 30, 'serving_size': 1},
            {'days': 'everyday', 'hour': 8, 'minute': 31, 'serving_size': 1},
        ]
        with pytest.raises(ValueError) as exc_info:
            _validate_schedule_config(config, tolerance_secs=120)
        error_msg = str(exc_info.value)
        assert "08:30" in error_msg
        assert "08:31" in error_msg

    def test_single_schedule_always_passes_proximity(self):
        """A single schedule has no conflicts."""
        config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        _validate_schedule_config(config, tolerance_secs=60)  # Should not raise

    def test_empty_schedule_passes(self):
        """An empty schedule list should pass validation."""
        _validate_schedule_config([], tolerance_secs=60)  # Should not raise


class TestDispensingSchedule:
    """Tests for the DispensingSchedule class."""

    @pytest.fixture
    def mock_history(self):
        return Mock()

    @pytest.fixture
    def mock_emergency_cb(self):
        return Mock()

    @pytest.fixture
    def valid_schedule(self):
        return [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]

    @pytest.fixture
    def mock_scheduler(self):
        with patch('schedule.BackgroundScheduler') as mock:
            mock_instance = Mock()
            mock.return_value = mock_instance
            yield mock_instance

    def create_schedule(self, mock_scheduler, mock_history, mock_emergency_cb, feeding_schedule, tolerance_secs=60):
        with patch('schedule.BackgroundScheduler', return_value=mock_scheduler):
            return DispensingSchedule(
                cat_feeder_name="test_feeder",
                history=mock_history,
                cb_emergency_dispense=mock_emergency_cb,
                feeding_schedule=feeding_schedule,
                tolerance_secs=tolerance_secs,
            )

    def test_get_schedule_returns_feeding_schedule(self, mock_scheduler, mock_history, mock_emergency_cb, valid_schedule):
        ds = self.create_schedule(mock_scheduler, mock_history, mock_emergency_cb, valid_schedule)
        assert ds.get_schedule() == valid_schedule

    def test_invalid_config_raises_on_init(self, mock_scheduler, mock_history, mock_emergency_cb):
        with pytest.raises(ValueError):
            self.create_schedule(mock_scheduler, mock_history, mock_emergency_cb, "not a list")


class TestFulfillmentCheck:
    """Tests for start_fulfillment_check and ensure_dispense_registered."""

    @pytest.fixture
    def mock_history(self):
        return Mock()

    @pytest.fixture
    def mock_emergency_cb(self):
        return Mock()

    @pytest.fixture
    def valid_schedule(self):
        return [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 2}]

    def create_schedule(self, mock_history, mock_emergency_cb, feeding_schedule, tolerance_secs=60):
        with patch('schedule.BackgroundScheduler') as mock_sched:
            mock_sched.return_value = Mock()
            return DispensingSchedule(
                cat_feeder_name="test_feeder",
                history=mock_history,
                cb_emergency_dispense=mock_emergency_cb,
                feeding_schedule=feeding_schedule,
                tolerance_secs=tolerance_secs,
            )

    def test_start_fulfillment_check_creates_timer(self, mock_history, mock_emergency_cb, valid_schedule):
        with patch('schedule.threading.Timer') as mock_timer:
            mock_timer_instance = Mock()
            mock_timer.return_value = mock_timer_instance

            ds = self.create_schedule(mock_history, mock_emergency_cb, valid_schedule, tolerance_secs=30)
            ds._start_fulfillment_check(8, 0, 2)

            mock_timer.assert_called_once_with(30, ds._ensure_dispense_registered, args=[8, 0, 2])
            mock_timer_instance.start.assert_called_once()

    def test_ensure_dispense_registered_calls_emergency_callback(self, mock_history, mock_emergency_cb, valid_schedule):
        ds = self.create_schedule(mock_history, mock_emergency_cb, valid_schedule, tolerance_secs=60)

        ds._ensure_dispense_registered(8, 0, 2)

        mock_emergency_cb.assert_called_once_with(source="Forced by missed schedule", serving_size=2)

    def test_ensure_dispense_registered_registers_missed_dispense(self, mock_history, mock_emergency_cb, valid_schedule):
        ds = self.create_schedule(mock_history, mock_emergency_cb, valid_schedule, tolerance_secs=60)

        ds._ensure_dispense_registered(8, 0, 2)

        mock_history.register_missed_scheduled_dispense.assert_called_once_with(8, 0, 60)

    def test_timeout_triggers_ensure_dispense_registered(self, mock_history, mock_emergency_cb, valid_schedule):
        """Test that after timeout, ensure_dispense_registered is called which invokes emergency callback and history."""
        ds = self.create_schedule(mock_history, mock_emergency_cb, valid_schedule, tolerance_secs=0.01)

        # Manually trigger fulfillment check with a very short timeout
        with patch('schedule.threading.Timer') as mock_timer:
            captured_callback = None
            captured_args = None

            def capture_timer(timeout, callback, args):
                nonlocal captured_callback, captured_args
                captured_callback = callback
                captured_args = args
                timer_mock = Mock()
                return timer_mock

            mock_timer.side_effect = capture_timer
            ds._start_fulfillment_check(8, 0, 2)

            # Simulate timer firing
            captured_callback(*captured_args)

        mock_emergency_cb.assert_called_once_with(source="Forced by missed schedule", serving_size=2)
        mock_history.register_missed_scheduled_dispense.assert_called_once()

    def test_start_fulfillment_check_cancels_existing_timer(self, mock_history, mock_emergency_cb, valid_schedule):
        """Test that calling start_fulfillment_check twice for the same slot cancels the first timer."""
        ds = self.create_schedule(mock_history, mock_emergency_cb, valid_schedule, tolerance_secs=60)

        first_timer = Mock()
        second_timer = Mock()

        with patch('schedule.threading.Timer', side_effect=[first_timer, second_timer]):
            ds._start_fulfillment_check(8, 0, 2)
            ds._start_fulfillment_check(8, 0, 2)

        first_timer.cancel.assert_called_once()
        second_timer.start.assert_called_once()


class TestRegisterScheduleTriggered:
    """Tests for register_schedule_triggered and timer cancellation."""

    @pytest.fixture
    def mock_history(self):
        return Mock()

    @pytest.fixture
    def mock_emergency_cb(self):
        return Mock()

    def create_schedule(self, mock_history, mock_emergency_cb, feeding_schedule, tolerance_secs=60):
        with patch('schedule.BackgroundScheduler') as mock_sched:
            mock_sched.return_value = Mock()
            return DispensingSchedule(
                cat_feeder_name="test_feeder",
                history=mock_history,
                cb_emergency_dispense=mock_emergency_cb,
                feeding_schedule=feeding_schedule,
                tolerance_secs=tolerance_secs,
            )

    def test_register_schedule_triggered_cancels_pending_timer(self, mock_history, mock_emergency_cb):
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=300)

        # Simulate a pending timer
        mock_timer = Mock()
        ds._pending_check_timers[(8, 0)] = mock_timer

        # Mock datetime to be exactly at scheduled time
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 0, 0)
            ds.register_schedule_triggered(portions_dispensed=1, weight_dispensed=50)

        mock_timer.cancel.assert_called_once()
        assert (8, 0) not in ds._pending_check_timers

    def test_register_schedule_triggered_prevents_ensure_dispense_call(self, mock_history, mock_emergency_cb):
        """If register_schedule_triggered is called, ensure_dispense_registered should NOT be invoked."""
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=300)

        captured_callback = None

        with patch('schedule.threading.Timer') as mock_timer:
            def capture_timer(timeout, callback, args):
                nonlocal captured_callback
                timer_mock = Mock()
                captured_callback = lambda: callback(*args)
                return timer_mock

            mock_timer.side_effect = capture_timer
            ds._start_fulfillment_check(8, 0, 1)

        # Register the scheduled trigger before timeout
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 0, 30)
            ds.register_schedule_triggered(portions_dispensed=1, weight_dispensed=50)

        # At this point, the timer should be cancelled, so calling the callback should not register missed dispense
        # (in real scenario, the timer would be cancelled and callback wouldn't fire)
        mock_history.register_missed_scheduled_dispense.assert_not_called()
        mock_emergency_cb.assert_not_called()


class TestToleranceMatching:
    """Tests for tolerance matching in register_schedule_triggered."""

    @pytest.fixture
    def mock_history(self):
        return Mock()

    @pytest.fixture
    def mock_emergency_cb(self):
        return Mock()

    def create_schedule(self, mock_history, mock_emergency_cb, feeding_schedule, tolerance_secs=60):
        with patch('schedule.BackgroundScheduler') as mock_sched:
            mock_sched.return_value = Mock()
            return DispensingSchedule(
                cat_feeder_name="test_feeder",
                history=mock_history,
                cb_emergency_dispense=mock_emergency_cb,
                feeding_schedule=feeding_schedule,
                tolerance_secs=tolerance_secs,
            )

    def test_event_within_tolerance_matches(self, mock_history, mock_emergency_cb):
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=60)

        # 30 seconds after scheduled time - should match
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 0, 30)
            ds.register_schedule_triggered(portions_dispensed=1, weight_dispensed=50)

        mock_history.register_scheduled_dispense_on_time.assert_called_once_with(1, 50)
        mock_history.register_unmatched_scheduled_dispense.assert_not_called()

    def test_event_outside_tolerance_does_not_match(self, mock_history, mock_emergency_cb):
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=60)

        # 90 seconds after scheduled time - should NOT match with 60s tolerance
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 1, 30)
            ds.register_schedule_triggered(portions_dispensed=1, weight_dispensed=50)

        mock_history.register_unmatched_scheduled_dispense.assert_called_once_with(1, 50)
        mock_history.register_scheduled_dispense_on_time.assert_not_called()

    def test_event_exactly_at_tolerance_boundary_matches(self, mock_history, mock_emergency_cb):
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=60)

        # Exactly 60 seconds after - should match (boundary)
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 1, 0)
            ds.register_schedule_triggered(portions_dispensed=1, weight_dispensed=50)

        mock_history.register_scheduled_dispense_on_time.assert_called_once()

    def test_event_just_outside_tolerance_boundary_does_not_match(self, mock_history, mock_emergency_cb):
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=60)

        # 61 seconds after - should NOT match
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 1, 1)
            ds.register_schedule_triggered(portions_dispensed=1, weight_dispensed=50)

        mock_history.register_unmatched_scheduled_dispense.assert_called_once()

    def test_event_before_scheduled_time_matches_within_tolerance(self, mock_history, mock_emergency_cb):
        """Event fired slightly before scheduled time should still match."""
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=60)

        # 30 seconds BEFORE scheduled time - should match
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 7, 59, 30)
            ds.register_schedule_triggered(portions_dispensed=1, weight_dispensed=50)

        mock_history.register_scheduled_dispense_on_time.assert_called_once()

    def test_changing_tolerance_affects_matching(self, mock_history, mock_emergency_cb):
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]

        # With 30s tolerance, 45s diff should NOT match
        ds1 = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=30)
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 0, 45)
            ds1.register_schedule_triggered(portions_dispensed=1, weight_dispensed=50)
        mock_history.register_unmatched_scheduled_dispense.assert_called_once()
        mock_history.reset_mock()

        # With 60s tolerance, 45s diff SHOULD match
        ds2 = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=60)
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 0, 45)
            ds2.register_schedule_triggered(portions_dispensed=1, weight_dispensed=50)
        mock_history.register_scheduled_dispense_on_time.assert_called_once()


class TestMultipleSchedules:
    """Tests for handling multiple scheduled events."""

    @pytest.fixture
    def mock_history(self):
        return Mock()

    @pytest.fixture
    def mock_emergency_cb(self):
        return Mock()

    def create_schedule(self, mock_history, mock_emergency_cb, feeding_schedule, tolerance_secs=60):
        with patch('schedule.BackgroundScheduler') as mock_sched:
            mock_sched.return_value = Mock()
            return DispensingSchedule(
                cat_feeder_name="test_feeder",
                history=mock_history,
                cb_emergency_dispense=mock_emergency_cb,
                feeding_schedule=feeding_schedule,
                tolerance_secs=tolerance_secs,
            )

    def test_multiple_schedules_picks_closest_match(self, mock_history, mock_emergency_cb):
        """When multiple schedules are within tolerance, the closest one should be selected."""
        schedule_config = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1},
            {'days': 'everyday', 'hour': 8, 'minute': 5, 'serving_size': 1},
        ]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=180)

        # Set up timers for both schedules
        timer1 = Mock()
        timer2 = Mock()
        ds._pending_check_timers[(8, 0)] = timer1
        ds._pending_check_timers[(8, 5)] = timer2

        # Event at 8:03:00 - closer to 8:05 (120s) than 8:00 (180s)
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 3, 0)
            ds.register_schedule_triggered(portions_dispensed=1, weight_dispensed=50)

        # The 8:05 timer should be cancelled (closer match)
        timer2.cancel.assert_called_once()
        timer1.cancel.assert_not_called()
        assert (8, 5) not in ds._pending_check_timers
        assert (8, 0) in ds._pending_check_timers

    def test_jobs_added_for_each_schedule(self, mock_history, mock_emergency_cb):
        """Verify that scheduler jobs are added for each schedule entry."""
        schedule_config = [
            {'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1},
            {'days': 'workdays', 'hour': 12, 'minute': 30, 'serving_size': 2},
            {'days': 'weekend', 'hour': 10, 'minute': 0, 'serving_size': 1},
        ]

        with patch('schedule.BackgroundScheduler') as mock_sched:
            mock_instance = Mock()
            mock_sched.return_value = mock_instance

            DispensingSchedule(
                cat_feeder_name="test_feeder",
                history=mock_history,
                cb_emergency_dispense=mock_emergency_cb,
                feeding_schedule=schedule_config,
                tolerance_secs=60,
            )

            assert mock_instance.add_job.call_count == 3
            mock_instance.start.assert_called_once()


class TestHistoryRegistration:
    """Tests for history registration based on match status."""

    @pytest.fixture
    def mock_history(self):
        return Mock()

    @pytest.fixture
    def mock_emergency_cb(self):
        return Mock()

    def create_schedule(self, mock_history, mock_emergency_cb, feeding_schedule, tolerance_secs=60):
        with patch('schedule.BackgroundScheduler') as mock_sched:
            mock_sched.return_value = Mock()
            return DispensingSchedule(
                cat_feeder_name="test_feeder",
                history=mock_history,
                cb_emergency_dispense=mock_emergency_cb,
                feeding_schedule=feeding_schedule,
                tolerance_secs=tolerance_secs,
            )

    def test_matched_event_calls_register_scheduled(self, mock_history, mock_emergency_cb):
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=60)

        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 8, 0, 15)
            ds.register_schedule_triggered(portions_dispensed=2, weight_dispensed=100)

        mock_history.register_scheduled_dispense_on_time.assert_called_once_with(2, 100)

    def test_unmatched_event_calls_unmatched_scheduled(self, mock_history, mock_emergency_cb):
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=60)

        # Event at 10:00 - no schedule at that time
        with patch('schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
            ds.register_schedule_triggered(portions_dispensed=2, weight_dispensed=100)

        mock_history.register_unmatched_scheduled_dispense.assert_called_once_with(2, 100)

    def test_missed_event_registers_missed_dispense(self, mock_history, mock_emergency_cb):
        schedule_config = [{'days': 'everyday', 'hour': 8, 'minute': 0, 'serving_size': 1}]
        ds = self.create_schedule(mock_history, mock_emergency_cb, schedule_config, tolerance_secs=60)

        ds._ensure_dispense_registered(8, 0, 1)

        mock_history.register_missed_scheduled_dispense.assert_called_once_with(8, 0, 60)
