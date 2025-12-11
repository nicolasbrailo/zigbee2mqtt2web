"""Unit tests for door_open_scene.py"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
import time

from door_open_scene import DoorOpenSceneLightManager, DoorOpenScene


class TestDoorOpenSceneLightManager:
    """Test DoorOpenSceneLightManager class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.cfg = {
            "door_open_scene_thing_to_manage": ["Light1", "Light2"],
        }
        self.mqtt_client = Mock()

    def _create_mock_thing(self, name, thing_type='light', is_on=False):
        """Helper to create mock thing object"""
        thing = Mock()
        thing.name = name
        thing.thing_type = thing_type
        thing.is_light_on = Mock(return_value=is_on)
        thing.turn_on = Mock()
        thing.turn_off = Mock()
        thing.on_any_change_from_mqtt = None
        return thing

    @patch('door_open_scene.Z2MProxy')
    def test_basic_flow_start_and_stop(self, mock_z2m_class):
        """Basic flow: a list of things is added (and found), when calling start they receive
        a list of updates via broadcast_things, and when stop is called a second broadcast is done."""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        # Simulate Z2M network discovery with lights
        light1 = self._create_mock_thing("Light1")
        light2 = self._create_mock_thing("Light2")
        known_things = {"Light1": light1, "Light2": light2}

        # Get the callback and invoke it
        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things)

        # Verify lights are tracked
        assert "Light1" in mgr._known_things
        assert "Light2" in mgr._known_things

        # Call start
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1000
            mgr.start()

        # Lights should be turned on
        light1.turn_on.assert_called_once()
        light2.turn_on.assert_called_once()

        # broadcast_things should be called with managed light names
        mock_z2m.broadcast_things.assert_called_once()
        broadcast_call_args = list(mock_z2m.broadcast_things.call_args[0][0])
        assert "Light1" in broadcast_call_args
        assert "Light2" in broadcast_call_args

        # Reset mock to check stop() call
        mock_z2m.broadcast_things.reset_mock()

        # Call stop
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 2000
            mgr.stop()

        # Lights should be turned off
        light1.turn_off.assert_called_once()
        light2.turn_off.assert_called_once()

        # broadcast_things should be called again on stop
        mock_z2m.broadcast_things.assert_called_once()

    @patch('door_open_scene.Z2MProxy')
    def test_only_lights_are_managed(self, mock_z2m_class):
        """Only things that are lights are managed, if a non-light thing is added then it's ignored"""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        # Simulate Z2M network discovery with a light and a non-light
        light1 = self._create_mock_thing("Light1", thing_type='light')
        sensor = self._create_mock_thing("Light2", thing_type='sensor')  # Not a light!
        known_things = {"Light1": light1, "Light2": sensor}

        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things)

        # Only the light should be in known_things
        assert "Light1" in mgr._known_things
        assert "Light2" not in mgr._known_things

        # Call start
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1000
            mgr.start()

        # Only light1 should be turned on
        light1.turn_on.assert_called_once()
        sensor.turn_on.assert_not_called()

    @patch('door_open_scene.Z2MProxy')
    def test_unknown_things_are_ignored(self, mock_z2m_class):
        """Things that are not part of known_things are ignored, and they never get managed"""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        # Config requests Light1 and Light2
        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        # But Z2M only discovers Light1
        light1 = self._create_mock_thing("Light1")
        known_things = {"Light1": light1}

        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things)

        # Only Light1 should be tracked
        assert "Light1" in mgr._known_things
        assert "Light2" not in mgr._known_things

        # Call start
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1000
            mgr.start()

        # Only light1 should be managed
        light1.turn_on.assert_called_once()
        broadcast_call_args = list(mock_z2m.broadcast_things.call_args[0][0])
        assert "Light1" in broadcast_call_args
        assert "Light2" not in broadcast_call_args

    @patch('door_open_scene.Z2MProxy')
    def test_updates_ignored_during_ignore_period(self, mock_z2m_class):
        """Updates are ignored for a period of time after start() and stop() are called,
        and when this happens lights don't get removed from managed list"""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        light1 = self._create_mock_thing("Light1")
        known_things = {"Light1": light1}

        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things)

        # Capture the on_any_change_from_mqtt callback
        mqtt_callback = light1.on_any_change_from_mqtt

        # Call start at time 1000
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1000
            mgr.start()

        # Light should be in managing list
        assert "Light1" in mgr._managing_things

        # Simulate MQTT update during ignore period (within 3 seconds)
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1001  # Only 1 second after start
            mqtt_callback()

        # Light should still be in managing list (update was ignored)
        assert "Light1" in mgr._managing_things

    @patch('door_open_scene.Z2MProxy')
    def test_lights_already_on_are_skipped(self, mock_z2m_class):
        """Lights that are already on are skipped during start() - prevents the scene
        from taking over lights already in use by something else"""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        # Light1 is off, Light2 is already on
        light1 = self._create_mock_thing("Light1", is_on=False)
        light2 = self._create_mock_thing("Light2", is_on=True)
        known_things = {"Light1": light1, "Light2": light2}

        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things)

        # Call start
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1000
            mgr.start()

        # Light1 should be turned on (it was off)
        light1.turn_on.assert_called_once()
        # Light2 should NOT be turned on (it was already on)
        light2.turn_on.assert_not_called()

        # Only Light1 should be in managing list
        assert "Light1" in mgr._managing_things
        assert "Light2" not in mgr._managing_things

        # Only Light1 should be broadcast
        broadcast_call_args = list(mock_z2m.broadcast_things.call_args[0][0])
        assert "Light1" in broadcast_call_args
        assert "Light2" not in broadcast_call_args

    @patch('door_open_scene.Z2MProxy')
    def test_callback_registration_on_discovery(self, mock_z2m_class):
        """Verify that on_any_change_from_mqtt callback is properly set on each discovered light"""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        light1 = self._create_mock_thing("Light1")
        light2 = self._create_mock_thing("Light2")
        known_things = {"Light1": light1, "Light2": light2}

        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things)

        # Both lights should have callbacks registered
        assert light1.on_any_change_from_mqtt is not None
        assert light2.on_any_change_from_mqtt is not None
        assert callable(light1.on_any_change_from_mqtt)
        assert callable(light2.on_any_change_from_mqtt)

    @patch('door_open_scene.Z2MProxy')
    def test_updates_outside_ignore_period_remove_light(self, mock_z2m_class):
        """When a light receives an update outside of the ignore period, they become
        unmanaged and don't get updated by stop() anymore"""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        light1 = self._create_mock_thing("Light1")
        light2 = self._create_mock_thing("Light2")
        known_things = {"Light1": light1, "Light2": light2}

        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things)

        # Capture the on_any_change_from_mqtt callbacks
        light1_mqtt_callback = light1.on_any_change_from_mqtt
        light2_mqtt_callback = light2.on_any_change_from_mqtt

        # Call start at time 1000
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1000
            mgr.start()

        # Both lights should be in managing list
        assert "Light1" in mgr._managing_things
        assert "Light2" in mgr._managing_things

        # Simulate MQTT update for Light1 outside ignore period (after 3 seconds)
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1005  # 5 seconds after start
            light1_mqtt_callback()

        # Light1 should be removed from managing list
        assert "Light1" not in mgr._managing_things
        # Light2 should still be managed
        assert "Light2" in mgr._managing_things

        # Reset turn_off mocks
        light1.turn_off.reset_mock()
        light2.turn_off.reset_mock()

        # Call stop
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 2000
            mgr.stop()

        # Light1 should NOT be turned off (it was unmanaged)
        light1.turn_off.assert_not_called()
        # Light2 should be turned off
        light2.turn_off.assert_called_once()

    @patch('door_open_scene.Z2MProxy')
    def test_stop_without_start(self, mock_z2m_class):
        """stop() called without start() handles gracefully when _managing_things is empty"""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        light1 = self._create_mock_thing("Light1")
        known_things = {"Light1": light1}

        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things)

        # Call stop without calling start first
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1000
            mgr.stop()  # Should not raise exception

        # No lights should be turned off (none were managed)
        light1.turn_off.assert_not_called()

        # broadcast_things should still be called (with empty list)
        mock_z2m.broadcast_things.assert_called_once()

    @patch('door_open_scene.Z2MProxy')
    def test_start_called_twice_without_stop_is_noop(self, mock_z2m_class):
        """start() called twice without stop() is a noop - the second call does nothing"""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        light1 = self._create_mock_thing("Light1")
        light2 = self._create_mock_thing("Light2")
        known_things = {"Light1": light1, "Light2": light2}

        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things)

        # Call start first time
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1000
            mgr.start()

        assert mgr._is_running is True
        assert "Light1" in mgr._managing_things
        assert "Light2" in mgr._managing_things
        light1.turn_on.assert_called_once()
        light2.turn_on.assert_called_once()

        # Reset mocks to track second call
        light1.turn_on.reset_mock()
        light2.turn_on.reset_mock()
        mock_z2m.broadcast_things.reset_mock()

        # Call start again without stop - should be a noop
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 2000
            mgr.start()

        # No lights should be turned on again (start was a noop)
        light1.turn_on.assert_not_called()
        light2.turn_on.assert_not_called()

        # broadcast_things should not be called again
        mock_z2m.broadcast_things.assert_not_called()

        # Managing things should be unchanged
        assert "Light1" in mgr._managing_things
        assert "Light2" in mgr._managing_things

    @patch('door_open_scene.Z2MProxy')
    def test_start_works_again_after_stop(self, mock_z2m_class):
        """After stop() is called, start() works again"""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        light1 = self._create_mock_thing("Light1")
        known_things = {"Light1": light1}

        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things)

        # Call start first time
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 1000
            mgr.start()

        assert mgr._is_running is True
        light1.turn_on.assert_called_once()

        # Call stop
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 2000
            mgr.stop()

        assert mgr._is_running is False

        # Reset mocks
        light1.turn_on.reset_mock()

        # Call start again - should work now
        with patch('door_open_scene.time') as mock_time:
            mock_time.time.return_value = 3000
            mgr.start()

        assert mgr._is_running is True
        light1.turn_on.assert_called_once()

    @patch('door_open_scene.Z2MProxy')
    def test_discovery_updates_known_things_list(self, mock_z2m_class):
        """When _on_z2m_network_discovery is called multiple times, the list of
        known_things is updated when the list of things changes"""
        mock_z2m = Mock()
        mock_z2m_class.return_value = mock_z2m

        mgr = DoorOpenSceneLightManager(self.cfg, self.mqtt_client)

        # First discovery: only Light1
        light1 = self._create_mock_thing("Light1")
        known_things_1 = {"Light1": light1}

        cb_on_discovery = mock_z2m_class.call_args[1]['cb_on_z2m_network_discovery']
        cb_on_discovery(True, known_things_1)

        assert "Light1" in mgr._known_things
        assert "Light2" not in mgr._known_things

        # Second discovery: Light1 and Light2
        light2 = self._create_mock_thing("Light2")
        known_things_2 = {"Light1": light1, "Light2": light2}

        cb_on_discovery(False, known_things_2)

        # Both lights should now be in known_things
        assert "Light1" in mgr._known_things
        assert "Light2" in mgr._known_things

        # Both should have callbacks registered
        assert light1.on_any_change_from_mqtt is not None
        assert light2.on_any_change_from_mqtt is not None


class TestDoorOpenScene:
    """Test DoorOpenScene class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.cfg = {
            "door_open_scene_thing_to_manage": ["Light1"],
            "door_open_scene_timeout_secs": 30,
            "latlon": [45.0, 9.0],
        }
        self.mqtt_client = Mock()

    @patch('door_open_scene.is_sun_out')
    @patch('door_open_scene.DoorOpenSceneLightManager')
    @patch('door_open_scene.threading.Timer')
    def test_basic_flow_maybe_start_and_timeout(self, mock_timer_class, mock_light_mgr_class, mock_is_sun_out):
        """Basic flow: calling maybe_start schedules a timer and calls light_mgr,
        when the timer expires it calls light_mgr stop()"""
        mock_is_sun_out.return_value = False
        mock_light_mgr = Mock()
        mock_light_mgr_class.return_value = mock_light_mgr
        mock_timer = Mock()
        mock_timer_class.return_value = mock_timer

        scene = DoorOpenScene(self.cfg, self.mqtt_client)

        # Call maybe_start
        scene.maybe_start()

        # Timer should be created with correct timeout
        mock_timer_class.assert_called_once_with(
            30,  # door_open_scene_timeout_secs
            scene._on_door_open_scene_timeout
        )
        # Timer should be started
        mock_timer.start.assert_called_once()

        # light_mgr.start() should be called
        mock_light_mgr.start.assert_called_once()

        # Simulate timer expiry by calling the timeout callback
        scene._on_door_open_scene_timeout()

        # light_mgr.stop() should be called
        mock_light_mgr.stop.assert_called_once()

        # Timer should be cleared
        assert scene._door_open_scene_timer is None

    @patch('door_open_scene.is_sun_out')
    @patch('door_open_scene.DoorOpenSceneLightManager')
    @patch('door_open_scene.threading.Timer')
    def test_maybe_start_noop_when_sun_is_out(self, mock_timer_class, mock_light_mgr_class, mock_is_sun_out):
        """maybe_start is a noop if is_sun_out is True"""
        mock_is_sun_out.return_value = True
        mock_light_mgr = Mock()
        mock_light_mgr_class.return_value = mock_light_mgr

        scene = DoorOpenScene(self.cfg, self.mqtt_client)

        # Call maybe_start
        scene.maybe_start()

        # Timer should NOT be created
        # Note: Timer is called once in __init__ for is_sun_out check, but not for scheduling
        mock_timer_class.assert_not_called()

        # light_mgr.start() should NOT be called
        mock_light_mgr.start.assert_not_called()

    @patch('door_open_scene.is_sun_out')
    @patch('door_open_scene.DoorOpenSceneLightManager')
    @patch('door_open_scene.threading.Timer')
    def test_pet_timer_extends_timeout(self, mock_timer_class, mock_light_mgr_class, mock_is_sun_out):
        """The timeout gets extended when calling pet_timer"""
        mock_is_sun_out.return_value = False
        mock_light_mgr = Mock()
        mock_light_mgr_class.return_value = mock_light_mgr
        mock_timer1 = Mock()
        mock_timer2 = Mock()
        mock_timer_class.side_effect = [mock_timer1, mock_timer2]

        scene = DoorOpenScene(self.cfg, self.mqtt_client)

        # Call maybe_start to start the timer
        scene.maybe_start()
        assert scene._door_open_scene_timer is mock_timer1
        mock_timer1.start.assert_called_once()

        # Call pet_timer
        scene.pet_timer()

        # Original timer should be cancelled
        mock_timer1.cancel.assert_called_once()

        # New timer should be created and started
        assert scene._door_open_scene_timer is mock_timer2
        mock_timer2.start.assert_called_once()

    @patch('door_open_scene.is_sun_out')
    @patch('door_open_scene.DoorOpenSceneLightManager')
    @patch('door_open_scene.threading.Timer')
    def test_maybe_start_extends_timeout_when_timer_active(self, mock_timer_class, mock_light_mgr_class, mock_is_sun_out):
        """When maybe_start is called and the timer is already in progress, it extends the timeout"""
        mock_is_sun_out.return_value = False
        mock_light_mgr = Mock()
        mock_light_mgr_class.return_value = mock_light_mgr
        mock_timer1 = Mock()
        mock_timer2 = Mock()
        mock_timer_class.side_effect = [mock_timer1, mock_timer2]

        scene = DoorOpenScene(self.cfg, self.mqtt_client)

        # Call maybe_start to start the timer
        scene.maybe_start()
        assert scene._door_open_scene_timer is mock_timer1
        mock_timer1.start.assert_called_once()
        mock_light_mgr.start.assert_called_once()

        # Reset mock to track second call
        mock_light_mgr.start.reset_mock()

        # Call maybe_start again while timer is active
        scene.maybe_start()

        # Original timer should be cancelled (via pet_timer internal call)
        mock_timer1.cancel.assert_called_once()

        # New timer should be created and started
        assert scene._door_open_scene_timer is mock_timer2
        mock_timer2.start.assert_called_once()

        # light_mgr.start() should NOT be called again
        mock_light_mgr.start.assert_not_called()

    @patch('door_open_scene.is_sun_out')
    @patch('door_open_scene.DoorOpenSceneLightManager')
    @patch('door_open_scene.threading.Timer')
    def test_pet_timer_noop_when_no_timer_active(self, mock_timer_class, mock_light_mgr_class, mock_is_sun_out):
        """pet_timer is a noop when no timer is active"""
        mock_is_sun_out.return_value = False
        mock_light_mgr = Mock()
        mock_light_mgr_class.return_value = mock_light_mgr

        scene = DoorOpenScene(self.cfg, self.mqtt_client)

        # Don't call maybe_start, so no timer is active
        assert scene._door_open_scene_timer is None

        # Call pet_timer - should not raise exception
        scene.pet_timer()

        # No timer should be created
        mock_timer_class.assert_not_called()

    @patch('door_open_scene.is_sun_out')
    @patch('door_open_scene.DoorOpenSceneLightManager')
    @patch('door_open_scene.threading.Timer')
    def test_timer_cleared_after_timeout(self, mock_timer_class, mock_light_mgr_class, mock_is_sun_out):
        """Verify _door_open_scene_timer is set to None after timeout fires"""
        mock_is_sun_out.return_value = False
        mock_light_mgr = Mock()
        mock_light_mgr_class.return_value = mock_light_mgr
        mock_timer = Mock()
        mock_timer_class.return_value = mock_timer

        scene = DoorOpenScene(self.cfg, self.mqtt_client)

        # Call maybe_start
        scene.maybe_start()

        # Timer should be set
        assert scene._door_open_scene_timer is not None

        # Simulate timer expiry
        scene._on_door_open_scene_timeout()

        # Timer should be cleared to None
        assert scene._door_open_scene_timer is None

        # Calling pet_timer after timeout should be a noop (no exception)
        scene.pet_timer()
        # No new timer should be created by pet_timer
        assert scene._door_open_scene_timer is None

    @patch('door_open_scene.is_sun_out')
    @patch('door_open_scene.DoorOpenSceneLightManager')
    @patch('door_open_scene.threading.Timer')
    def test_is_sun_out_called_with_correct_latlon(self, mock_timer_class, mock_light_mgr_class, mock_is_sun_out):
        """Verify is_sun_out is called with the correct lat/lon from config"""
        mock_is_sun_out.return_value = False
        mock_light_mgr = Mock()
        mock_light_mgr_class.return_value = mock_light_mgr
        mock_timer = Mock()
        mock_timer_class.return_value = mock_timer

        scene = DoorOpenScene(self.cfg, self.mqtt_client)

        # is_sun_out is called once in __init__
        mock_is_sun_out.assert_called_with(45.0, 9.0)

        mock_is_sun_out.reset_mock()

        # Call maybe_start
        scene.maybe_start()

        # is_sun_out should be called again with correct coordinates
        mock_is_sun_out.assert_called_with(45.0, 9.0)
