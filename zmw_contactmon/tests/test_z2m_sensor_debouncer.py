"""Unit tests for z2m_sensor_debouncer.py"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from z2m_sensor_debouncer import Z2mContactSensorDebouncer


class TestZ2mContactSensorDebouncer:
    """Test Z2mContactSensorDebouncer class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.cfg = {}
        self.mqtt = Mock()
        self.actions_on_sensor_change = {
            'Sensor1': {
                'normal_state': False,
                'open': {'telegram': {'msg': 'Door opened'}},
                'close': {'telegram': {'msg': 'Door closed'}}
            },
            'Sensor2': {
                'normal_state': True,
                'timeout': {'telegram': {'msg': 'Timeout'}}
            }
        }
        self.callback = Mock()

        with patch('z2m_sensor_debouncer.Z2MProxy'):
            self.debouncer = Z2mContactSensorDebouncer(
                self.cfg,
                self.mqtt,
                self.actions_on_sensor_change,
                self.callback
            )

    def _create_thing(self, name, contact_value):
        """Helper to create mock thing object"""
        thing = Mock()
        thing.name = name
        thing.actions = {'contact': Mock()}
        thing.get = Mock(return_value=contact_value)
        return thing

    def _add_to_monitoring(self, thing):
        """Helper to add thing to monitoring"""
        self.debouncer.monitoring[thing.name] = thing
        if thing.name not in self.debouncer.history:
            self.debouncer.history[thing.name] = []

    def test_sensor_no_config_action(self):
        """Test sensor reports event but has no associated config action"""
        thing = self._create_thing('UnknownSensor', False)
        self._add_to_monitoring(thing)

        self.debouncer._on_contact_change(thing)

        self.callback.assert_not_called()

    def test_sensor_no_action_for_event(self):
        """Test sensor reports event but we don't have an action for the event"""
        thing = self._create_thing('Sensor1', False)
        self._add_to_monitoring(thing)

        # Sensor1 has normal_state=False, so contact=False is 'close' event
        # Remove 'close' action to test this case
        del self.debouncer._actions_on_sensor_change['Sensor1']['close']
        del self.debouncer._actions_on_sensor_change['Sensor1']['open']

        self.debouncer._on_contact_change(thing)

        self.callback.assert_not_called()

    def test_sensor_faulty_value(self):
        """Test sensor reports a faulty value (not True/False)"""
        thing = self._create_thing('Sensor1', 123)
        self._add_to_monitoring(thing)

        self.debouncer._on_contact_change(thing)

        self.callback.assert_not_called()

    def test_sensor_faulty_value_string(self):
        """Test sensor reports a faulty value (string)"""
        thing = self._create_thing('Sensor1', 'unknown')
        self._add_to_monitoring(thing)

        self.debouncer._on_contact_change(thing)

        self.callback.assert_not_called()

    def test_sensor_duplicated_state(self):
        """Test sensor reports duplicated state twice in a row"""
        thing = self._create_thing('Sensor1', True)
        self._add_to_monitoring(thing)

        # First report
        self.debouncer._on_contact_change(thing)
        self.callback.assert_called_once()

        # Second report with same state
        self.callback.reset_mock()
        self.debouncer._on_contact_change(thing)

        self.callback.assert_not_called()

    def test_first_state_normal_ignored(self):
        """Test first state is ignored if it's normal"""
        thing = self._create_thing('Sensor1', False)
        self._add_to_monitoring(thing)

        # Sensor1 has normal_state=False, so this is normal
        self.debouncer._on_contact_change(thing)

        self.callback.assert_not_called()

    def test_first_state_non_normal_actioned(self):
        """Test first state is actioned if it's non-normal"""
        thing = self._create_thing('Sensor1', True)
        self._add_to_monitoring(thing)

        # Sensor1 has normal_state=False, so True is non-normal
        self.debouncer._on_contact_change(thing)

        self.callback.assert_called_once_with(
            thing,
            True,  # now_contact
            'open',  # action
            False,  # prev_contact_state (assumed normal_state)
            True  # entering_non_normal
        )

    def test_valid_state_transition_with_callback(self):
        """Test valid state transition invokes callback with correct parameters"""
        thing = self._create_thing('Sensor1', True)
        self._add_to_monitoring(thing)

        # First transition (non-normal)
        self.debouncer._on_contact_change(thing)
        self.callback.assert_called_once()

        # Second transition (back to normal)
        self.callback.reset_mock()
        thing.get = Mock(return_value=False)
        self.debouncer._on_contact_change(thing)

        self.callback.assert_called_once_with(
            thing,
            False,  # now_contact
            'close',  # action
            True,  # prev_contact_state
            False  # entering_non_normal
        )

    def test_sensor_with_only_timeout_action(self):
        """Test sensor has only timeout action but no direct open/close action"""
        thing = self._create_thing('Sensor2', False)
        self._add_to_monitoring(thing)

        # First report non-normal
        self.debouncer._on_contact_change(thing)

        # Should call callback even though there's no 'open' action (has 'timeout')
        self.callback.assert_called_once_with(
            thing,
            False,  # now_contact
            'open',  # action (False != True, so entering non-normal)
            True,  # prev_contact_state (assumed normal_state)
            True  # entering_non_normal
        )

    def test_multiple_state_changes_tracking(self):
        """Test multiple state changes track previous state correctly"""
        thing = self._create_thing('Sensor1', True)
        self._add_to_monitoring(thing)

        # First change: None -> True
        self.debouncer._on_contact_change(thing)
        assert self.debouncer.monitoring_prev_state['Sensor1'] is True

        # Second change: True -> False
        thing.get = Mock(return_value=False)
        self.debouncer._on_contact_change(thing)
        assert self.debouncer.monitoring_prev_state['Sensor1'] is False

        # Third change: False -> True
        thing.get = Mock(return_value=True)
        self.debouncer._on_contact_change(thing)
        assert self.debouncer.monitoring_prev_state['Sensor1'] is True

    def test_history_recording_for_all_events(self):
        """Test history is recorded for all state changes"""
        thing = self._create_thing('Sensor1', True)
        self._add_to_monitoring(thing)

        # First event
        self.debouncer._on_contact_change(thing)
        history = self.debouncer.get_contact_history()
        assert 'Sensor1' in history
        assert len(history['Sensor1']) == 1
        assert history['Sensor1'][0]['contact'] is True
        assert history['Sensor1'][0]['action'] == 'open'

        # Second event
        thing.get = Mock(return_value=False)
        self.debouncer._on_contact_change(thing)
        history = self.debouncer.get_contact_history()
        assert len(history['Sensor1']) == 2
        assert history['Sensor1'][1]['contact'] is False
        assert history['Sensor1'][1]['action'] == 'close'

    def test_history_no_duplicates(self):
        """Test history doesn't record duplicate states"""
        thing = self._create_thing('Sensor1', True)
        self._add_to_monitoring(thing)

        # First event
        self.debouncer._on_contact_change(thing)

        # Duplicate event (should not be added to history)
        self.debouncer._on_contact_change(thing)

        history = self.debouncer.get_contact_history()
        assert len(history['Sensor1']) == 1

    def test_history_for_sensor_without_config(self):
        """Test history recording for sensors without config"""
        thing = self._create_thing('UnconfiguredSensor', False)
        self._add_to_monitoring(thing)

        # Should still record history even without config
        self.debouncer._on_contact_change(thing)

        history = self.debouncer.get_contact_history()
        assert 'UnconfiguredSensor' in history
        assert len(history['UnconfiguredSensor']) == 1
        # Without config, assumes normal_state=True, so False is entering non-normal
        assert history['UnconfiguredSensor'][0]['action'] == 'open'

    def test_get_sensors_state(self):
        """Test get_sensors_state returns last sensor state"""
        thing1 = self._create_thing('Sensor1', True)
        thing2 = self._create_thing('Sensor2', False)
        self._add_to_monitoring(thing1)
        self._add_to_monitoring(thing2)

        self.debouncer._on_contact_change(thing1)
        self.debouncer._on_contact_change(thing2)

        state = self.debouncer.get_sensors_state()
        assert 'Sensor1' in state
        assert 'Sensor2' in state
        assert state['Sensor1']['contact'] is True
        assert state['Sensor2']['contact'] is False

    def test_get_sensors_state_empty_history(self):
        """Test get_sensors_state with empty history returns empty dict"""
        thing = self._create_thing('Sensor1', True)
        self._add_to_monitoring(thing)

        state = self.debouncer.get_sensors_state()
        assert 'Sensor1' in state
        assert state['Sensor1'] == {}

    def test_normal_state_true_sensor(self):
        """Test sensor with normal_state=True correctly identifies transitions"""
        thing = self._create_thing('Sensor2', False)
        self._add_to_monitoring(thing)

        # Sensor2 has normal_state=True, so False is non-normal (open)
        self.debouncer._on_contact_change(thing)

        self.callback.assert_called_once()
        call_args = self.callback.call_args[0]
        assert call_args[2] == 'open'  # action
        assert call_args[4] is True  # entering_non_normal

        # Transition to normal state (True)
        self.callback.reset_mock()
        thing.get = Mock(return_value=True)
        self.debouncer._on_contact_change(thing)

        call_args = self.callback.call_args[0]
        assert call_args[2] == 'close'  # action
        assert call_args[4] is False  # entering_non_normal

    def test_history_includes_timestamp(self):
        """Test history entries include timestamp"""
        thing = self._create_thing('Sensor1', True)
        self._add_to_monitoring(thing)

        self.debouncer._on_contact_change(thing)

        history = self.debouncer.get_contact_history()
        assert 'changed' in history['Sensor1'][0]
        assert history['Sensor1'][0]['changed'] is not None

    def test_history_includes_in_normal_state(self):
        """Test history entries include in_normal_state flag"""
        thing = self._create_thing('Sensor1', True)
        self._add_to_monitoring(thing)

        # Sensor1 has normal_state=False, so True is non-normal
        self.debouncer._on_contact_change(thing)

        history = self.debouncer.get_contact_history()
        assert history['Sensor1'][0]['in_normal_state'] is False

        # Transition to normal
        thing.get = Mock(return_value=False)
        self.debouncer._on_contact_change(thing)

        history = self.debouncer.get_contact_history()
        assert history['Sensor1'][1]['in_normal_state'] is True
