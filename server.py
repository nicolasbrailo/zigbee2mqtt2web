#import os
#pid = os.fork()
#if pid > 0:
#    print("Daemon started!")
#    os._exit(0)
#
#print("Daemon running!")

# TODO
# * Stream obj state update ui
# * Spotify
# * MV flask bindings
# * Local sensors
# * Small viewer CC
# * Deploy
# * RM thing.thing_type -> replace only with supported_actions


import json
from things import Thing, Lamp, DimmableLamp, ColorDimmableLamp, Button

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

class HueButton(Button):
    def __init__(self, mqtt_id, pretty_name, world):
        super().__init__(mqtt_id, pretty_name)
        self.world = world

    def handle_action(self, action, msg):
        if action == 'up-press':
            for thing in self.world.get_known_things_names():
                kind = self.world.get_by_name_or_id(thing).thing_types()
                if 'media_player' in kind:
                    self.world.get_by_name_or_id(thing).volume_up()
            return True

        if action == 'down-press':
            self.world.get_by_name_or_id('DeskLamp').set_brightness(10)
            #for thing in self.world.get_known_things_names():
            #    kind = self.world.get_by_name_or_id(thing).thing_types()
            #    if 'media_player' in kind:
            #        self.world.get_by_name_or_id(thing).volume_down()
            return True

        if action == 'off-hold':
            # Shut down the world
            for thing in self.world.get_known_things_names():
                kind = self.world.get_by_name_or_id(thing).thing_types()
                if 'lamp' in kind:
                    self.world.get_by_name_or_id(thing).turn_off()
                elif 'media_player' in kind:
                    self.world.get_by_name_or_id(thing).stop()
            return True

        if action == 'off-press':
            print("Scene: goto sleep")
            self.world.get_by_name_or_id('DeskLamp').set_brightness(5)
            self.world.get_by_name_or_id('Livingroom Lamp').turn_off()
            self.world.get_by_name_or_id('Floorlamp').set_brightness(5)
            self.world.get_by_name_or_id('Kitchen Counter - Right').set_brightness(25)
            self.world.get_by_name_or_id('Kitchen Counter - Left').turn_off()
            self.world.get_by_name_or_id('Baticueva TV').stop()
            return True

        if action == 'on-press':
            print("Scene set")
            self.world.get_by_name_or_id('DeskLamp').set_brightness(50)
            self.world.get_by_name_or_id('DeskLamp').set_rgb('FFA000')
            self.world.get_by_name_or_id('Floorlamp').set_brightness(100)
            self.world.get_by_name_or_id('Kitchen - Right').set_brightness(80)
            self.world.get_by_name_or_id('Kitchen - Left').set_brightness(80)
            return True

        print("No handler for action {} message {}".format(action, msg))
        return False
    


from thing_registry import ThingRegistry
from mqtt_proxy import MqttProxy, MqttLogger

thing_registry = ThingRegistry()
mqtt_logger = MqttLogger(thing_registry)
mqtt = MqttProxy('192.168.2.100', 1883, 'zigbee2mqtt/', [thing_registry, mqtt_logger])

thing_registry.register_thing(ColorDimmableLamp('DeskLamp', 'DeskLamp', mqtt))
thing_registry.register_thing(DimmableLamp('Kitchen Counter - Left', 'Kitchen Counter - Left', mqtt))
thing_registry.register_thing(DimmableLamp('Kitchen Counter - Right', 'Kitchen Counter - Right', mqtt))
thing_registry.register_thing(DimmableLamp('Floorlamp', 'Floorlamp', mqtt))
thing_registry.register_thing(DimmableLamp('Livingroom Lamp', 'Livingroom Lamp', mqtt))
thing_registry.register_thing(HueButton(   'HueButton', 'HueButton', thing_registry))
thing_registry.register_thing(MyIkeaButton('IkeaButton', 'IkeaButton',
                                           thing_registry.get_by_name_or_id('Kitchen Counter - Left'),
                                           thing_registry.get_by_name_or_id('Kitchen Counter - Right')))

mqtt.bg_run()


from flask import Flask, send_from_directory
from flask_socketio import SocketIO
flask_app = Flask(__name__)
flask_socketio = SocketIO(flask_app)

class MqttToWebSocket(object):
    def on_thing_message(self, thing_id, topic, parsed_msg):
        flask_socketio.emit('mqtt-thing-message', 
                {'thing': thing_id, 'topic': topic, 'msg': parsed_msg})

    def on_unknown_message(self, topic, payload):
        flask_socketio.emit('non-understood-mqtt-message',
                {'topic': topic, 'msg': str(payload.decode('utf-8'))})

mqtt_logger.register_listener(MqttToWebSocket())


from thing_chromecast import ThingChromecast
for cc in ThingChromecast.scan_network('192.168.2.101'):
    thing_registry.register_thing(cc)


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

@flask_app.route('/things/<name_or_id>/set_rgb/<html_rgb_triple>')
def flask_endpoint_things_set_rgb(name_or_id, html_rgb_triple):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.set_rgb(html_rgb_triple)
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/status')
def flask_endpoint_things_status(name_or_id):
    return json.dumps(thing_registry.get_by_name_or_id(name_or_id).json_status())



## TODO: Move flask bindings to own object

@flask_app.route('/world/scan_chromecasts')
def flask_endpoint_world_scan_chromecasts():
    scan_result = {}
    for cc in ThingChromecast.scan_network():
        try:
            thing_registry.register_thing(cc)
            scan_result[cc.get_pretty_name()] = 'Found new device'
        except KeyError:
            scan_result[cc.get_pretty_name()] = 'Already registered'
    return json.dumps(scan_result)

@flask_app.route('/things/<name_or_id>/playpause')
def flask_endpoint_things_playpause(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.playpause()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/stop')
def flask_endpoint_things_stop(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.stop()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/play_prev_in_queue')
def flask_endpoint_things_play_prev_in_queue(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.play_prev_in_queue()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/play_next_in_queue')
def flask_endpoint_things_play_next_in_queue(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.play_next_in_queue()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/toggle_mute')
def flask_endpoint_things_toggle_mute(name_or_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.toggle_mute()
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/set_volume_pct/<vol_pct>')
def flask_endpoint_things_set_volume_pct(name_or_id, vol_pct):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.set_volume_pct(vol_pct)
    return json.dumps(obj.json_status())

@flask_app.route('/things/<name_or_id>/set_playtime/<time>')
def flask_endpoint_things_set_playtime(name_or_id, time):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.set_playtime(time)
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

@flask_app.route('/things/<name_or_id>/youtube/<video_id>')
def flask_endpoint_things_youtube(name_or_id, video_id):
    obj = thing_registry.get_by_name_or_id(name_or_id)
    obj.youtube(video_id)
    return json.dumps(obj.json_status())
 


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

flask_socketio.run(flask_app, host='0.0.0.0', port=2000, debug=False)

print("STOPPING")
mqtt.stop()
print("EXIT")

