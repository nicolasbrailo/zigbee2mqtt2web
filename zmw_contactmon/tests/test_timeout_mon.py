"""Unit tests for timeout_mon.py"""
import pytest
from unittest.mock import Mock, MagicMock, call
from datetime import datetime, timedelta
from timeout_mon import TimeoutMonitor


class TestTimeoutMonitor:
    """Test TimeoutMonitor class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.scheduler = Mock()
        self.executor = Mock()
        self.actions = {
            'Sensor1': {
                'normal_state': False,
                'timeout_secs': 300,
                'timeout': {'telegram': {'msg': 'Timeout'}}
            },
            'Sensor2': {
                'normal_state': True,
                'open': {'telegram': {'msg': 'Door opened'}}
                # No timeout_secs
            }
        }

        self.monitor = TimeoutMonitor(
            self.scheduler,
            self.executor,
            self.actions
        )

    def _create_thing(self, name):
        """Helper to create mock thing object"""
        thing = Mock()
        thing.name = name
        return thing

    def test_ignore_sensor_no_timeout_secs(self):
        """Test sensor with no timeout_secs is ignored"""
        thing = self._create_thing('Sensor2')

        self.monitor.notify_change(thing, entering_non_normal=True)

        # Should not schedule any job
        self.scheduler.add_job.assert_not_called()
        assert 'Sensor2' not in self.monitor._timeout_jobs

    def test_ignore_duplicated_non_normal_event(self):
        """Test duplicated non-normal events are ignored"""
        thing = self._create_thing('Sensor1')
        mock_job = Mock()
        mock_job.id = 'job1'
        self.scheduler.add_job.return_value = mock_job

        # First event - should schedule
        self.monitor.notify_change(thing, entering_non_normal=True)
        self.scheduler.add_job.assert_called_once()

        # Second event - should ignore (not schedule again)
        self.scheduler.reset_mock()
        self.monitor.notify_change(thing, entering_non_normal=True)
        self.scheduler.add_job.assert_not_called()

    def test_duplicated_event_does_not_reset_timeout(self):
        """Test duplicated event doesn't reset timeout"""
        thing = self._create_thing('Sensor1')
        mock_job = Mock()
        mock_job.id = 'job1'
        self.scheduler.add_job.return_value = mock_job

        # First event
        self.monitor.notify_change(thing, entering_non_normal=True)
        first_job = self.monitor._timeout_jobs['Sensor1']

        # Second event (duplicate)
        self.monitor.notify_change(thing, entering_non_normal=True)

        # Should still have the same job (not a new one)
        assert self.monitor._timeout_jobs['Sensor1'] == first_job
        # Should not have removed the old job
        self.scheduler.remove_job.assert_not_called()

    def test_add_sensor_to_monitoring_on_non_normal(self):
        """Test sensor is added to monitored list when entering non-normal state"""
        thing = self._create_thing('Sensor1')
        mock_job = Mock()
        mock_job.id = 'job1'
        self.scheduler.add_job.return_value = mock_job

        # Should not be monitored initially
        assert 'Sensor1' not in self.monitor._timeout_jobs

        self.monitor.notify_change(thing, entering_non_normal=True)

        # Should now be monitored
        assert 'Sensor1' in self.monitor._timeout_jobs
        assert self.monitor._timeout_jobs['Sensor1']['job'] == mock_job

    def test_timeout_scheduled_with_correct_duration(self):
        """Test timeout job is scheduled with correct duration"""
        thing = self._create_thing('Sensor1')
        mock_job = Mock()
        self.scheduler.add_job.return_value = mock_job

        self.monitor.notify_change(thing, entering_non_normal=True)

        # Verify scheduler was called
        self.scheduler.add_job.assert_called_once()
        call_args = self.scheduler.add_job.call_args

        # Check run_date is approximately 300 seconds from now
        run_date = call_args[1]['run_date']
        expected_time = datetime.now() + timedelta(seconds=300)
        # Allow 1 second variance for test execution time
        assert abs((run_date - expected_time).total_seconds()) < 1

    def test_timeout_triggers_executor(self):
        """Test timeout triggers executor.on_transition"""
        thing = self._create_thing('Sensor1')

        # Capture the lambda function passed to add_job
        timeout_callback = None
        def capture_callback(callback, *args, **kwargs):
            nonlocal timeout_callback
            timeout_callback = callback
            mock_job = Mock()
            mock_job.id = 'job1'
            return mock_job

        self.scheduler.add_job.side_effect = capture_callback

        # Trigger non-normal state
        self.monitor.notify_change(thing, entering_non_normal=True)

        # Simulate timeout by calling the captured callback
        assert timeout_callback is not None
        timeout_callback()

        # Executor should be called with timeout action
        self.executor.on_transition.assert_called_once_with('Sensor1', 'timeout')

    def test_timeout_job_removed_after_trigger(self):
        """Test timeout job is removed from monitoring after it triggers"""
        thing = self._create_thing('Sensor1')

        # Capture the lambda function
        timeout_callback = None
        def capture_callback(callback, *args, **kwargs):
            nonlocal timeout_callback
            timeout_callback = callback
            mock_job = Mock()
            mock_job.id = 'job1'
            return mock_job

        self.scheduler.add_job.side_effect = capture_callback

        self.monitor.notify_change(thing, entering_non_normal=True)
        assert 'Sensor1' in self.monitor._timeout_jobs

        # Trigger timeout
        timeout_callback()

        # Should still be in monitoring but with job set to None
        assert 'Sensor1' in self.monitor._timeout_jobs
        assert self.monitor._timeout_jobs['Sensor1']['job'] is None

    def test_timeout_job_removed_on_normal_transition(self):
        """Test timeout job is removed when sensor transitions back to normal"""
        thing = self._create_thing('Sensor1')
        mock_job = Mock()
        mock_job.id = 'job1'
        self.scheduler.add_job.return_value = mock_job

        # Enter non-normal state
        self.monitor.notify_change(thing, entering_non_normal=True)
        assert 'Sensor1' in self.monitor._timeout_jobs

        # Return to normal state
        self.monitor.notify_change(thing, entering_non_normal=False)

        # Job should be removed from scheduler
        self.scheduler.remove_job.assert_called_once_with('job1')
        # Job should be removed from monitoring
        assert 'Sensor1' not in self.monitor._timeout_jobs

    def test_normal_transition_without_monitoring_ignored(self):
        """Test normal transition for non-monitored sensor is ignored"""
        thing = self._create_thing('Sensor1')

        # Sensor is not being monitored
        assert 'Sensor1' not in self.monitor._timeout_jobs

        # Report normal state
        self.monitor.notify_change(thing, entering_non_normal=False)

        # Should not try to remove any job
        self.scheduler.remove_job.assert_not_called()

    def test_cancel_timeout_handles_already_removed_job(self):
        """Test _cancel_timeout handles job removal errors gracefully"""
        thing = self._create_thing('Sensor1')
        mock_job = Mock()
        mock_job.id = 'job1'
        self.scheduler.add_job.return_value = mock_job

        # Set up job
        self.monitor.notify_change(thing, entering_non_normal=True)

        # Make remove_job raise exception (job already removed)
        self.scheduler.remove_job.side_effect = Exception("Job not found")

        # Should not raise exception
        self.monitor.notify_change(thing, entering_non_normal=False)

        # Job should still be removed from internal tracking
        assert 'Sensor1' not in self.monitor._timeout_jobs

    def test_multiple_sensors_monitored_independently(self):
        """Test multiple sensors can be monitored independently"""
        # Add timeout_secs to Sensor2 for this test
        self.monitor._actions_on_sensor_change['Sensor2']['timeout_secs'] = 200

        thing1 = self._create_thing('Sensor1')
        thing2 = self._create_thing('Sensor2')

        mock_job1 = Mock()
        mock_job1.id = 'job1'
        mock_job2 = Mock()
        mock_job2.id = 'job2'

        self.scheduler.add_job.side_effect = [mock_job1, mock_job2]

        # Both enter non-normal state
        self.monitor.notify_change(thing1, entering_non_normal=True)
        self.monitor.notify_change(thing2, entering_non_normal=True)

        # Both should be monitored
        assert 'Sensor1' in self.monitor._timeout_jobs
        assert 'Sensor2' in self.monitor._timeout_jobs

        # Sensor1 returns to normal
        self.monitor.notify_change(thing1, entering_non_normal=False)

        # Only Sensor1 should be removed
        assert 'Sensor1' not in self.monitor._timeout_jobs
        assert 'Sensor2' in self.monitor._timeout_jobs

    def test_timeout_callback_includes_sensor_name(self):
        """Test timeout callback correctly identifies which sensor timed out"""
        thing1 = self._create_thing('Sensor1')

        # Add another sensor with timeout
        self.monitor._actions_on_sensor_change['Sensor3'] = {
            'normal_state': False,
            'timeout_secs': 150,
            'timeout': {'telegram': {'msg': 'Timeout'}}
        }
        thing3 = self._create_thing('Sensor3')

        # Capture callbacks
        callbacks = {}
        def capture_callback(callback, *args, **kwargs):
            mock_job = Mock()
            mock_job.id = f'job{len(callbacks)}'
            # Store callback - we need to identify which sensor it's for
            # by looking at the call order
            sensor_name = thing1.name if len(callbacks) == 0 else thing3.name
            callbacks[sensor_name] = callback
            return mock_job

        self.scheduler.add_job.side_effect = capture_callback

        # Both sensors enter non-normal
        self.monitor.notify_change(thing1, entering_non_normal=True)
        self.monitor.notify_change(thing3, entering_non_normal=True)

        # Trigger Sensor3 timeout
        callbacks['Sensor3']()

        # Only Sensor3 timeout should be executed
        self.executor.on_transition.assert_called_once_with('Sensor3', 'timeout')

    def test_cancel_timeout_when_not_monitored(self):
        """Test _cancel_timeout when sensor is not being monitored"""
        # Should not raise exception
        self.monitor._cancel_timeout('NonexistentSensor')

        # Should not try to remove any job
        self.scheduler.remove_job.assert_not_called()

    def test_scheduler_job_type_is_date(self):
        """Test timeout job is scheduled as 'date' type"""
        thing = self._create_thing('Sensor1')
        mock_job = Mock()
        self.scheduler.add_job.return_value = mock_job

        self.monitor.notify_change(thing, entering_non_normal=True)

        # Check second argument is 'date'
        call_args = self.scheduler.add_job.call_args
        assert call_args[0][1] == 'date'

    def test_get_monitoring_sensors_empty(self):
        """Test get_monitoring_sensors returns empty dict when no sensors monitored"""
        result = self.monitor.get_monitoring_sensors()
        assert result == {}

    def test_get_monitoring_sensors_shows_time_remaining(self):
        """Test get_monitoring_sensors shows time remaining for pending timeouts"""
        thing = self._create_thing('Sensor1')
        mock_job = Mock()
        mock_job.id = 'job1'
        self.scheduler.add_job.return_value = mock_job

        self.monitor.notify_change(thing, entering_non_normal=True)

        result = self.monitor.get_monitoring_sensors()

        assert 'Sensor1' in result
        # Should show sensor reports open
        assert 'reports open' in result['Sensor1']

    def test_get_monitoring_sensors_shows_expired(self):
        """Test get_monitoring_sensors shows expired message after timeout triggers"""
        thing = self._create_thing('Sensor1')

        timeout_callback = None
        def capture_callback(callback, *args, **kwargs):
            nonlocal timeout_callback
            timeout_callback = callback
            mock_job = Mock()
            mock_job.id = 'job1'
            return mock_job

        self.scheduler.add_job.side_effect = capture_callback

        self.monitor.notify_change(thing, entering_non_normal=True)
        timeout_callback()

        result = self.monitor.get_monitoring_sensors()

        assert 'Sensor1' in result
        assert 'timeout expired' in result['Sensor1']
        assert '300' in result['Sensor1']  # timeout_secs value

    def test_get_monitoring_sensors_removed_after_normal(self):
        """Test sensor removed from get_monitoring_sensors after returning to normal"""
        thing = self._create_thing('Sensor1')
        mock_job = Mock()
        mock_job.id = 'job1'
        self.scheduler.add_job.return_value = mock_job

        self.monitor.notify_change(thing, entering_non_normal=True)
        assert 'Sensor1' in self.monitor.get_monitoring_sensors()

        self.monitor.notify_change(thing, entering_non_normal=False)
        assert 'Sensor1' not in self.monitor.get_monitoring_sensors()

    def test_get_monitoring_sensors_multiple_sensors(self):
        """Test get_monitoring_sensors with multiple sensors in different states"""
        self.monitor._actions_on_sensor_change['Sensor2']['timeout_secs'] = 200

        thing1 = self._create_thing('Sensor1')
        thing2 = self._create_thing('Sensor2')

        timeout_callback1 = None
        def capture_callback(callback, *args, **kwargs):
            nonlocal timeout_callback1
            mock_job = Mock()
            mock_job.id = f'job{len(self.monitor._timeout_jobs)}'
            if timeout_callback1 is None:
                timeout_callback1 = callback
            return mock_job

        self.scheduler.add_job.side_effect = capture_callback

        # Both enter non-normal
        self.monitor.notify_change(thing1, entering_non_normal=True)
        self.monitor.notify_change(thing2, entering_non_normal=True)

        # Trigger timeout for Sensor1 only
        timeout_callback1()

        result = self.monitor.get_monitoring_sensors()

        # Sensor1 should show expired
        assert 'Sensor1' in result
        assert 'timeout expired' in result['Sensor1']

        # Sensor2 should show reports open
        assert 'Sensor2' in result
        assert 'reports open' in result['Sensor2']
