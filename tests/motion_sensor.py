from zigbee2mqtt2web_extras.motion_sensors import MultiMotionSensor
from zigbee2mqtt2web.zigbee2mqtt_thing import parse_from_zigbee2mqtt

from .setup import get_motion_sensor
from .setup import get_another_motion_sensor

import json
import unittest

class FakeRegistry:
    def __init__(self):
        self.installed_cb = None
        self.last_get_thing = None
        self.thing1 = parse_from_zigbee2mqtt(0, get_motion_sensor())
        self.thing2 = parse_from_zigbee2mqtt(0, get_another_motion_sensor())

    def on_mqtt_network_discovered(self, cb):
        self.installed_cb = cb

    def get_thing(self, name):
        self.last_get_thing = name
        if name == self.thing1.name:
            return self.thing1
        if name == self.thing2.name:
            return self.thing2
        raise RuntimeError


class Sensor_ExposeActiveBit:
    def __init__(self, sensor):
        self.sensor_active = False
        def log_detect():
            self.sensor_active = True

        def log_cleared():
            self.sensor_active = False

        sensor.on_activity_detected = log_detect
        sensor.on_activity_cleared = log_cleared


class TestMotionSensor(unittest.TestCase):
    def test_init(self):
        registry = FakeRegistry()

        with self.assertRaises(TypeError):
            sensor = MultiMotionSensor(registry, 'MotionSensor1')

        sensor = MultiMotionSensor(registry, ['MotionSensor1'])
        self.assertEqual(registry.installed_cb, sensor._install_motion_cbs)
        self.assertEqual(registry.last_get_thing, 'MotionSensor1')
        self.assertFalse(registry.thing1.actions['occupancy'].value.on_change_from_mqtt == None)
        self.assertTrue(registry.thing2.actions['occupancy'].value.on_change_from_mqtt == None)

    def test_state_single_sensor(self):
        registry = FakeRegistry()
        sensor = MultiMotionSensor(registry, ['MotionSensor1'])
        test_sensor = Sensor_ExposeActiveBit(sensor)

        registry.thing1.on_mqtt_update('topic', json.loads('{"occupancy": true}'))
        self.assertTrue(test_sensor.sensor_active)

        registry.thing1.on_mqtt_update('topic', json.loads('{"occupancy": false}'))
        self.assertFalse(test_sensor.sensor_active)

    def test_state_multi_sensor(self):
        registry = FakeRegistry()
        sensor = MultiMotionSensor(registry, ['MotionSensor1', 'MotionSensor2'])
        test_sensor = Sensor_ExposeActiveBit(sensor)

        registry.thing1.on_mqtt_update('topic', json.loads('{"occupancy": true}'))
        self.assertTrue(test_sensor.sensor_active)

        registry.thing2.on_mqtt_update('topic', json.loads('{"occupancy": true}'))
        self.assertTrue(test_sensor.sensor_active)

        registry.thing1.on_mqtt_update('topic', json.loads('{"occupancy": false}'))
        self.assertTrue(test_sensor.sensor_active)

        registry.thing2.on_mqtt_update('topic', json.loads('{"occupancy": false}'))
        self.assertFalse(test_sensor.sensor_active)
