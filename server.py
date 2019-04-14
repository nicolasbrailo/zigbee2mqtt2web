import json
from thing_registry import ThingRegistry
from mqtt_proxy import MqttProxy
from things import Thing, Lamp, DimmableLamp, Button
from thing_chromecast import ThingChromecast

thing_registry = ThingRegistry()

for cc in ThingChromecast.scan_network('192.168.2.101'):
    thing_registry.register_thing(cc)

class MyIkeaButton(Button):
    def __init__(self, mqtt_id, pretty_name, btn1, btn2):
        super().__init__(mqtt_id, pretty_name)
        self.btn1 = btn1
        self.btn2 = btn2

    def handle_action(self, action, msg):
        if action == 'arrow_right_click':
            self.btn1.brightness_up()
        if action == 'arrow_left_click':
            self.btn1.brightness_down()
        if action == 'brightness_up_click':
            self.btn2.brightness_up()
        if action == 'brightness_down_click':
            self.btn2.brightness_down()
        if action == 'toggle':
            if self.btn1.is_on or self.btn2.is_on:
                self.btn1.turn_off()
                self.btn2.turn_off()
            else:
                self.btn2.set_brightness(20)

class MqttLogger(object):
    def __init__(self, registry):
        self.listener = None
        self.registry = registry

    def register_listener(self, l):
        self.listener = l

    def on_thing_message(self, thing_id, topic, parsed_msg):
        if self.listener is not None:
            thing = self.registry.get_by_name_or_id(thing_id)
            self.listener.on_thing_message(thing.get_pretty_name(), topic, parsed_msg)

    def on_unknown_message(self, topic, payload):
        if self.listener is not None:
            self.listener.on_unknown_message(topic, payload)

mqtt_logger = MqttLogger(thing_registry)
mqtt = MqttProxy('192.168.2.100', 1883, 'zigbee2mqtt/', [thing_registry, mqtt_logger])

thing_registry.register_thing(DimmableLamp('0xd0cf5efffe30c9bd', 'DeskLamp', mqtt))
thing_registry.register_thing(DimmableLamp('0x000d6ffffef34561', 'Kitchen - Left', mqtt))
thing_registry.register_thing(DimmableLamp('0x0017880104b8c734', 'Kitchen - Right', mqtt))
thing_registry.register_thing(DimmableLamp('0xd0cf5efffe7b6279', 'FloorLamp', mqtt))
thing_registry.register_thing(Button(      '0x0017880104efbfdd', 'HueButton'))
thing_registry.register_thing(MyIkeaButton('0xd0cf5efffeffac46', 'IkeaButton',
                                           thing_registry.get_by_name_or_id('Kitchen - Left'),
                                           thing_registry.get_by_name_or_id('Kitchen - Right')))

mqtt.bg_run()


from flask import Flask, send_from_directory
from flask_socketio import SocketIO
# TODO? app.config['SECRET_KEY'] = 'secret!'
flask_app = Flask(__name__)
flask_socketio = SocketIO(flask_app)

class MqttToWebSocket(object):
    def on_thing_message(self, thing_id, topic, parsed_msg):
        flask_socketio.emit('mqtt-thing-message', 
                {'thing': thing_id, 'topic': topic, 'msg': parsed_msg})

    def on_unknown_message(self, topic, payload):
        flask_socketio.emit('non-understood-mqtt-message',
                {'topic': topic, 'msg': payload})

mqtt_logger.register_listener(MqttToWebSocket())



@flask_app.route('/webapp/<path:path>')
def flask_endpoint_webapp_root(path):
    return send_from_directory('webapp', path)


# Registry status actions

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


# Thing actions

@flask_app.route('/things/<name_or_id>/turn_on')
def flask_endpoint_things_turn_on(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.turn_on()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/turn_off')
def flask_endpoint_things_turn_off(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.turn_off()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/set_brightness/<brightness>')
def flask_endpoint_things_set_brightness(name_or_id, brightness):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.set_brightness(int(brightness))
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/status')
def flask_endpoint_things_status(name_or_id):
    return json.dumps(thing_registry.get_by_name_or_id(name_or_id).json_status())



## TODO: Move flask bindings to own object

@flask_app.route('/things/<name_or_id>/play')
def flask_endpoint_things_play(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.play()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/pause')
def flask_endpoint_things_pause(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.pause()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/stop')
def flask_endpoint_things_stop(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.stop()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/mute')
def flask_endpoint_things_mute(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.mute()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/unmute')
def flask_endpoint_things_unmute(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.unmute()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/volume_up')
def flask_endpoint_things_volume_up(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.volume_up()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/volume_down')
def flask_endpoint_things_volume_down(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.volume_down()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/set_volume/<vol>')
def flask_endpoint_things_set_volume(name_or_id, vol):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.set_volume(vol)
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/youtube/<video_id>')
def flask_endpoint_things_youtube(name_or_id, video_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.youtube(video_id)
    return json.dumps(obj.json_status())
 


#from flask_socketio import emit as websock_emit
@flask_app.route('/foo')
def flask_foo():
    flask_socketio.emit('my-event', {"Foo": "Bar"})
    return "OK"
 


# @flask_app.route('/things/<name_or_id>/toggle')
# def flask_endpoint_things_toggle(name_or_id):
#     obj = thing_registry.get_by_name_or_id(name_or_id)
#     obj.toggle()
#     return json.dumps(obj.json_status())
# 
# @flask_app.route('/things/<name_or_id>/brightness_down')
# def flask_endpoint_things_brightness_down(name_or_id):
#     obj = thing_registry.get_by_name_or_id(name_or_id)
#     obj.brightness_down()
#     return json.dumps(obj.json_status())
# 
# @flask_app.route('/things/<name_or_id>/brightness_up')
# def flask_endpoint_things_brightness_up(name_or_id):
#     obj = thing_registry.get_by_name_or_id(name_or_id)
#     obj.brightness_up()
#     return json.dumps(obj.json_status())

flask_socketio.run(flask_app, host='0.0.0.0', port=2000, debug=True)

print("STOPPING")
mqtt.stop()
print("EXIT")

