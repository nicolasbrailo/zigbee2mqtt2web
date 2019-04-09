import json
from thing_registry import MqttProxy, ThingRegistry

class Thing(object):
    def __init__(self, pretty_name):
        self.pretty_name = pretty_name
        self.link_quality = None

    def describe_capabilities(self):
        return {'thing_types': self.thing_types(),
                'supported_actions': self.supported_actions()}

    def thing_types(self):
        return []

    def supported_actions(self):
        return []

    def json_status(self):
        return {'link_quality': self.link_quality}
        
    def on_message(self, topic, msg):
        try:
            self.link_quality = msg['linkquality']
        except KeyError:
            print('Warning: {} doesn\'t support link_quality'.format(self.pretty_name))


class BatteryPoweredThing(Thing):
    def __init__(self, pretty_name):
        super().__init__(pretty_name)
        self.battery_level = None

    def thing_types(self):
        s = super().thing_types()
        s.extend(['battery_powered'])
        return s

    def json_status(self):
        s = super().json_status()
        s.update({'battery_level': self.battery_level})
        return s
        
    def on_message(self, topic, msg):
        try:
            self.battery_level = msg['battery']
        except KeyError:
            print('Warning: {} doesn\'t support battery'.format(self.pretty_name))


class DimmableLamp(Thing):
    def __init__(self, pretty_name, mqtt):
        super().__init__(pretty_name)
        self.is_on = None
        self.brightness = None # 0-255
        self.mqtt = mqtt

    def thing_types(self):
        s = super().thing_types()
        s.extend(['lamp'])
        return s

    def supported_actions(self):
        s = super().supported_actions()
        s.extend(['turn_on', 'turn_off', 'toggle', 'set_brightness', 'brightness_up', 'brightness_down'])
        return s

    def json_status(self):
        s = super().json_status()
        s.update({'is_on': self.is_on, 'brightness': self.brightness})
        if self.brightness is not None:
            s['brightness'] = self.brightness / 255
        return s

    def on_message(self, topic, msg):
        super().on_message(topic, msg)
        if topic.lower().endswith('/config'):
            # Received thing config when 1st connecting. No use for it so far:
            # since everything is setup by hand the capabilities of each device
            # are already known
            self.config = msg
        else:
            self.is_on = (msg['state'] == 'ON')
            self.brightness = int(msg['brightness'])
            print(topic)
            print(msg)
            print("XXXXXXXXXXXXXXXXX")
            print("XXXXXXXXXXXXXXXXX")

    def turn_on(self):
        self.is_on = True
        self.broadcast_new_state()

    def turn_off(self):
        self.is_on = False
        self.broadcast_new_state()

    def toggle(self):
        if self.is_on == True:
            self.turn_off()
        else:
            # If is_on was None (unknown) assume it was off
            self.turn_on()

    def set_brightness(self, pct):
        if pct < 0 or pct > 100:
            raise Exception('Unexpected brightness %: {} (should be 0-100)'.format(pct))

        self.brightness = 255.0*pct/100
        self.is_on = (self.brightness > 0)
        self.broadcast_new_state()

    def brightness_up(self):
        self._chg_brightness(+1)

    def brightness_down(self):
        self._chg_brightness(-1)

    def _chg_brightness(self, direction):
        if self.brightness is None:
            self.brightness = 0
        self.brightness += int(direction * 255 / 5)
        if self.brightness >= 255:
            self.brightness = 255
        if self.brightness <= 0:
            self.brightness = 0
        self.is_on = (self.brightness > 0)

        self.broadcast_new_state()

    def broadcast_new_state(self):
        state = 'ON' if self.is_on else 'OFF'
        msg = '"state":"{}"'.format(state)
        if self.brightness is not None:
            msg += ',"brightness":{}'.format(self.brightness)
        self.mqtt.send_message_to_thing(self.pretty_name, '{{{}}}'.format(msg))

class Buttons(BatteryPoweredThing):
    def __init__(self, pretty_name, btn1, btn2):
        super().__init__(pretty_name)
        self.btn1 = btn1
        self.btn2 = btn2

    def thing_types(self):
        s = super().thing_types()
        s.extend(['button'])
        return s

    def on_message(self, topic, msg):
        super().on_message(topic, msg)
        if msg['action'] == 'arrow_right_click':
            self.btn1.brightness_up()
        if msg['action'] == 'arrow_left_click':
            self.btn1.brightness_down()
        if msg['action'] == 'brightness_up_click':
            self.btn2.brightness_up()
        if msg['action'] == 'brightness_down_click':
            self.btn2.brightness_down()
        if msg['action'] == 'toggle':
            if self.btn1.is_on or self.btn2.is_on:
                self.btn1.turn_off()
                self.btn2.turn_off()
            else:
                self.btn2.set_brightness(20)


mqtt = MqttProxy('192.168.2.100', 1883, 'zigbee2mqtt/')
thing_registry = ThingRegistry(mqtt)
ll = DimmableLamp('Kitchen - Left', thing_registry)
lr = DimmableLamp('Kitchen - Right', thing_registry)

thing_registry.register_thing('0xd0cf5efffe30c9bd', DimmableLamp('DeskLamp', thing_registry))
thing_registry.register_thing('0x000d6ffffef34561', ll)
thing_registry.register_thing('0x0017880104b8c734', lr)
thing_registry.register_thing('0xd0cf5efffe7b6279', DimmableLamp('FloorLamp', thing_registry))
thing_registry.register_thing('0x0017880104efbfdd', Buttons('HueButton', None, None))
thing_registry.register_thing('0xd0cf5efffeffac46', Buttons('IkeaButton', ll, lr))

mqtt.bg_run()


from flask import Flask, send_from_directory
flask_app = Flask(__name__)


@flask_app.route('/webapp/<path:path>')
def flask_endpoint_webapp_root(path):
    print(path)
    return send_from_directory('webapp', path)



@flask_app.route('/things/all_known_things')
def flask_endpoint_known_things():
    return json.dumps(thing_registry.get_known_things_names())

@flask_app.route('/things/unknown_things')
def flask_endpoint_things_unknown_ids():
    return json.dumps(thing_registry.get_unknown_ids())

@flask_app.route('/things/get_world_status')
def flask_endpoint_get_world_status():
    actions = {}
    for thing in thing_registry.get_known_things_names():
        obj = thing_registry.get_by_name_or_id(thing)
        actions[thing] = {'status': obj.json_status()}
        actions[thing].update(obj.describe_capabilities())

    return json.dumps(actions)




@flask_app.route('/things/<name_or_id>/status')
def flask_endpoint_things_status(name_or_id):
    return json.dumps(thing_registry.get_by_name_or_id(name_or_id).json_status())

@flask_app.route('/things/<name_or_id>/toggle')
def flask_endpoint_things_toggle(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.toggle()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/brightness_down')
def flask_endpoint_things_brightness_down(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.brightness_down()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/brightness_up')
def flask_endpoint_things_brightness_up(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.brightness_up()
    return json.dumps(obj.json_status())

flask_app.run(host='0.0.0.0', port=2000, debug=True)

print("STOPPING")
mqtt.stop()
print("CHAU")


exit(0)


