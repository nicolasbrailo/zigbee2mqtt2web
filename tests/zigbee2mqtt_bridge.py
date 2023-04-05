from .setup import get_a_lamp
from .setup import get_broken_thing
from .setup import get_contact_sensor
from .setup import get_lamp_with_composite_action
from .setup import get_motion_sensor
from .setup import get_bridge_all_devs_msg
from .setup import get_bridge_some_devs_msg
from .setup import FakeMqtt

import unittest

from zigbee2mqtt2web import Zigbee2MqttBridge


CFG = {'mqtt_topic_prefix': 'topic_prefix', 'mqtt_device_aliases': {}}


class TestZigbee2MqttBridge(unittest.TestCase):
    def test_starts(self):
        mqtt = FakeMqtt()
        bridge = Zigbee2MqttBridge(CFG, mqtt)
        bridge.start()
        self.assertTrue(mqtt.started)
        bridge.stop()
        self.assertFalse(mqtt.started)

    def test_parses_thing_discovery_msg(self):
        mqtt = FakeMqtt()
        bridge = Zigbee2MqttBridge(CFG, mqtt)
        bridge.start()
        mqtt.on_message(
            'topic_prefix/bridge/devices',
            get_bridge_all_devs_msg())
        found = set(bridge.get_all_known_thing_names())
        expected = set(['Oficina', 'foo', 'SensorPuertaEntrada',
                        'Belador', 'MotionSensor1'])
        self.assertEqual(expected.intersection(found), expected)

        t = bridge.get_thing('Oficina')
        self.assertEqual(t.name, 'Oficina')
        self.assertEqual(t.broken, False)
        self.assertEqual(len(t.actions), 7)
        self.assertTrue('brightness' in t.actions)
        self.assertEqual(t.actions['brightness'].value.meta['type'], 'numeric')
        t.set('brightness', 123)
        self.assertEqual(bridge.get_thing('Oficina').get('brightness'), 123)

    def test_devices_with_same_name_are_replaced(self):
        mqtt = FakeMqtt()
        bridge = Zigbee2MqttBridge(CFG, mqtt)
        bridge.start()
        mqtt.on_message(
            'topic_prefix/bridge/devices',
            get_bridge_all_devs_msg())
        found1 = set(bridge.get_thing_names())
        mqtt.on_message(
            'topic_prefix/bridge/devices',
            get_bridge_some_devs_msg())
        found2 = set(bridge.get_thing_names())
        self.assertEqual(found1.intersection(found2), found1)

    def test_broken_devices_are_hidden(self):
        mqtt = FakeMqtt()
        bridge = Zigbee2MqttBridge(CFG, mqtt)
        bridge.start()
        mqtt.on_message(
            'topic_prefix/bridge/devices',
            get_bridge_all_devs_msg())
        known = set(bridge.get_thing_names())
        known_and_broken = set(bridge.get_all_known_thing_names())

        expected = set(['Oficina', 'SensorPuertaEntrada',
                        'Belador', 'MotionSensor1'])
        self.assertEqual(known.intersection(expected), known)
        self.assertEqual(known_and_broken.difference(known), {'foo'})

    def test_callback_on_network_discovered_out_of_order(self):
        called = 0

        def check_call():
            nonlocal called
            called += 1

        mqtt = FakeMqtt()
        bridge = Zigbee2MqttBridge(CFG, mqtt)
        bridge.start()
        mqtt.on_message(
            'topic_prefix/bridge/devices',
            get_bridge_all_devs_msg())
        bridge.on_mqtt_network_discovered(check_call)
        self.assertEqual(called, 1)

    def test_custom_callbacks(self):
        mqtt = FakeMqtt()
        bridge = Zigbee2MqttBridge(CFG, mqtt)
        bridge.start()

        called = False

        def check_call(topic, msg):
            self.assertEqual(topic, 'topic_prefix/foo')
            self.assertEqual(msg, {'foo': 123})
            nonlocal called
            called = True

        bridge.cb_for_mqtt_topic('foo', check_call)
        mqtt.on_message('topic_prefix/foo', {"foo": 123})
        self.assertTrue(called)

    def test_multiple_custom_callbacks(self):
        mqtt = FakeMqtt()
        bridge = Zigbee2MqttBridge(CFG, mqtt)
        bridge.start()

        called1 = False

        def check_call1(topic, msg):
            self.assertEqual(topic, 'topic_prefix/foo')
            self.assertEqual(msg, {'foo': 123})
            nonlocal called1
            called1 = True

        called2 = False

        def check_call2(topic, msg):
            self.assertEqual(topic, 'topic_prefix/foo')
            self.assertEqual(msg, {'foo': 123})
            nonlocal called2
            called2 = True

        bridge.cb_for_mqtt_topic('foo', check_call1)
        bridge.cb_for_mqtt_topic('foo', check_call2)

        mqtt.on_message('topic_prefix/foo', {"foo": 123})
        self.assertTrue(called1)
        self.assertTrue(called2)

    def test_callback_on_network_discovered(self):
        called = 0

        def check_call():
            nonlocal called
            called += 1

        mqtt = FakeMqtt()
        bridge = Zigbee2MqttBridge(CFG, mqtt)
        bridge.on_mqtt_network_discovered(check_call)
        bridge.start()
        mqtt.on_message(
            'topic_prefix/bridge/devices',
            get_bridge_some_devs_msg())
        self.assertEqual(called, 1)

        mqtt.on_message(
            'topic_prefix/bridge/devices',
            get_bridge_some_devs_msg())
        # Same list of devices == no callback
        self.assertEqual(called, 1)

        mqtt.on_message(
            'topic_prefix/bridge/devices',
            get_bridge_all_devs_msg())
        self.assertEqual(called, 2)

    def test_devices_have_alias(self):
        mqtt = FakeMqtt()
        aliases = {"Oficina": "Oficina_aliased", "0x00158d0008ad5e77": "SensorPuertaEntrada_aliased"}
        bridge = Zigbee2MqttBridge({'mqtt_topic_prefix': 'topic_prefix', 'mqtt_device_aliases': aliases}, mqtt)
        bridge.start()
        mqtt.on_message(
            'topic_prefix/bridge/devices',
            get_bridge_all_devs_msg())

        self.assertFalse("Oficina" in bridge.get_thing_names())
        self.assertFalse("SensorPuertaEntrada" in bridge.get_thing_names())
        self.assertTrue("Oficina_aliased" in bridge.get_thing_names())
        self.assertTrue("SensorPuertaEntrada_aliased" in bridge.get_thing_names())

        self.assertEqual(bridge.get_thing('Oficina_aliased').real_name, 'Oficina')
        self.assertEqual(bridge.get_thing('SensorPuertaEntrada_aliased').real_name, 'SensorPuertaEntrada')
