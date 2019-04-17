#import os
#pid = os.fork()
#if pid > 0:
#    print("Daemon started!")
#    os._exit(0)
#
#print("Daemon running!")

# TODO
# * Stream obj state update ui
# * Smart update (instead of N seconds -> when media is about to end)
# * Local sensors
# * MK proper logger for sys srvc
# * Integrate as service + parseargs


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
                self.btn1.light_off()
                self.btn2.light_off()
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
            for thing in self.world.get_known_things_names():
                kind = self.world.get_by_name_or_id(thing).thing_types()
                if 'media_player' in kind:
                    self.world.get_by_name_or_id(thing).volume_down()
            return True

        if action == 'off-hold':
            # Shut down the world
            for thing in self.world.get_known_things_names():
                kind = self.world.get_by_name_or_id(thing).thing_types()
                if 'lamp' in kind:
                    self.world.get_by_name_or_id(thing).light_off()
                elif 'media_player' in kind:
                    self.world.get_by_name_or_id(thing).stop()
            return True

        if action == 'off-press':
            print("Scene: goto sleep")
            self.world.get_by_name_or_id('DeskLamp').set_brightness(5)
            self.world.get_by_name_or_id('Livingroom Lamp').light_off()
            self.world.get_by_name_or_id('Floorlamp').set_brightness(5)
            self.world.get_by_name_or_id('Kitchen Counter - Right').set_brightness(25)
            self.world.get_by_name_or_id('Kitchen Counter - Left').light_off()
            self.world.get_by_name_or_id('Baticueva TV').stop()
            return True

        if action == 'on-press':
            print("Scene set")
            self.world.get_by_name_or_id('DeskLamp').set_brightness(50)
            self.world.get_by_name_or_id('DeskLamp').set_rgb('FFA000')
            self.world.get_by_name_or_id('Floorlamp').set_brightness(100)
            self.world.get_by_name_or_id('Kitchen Counter - Right').set_brightness(80)
            self.world.get_by_name_or_id('Kitchen Counter - Left').set_brightness(80)
            return True

        print("No handler for action {} message {}".format(action, msg))
        return False
    

class SceneHandler(object):
    def __init__(self, world):
        self.world = world

    def living_room_evening(self):
        self.world.get_by_name_or_id('DeskLamp').set_brightness(60)
        self.world.get_by_name_or_id('DeskLamp').set_rgb('ED7F0C')
        self.world.get_by_name_or_id('Floorlamp').set_brightness(100)
        self.world.get_by_name_or_id('Livingroom Lamp').set_brightness(100)

    def dinner(self):
        self.world.get_by_name_or_id('DeskLamp').set_brightness(30)
        self.world.get_by_name_or_id('Floorlamp').set_brightness(100)
        self.world.get_by_name_or_id('Livingroom Lamp').light_off()
        self.world.get_by_name_or_id('Kitchen Counter - Right').set_brightness(50)
        self.world.get_by_name_or_id('Kitchen Counter - Left').set_brightness(80)
        self.world.get_by_name_or_id('Baticueva TV').stop()

    def sleepy(self):
        self.world.get_by_name_or_id('DeskLamp').set_brightness(20)
        self.world.get_by_name_or_id('Floorlamp').set_brightness(20)
        self.world.get_by_name_or_id('Livingroom Lamp').light_off()
        self.world.get_by_name_or_id('Kitchen Counter - Right').set_brightness(40)
        self.world.get_by_name_or_id('Kitchen Counter - Left').light_off()
        self.world.get_by_name_or_id('Baticueva TV').stop()
        try:
            self.world.get_by_name_or_id('Spotify').stop()
        except:
            pass

    def world_off(self):
        self.world.get_by_name_or_id('DeskLamp').light_off()
        self.world.get_by_name_or_id('Floorlamp').light_off()
        self.world.get_by_name_or_id('Livingroom Lamp').light_off()
        self.world.get_by_name_or_id('Kitchen Counter - Right').light_off()
        self.world.get_by_name_or_id('Kitchen Counter - Left').light_off()
        self.world.get_by_name_or_id('Baticueva TV').stop()
        try:
            self.world.get_by_name_or_id('Spotify').stop()
        except:
            pass


from thing_registry import ThingRegistry
from mqtt_proxy import MqttProxy, MqttLogger

from flask import Flask, send_from_directory
flask_app = Flask(__name__)

thing_registry = ThingRegistry(flask_app)
mqtt_logger = MqttLogger(thing_registry)
mqtt = MqttProxy('192.168.2.100', 1883, 'zigbee2mqtt/', [thing_registry, mqtt_logger])
scenes = SceneHandler(thing_registry)

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


from flask_socketio import SocketIO
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

import json
with open('config.json', 'r') as fp:
    cfg = json.loads(fp.read())

from thing_spotify import ThingSpotify

# TODO
#ThingSpotify.update_token_from_url(cfg, cfg['spotify_last_redir_url'])
#exit(0)

try:
    tok = ThingSpotify.get_cached_token(cfg)
    #thing_registry.register_thing(ThingSpotify(tok))
except ThingSpotify.TokenNeedsRefresh as ex:
    print("Spotify token needs a refresh. Please GOTO {}".format(ex.refresh_url))
    exit(0)


@flask_app.route('/scenes/living_room_evening')
def flask_endpoint_scenes_1():
    scenes.living_room_evening()
    return "OK"
@flask_app.route('/scenes/dinner')
def flask_endpoint_scenes_2():
    scenes.dinner()
    return "OK"
@flask_app.route('/scenes/sleepy')
def flask_endpoint_scenes_3():
    scenes.sleepy()
    return "OK"
@flask_app.route('/scenes/world_off')
def flask_endpoint_scenes_4():
    scenes.world_off()
    return "OK"


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
        actions[thing] = {'status': obj.json_status(),
                          'supported_actions': obj.supported_actions()}

    return json.dumps(actions)


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

flask_socketio.run(flask_app, host='0.0.0.0', port=2000, debug=False)

print("STOPPING")
mqtt.stop()
print("EXIT")

