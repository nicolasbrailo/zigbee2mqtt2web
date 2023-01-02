from .setup import get_a_lamp
from .setup import get_broken_thing
from .setup import get_contact_sensor
from .setup import get_lamp_with_composite_action
from .setup import get_motion_sensor

import json
import unittest
from zigbee2mqtt2web.zigbee2mqtt_thing import parse_from_zigbee2mqtt
from zigbee2mqtt2web_extras.multi_mqtt_thing import MultiMqttThing

class DummyRegistry:
    def __init__(self, things):
        self.things = {}
        for thing in things:
            self.things[thing.name] = thing

    def get_thing(self, name):
        return self.things[name]

class TestMultiMqttThings(unittest.TestCase):
    def test_double_lamp(self):
        lamp_def1 = get_a_lamp()
        lamp_def1['friendly_name'] = 'Lamp1'
        lamp_def2 = get_a_lamp()
        lamp_def2['friendly_name'] = 'Lamp2'
        registry = DummyRegistry([
                        parse_from_zigbee2mqtt(0, lamp_def1),
                        parse_from_zigbee2mqtt(0, lamp_def2),
                ])

        t = MultiMqttThing(registry, 'Lamp', ['Lamp1', 'Lamp2'])

        self.assertTrue(t.group_has_same_metadata)
        self.assertTrue(t.group_has_same_actions)

        self.assertEqual(t.name, 'Lamp')
        self.assertEqual(t.broken, False)
        self.assertEqual(t.manufacturer, 'IKEA of Sweden')
        self.assertEqual(t.model, 'LED1732G11')
        self.assertEqual(
            t.description,
            "TRADFRI LED bulb E27 1000 lumen, dimmable, white spectrum, opal white")
        self.assertEqual(t.thing_type, 'light')

        expected_actions = {
            'state',
            'brightness',
            'color_temp',
            'color_temp_startup',
            'effect',
            'power_on_behavior',
            'linkquality'}
        self.assertEqual(
            expected_actions.intersection(
                t.actions), expected_actions)

        for a in t.actions:
            self.assertEqual(t.actions[a].name, a)

        self.assertTrue(t.actions['state'].can_set)
        self.assertTrue(t.actions['state'].can_get)
        self.assertTrue(t.actions['effect'].can_set)
        self.assertFalse(t.actions['effect'].can_get)
        self.assertFalse(t.actions['linkquality'].can_set)
        self.assertFalse(t.actions['linkquality'].can_get)

        self.assertEqual(t.actions['state'].value.meta['type'], 'binary')
        self.assertEqual(t.actions['state'].value.meta['value_off'], 'OFF')
        self.assertEqual(t.actions['state'].value.meta['value_on'], 'ON')

        self.assertEqual(t.actions['brightness'].value.meta['type'], 'numeric')
        self.assertEqual(t.actions['brightness'].value.meta['value_min'], 0)
        self.assertEqual(t.actions['brightness'].value.meta['value_max'], 254)

        self.assertEqual(t.actions['effect'].value.meta['type'], 'enum')
        self.assertEqual(len(t.actions['effect'].value.meta['values']), 6)

    def test_warns_different_meta(self):
        lamp_def1 = get_a_lamp()
        lamp_def1['friendly_name'] = 'Lamp1'
        lamp_def1['manufacturer'] = 'Not IKEA'
        lamp_def2 = get_a_lamp()
        lamp_def2['friendly_name'] = 'ALampToo'
        registry = DummyRegistry([
                        parse_from_zigbee2mqtt(0, lamp_def1),
                        parse_from_zigbee2mqtt(0, lamp_def2),
                ])

        t = MultiMqttThing(registry, 'Lamp', ['Lamp1', 'ALampToo'])
        self.assertFalse(t.group_has_same_metadata)

    def test_warns_different_actions(self):
        lamp_def1 = get_a_lamp()
        lamp_def1['friendly_name'] = 'Lamp1'
        fake_action = {
            'access': 7,
            'name': 'foo',
            'property': 'foo',
            'type': 'numeric'}
        lamp_def1['definition']['exposes'][0]['features'].append(fake_action)
        lamp_def2 = get_a_lamp()
        lamp_def2['friendly_name'] = 'ALampToo'
        registry = DummyRegistry([
                        parse_from_zigbee2mqtt(0, lamp_def1),
                        parse_from_zigbee2mqtt(0, lamp_def2),
                ])

        t = MultiMqttThing(registry, 'Lamp', ['Lamp1', 'ALampToo'])
        self.assertFalse(t.group_has_same_actions)

    def test_can_bcast(self):
        lamp_def1 = get_a_lamp()
        lamp_def1['friendly_name'] = 'Lamp1'
        lamp_def2 = get_a_lamp()
        lamp_def2['friendly_name'] = 'ALampToo'
        registry = DummyRegistry([
                        parse_from_zigbee2mqtt(0, lamp_def1),
                        parse_from_zigbee2mqtt(0, lamp_def2),
                ])

        t = MultiMqttThing(registry, 'Lamp', ['Lamp1', 'ALampToo'])
        self.assertEqual(t.get_broadcast_names(), ['Lamp1', 'ALampToo'])

    def test_get_shared_state(self):
        lamp_def1 = get_a_lamp()
        lamp_def1['friendly_name'] = 'Lamp1'
        lamp_def2 = get_a_lamp()
        lamp_def2['friendly_name'] = 'ALampToo'
        registry = DummyRegistry([
                        parse_from_zigbee2mqtt(0, lamp_def1),
                        parse_from_zigbee2mqtt(0, lamp_def2),
                ])
        registry.things['Lamp1'].set('brightness', 123)
        registry.things['ALampToo'].set('brightness', 123)

        t = MultiMqttThing(registry, 'Lamp', ['Lamp1', 'ALampToo'])
        self.assertEqual(t.get_json_state()['brightness'], 123)
        self.assertEqual(t.get('brightness'), 123)

    def test_set_shared_state(self):
        lamp_def1 = get_a_lamp()
        lamp_def1['friendly_name'] = 'Lamp1'
        lamp_def2 = get_a_lamp()
        lamp_def2['friendly_name'] = 'ALampToo'
        registry = DummyRegistry([
                        parse_from_zigbee2mqtt(0, lamp_def1),
                        parse_from_zigbee2mqtt(0, lamp_def2),
                ])

        t = MultiMqttThing(registry, 'Lamp', ['Lamp1', 'ALampToo'])
        t.set('brightness', 123)
        self.assertEqual(t.get('brightness'), 123)
        self.assertEqual(registry.things['Lamp1'].get('brightness'), 123)
        self.assertEqual(registry.things['ALampToo'].get('brightness'), 123)

    def test_objects_not_cached(self):
        lamp_def1 = get_a_lamp()
        lamp_def1['friendly_name'] = 'Lamp1'
        lamp_def2 = get_a_lamp()
        lamp_def2['friendly_name'] = 'ALampToo'
        registry = DummyRegistry([
                        parse_from_zigbee2mqtt(0, lamp_def1),
                        parse_from_zigbee2mqtt(0, lamp_def2),
                ])

        t = MultiMqttThing(registry, 'Lamp', ['Lamp1', 'ALampToo'])

        # Replace the object in the registry
        registry.things['Lamp1'] = parse_from_zigbee2mqtt(0, lamp_def1)

        t.set('brightness', 123)
        self.assertEqual(t.get('brightness'), 123)
        self.assertEqual(registry.things['Lamp1'].get('brightness'), 123)
        self.assertEqual(registry.things['ALampToo'].get('brightness'), 123)
