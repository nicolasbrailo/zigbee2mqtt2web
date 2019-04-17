#import os
#pid = os.fork()
#if pid > 0:
#    print("Daemon started!")
#    os._exit(0)
#
#print("Daemon running!")

# TODO
# * Local sensors
# * MK proper logger for sys srvc
# * Integrate as service + parseargs

import json
from zigbee2mqtt2flask.things import Thing, Lamp, DimmableLamp, ColorDimmableLamp, Button

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
    def __init__(self, mqtt_id, pretty_name):
        super().__init__(mqtt_id, pretty_name)

    def handle_action(self, action, msg):
        if action == 'up-press':
            print("UP")
            return True

        if action == 'down-press':
            print("DOWN")
            return True

        if action == 'off-hold':
            print("OFF")
            return True

        if action == 'off-press':
            print("OFF2")
            return True

        if action == 'on-press':
            print("ON")
            return True

        print("No handler for action {} message {}".format(action, msg))
        return False
    

class SceneHandler(object):
    def __init__(self, world):
        self.world = world

    def living_room_evening(self):
        self.world.get_thing_by_name('DeskLamp').set_brightness(60)
        self.world.get_thing_by_name('DeskLamp').set_rgb('ED7F0C')
        self.world.get_thing_by_name('Floorlamp').set_brightness(100)
        self.world.get_thing_by_name('Livingroom Lamp').set_brightness(100)

    def dinner(self):
        self.world.get_thing_by_name('DeskLamp').set_brightness(30)
        self.world.get_thing_by_name('Floorlamp').set_brightness(100)
        self.world.get_thing_by_name('Livingroom Lamp').light_off()
        self.world.get_thing_by_name('Kitchen Counter - Right').set_brightness(50)
        self.world.get_thing_by_name('Kitchen Counter - Left').set_brightness(80)
        self.world.get_thing_by_name('Baticueva TV').stop()

    def sleepy(self):
        self.world.get_thing_by_name('DeskLamp').set_brightness(20)
        self.world.get_thing_by_name('Floorlamp').set_brightness(20)
        self.world.get_thing_by_name('Livingroom Lamp').light_off()
        self.world.get_thing_by_name('Kitchen Counter - Right').set_brightness(40)
        self.world.get_thing_by_name('Kitchen Counter - Left').light_off()
        self.world.get_thing_by_name('Baticueva TV').stop()
        try:
            self.world.get_thing_by_name('Spotify').stop()
        except:
            pass

    def world_off(self):
        self.world.get_thing_by_name('DeskLamp').light_off()
        self.world.get_thing_by_name('Floorlamp').light_off()
        self.world.get_thing_by_name('Livingroom Lamp').light_off()
        self.world.get_thing_by_name('Kitchen Counter - Right').light_off()
        self.world.get_thing_by_name('Kitchen Counter - Left').light_off()
        self.world.get_thing_by_name('Baticueva TV').stop()
        try:
            self.world.get_thing_by_name('Spotify').stop()
        except:
            pass

    def test(self):
        self.world.get_thing_by_name('DeskLamp').set_rgb('F00000')



from zigbee2mqtt2flask import Zigbee2Mqtt2Flask
from flask import Flask, send_from_directory
flask_app = Flask(__name__)


world = Zigbee2Mqtt2Flask(flask_app, '192.168.2.100', 1883, 'zigbee2mqtt/')

scenes = SceneHandler(world)

world.register_thing(ColorDimmableLamp('DeskLamp', 'DeskLamp', world.mqtt))
world.register_thing(DimmableLamp('Kitchen Counter - Left', 'Kitchen Counter - Left', world.mqtt))
world.register_thing(DimmableLamp('Kitchen Counter - Right', 'Kitchen Counter - Right', world.mqtt))
world.register_thing(DimmableLamp('Floorlamp', 'Floorlamp', world.mqtt))
world.register_thing(DimmableLamp('Livingroom Lamp', 'Livingroom Lamp', world.mqtt))
world.register_thing(HueButton(   'HueButton', 'HueButton'))
world.register_thing(MyIkeaButton('IkeaButton', 'IkeaButton',
                                           world.get_thing_by_name('Kitchen Counter - Left'),
                                           world.get_thing_by_name('Kitchen Counter - Right')))

world.start_mqtt_connection()


from flask_socketio import SocketIO
flask_socketio = SocketIO(flask_app)

class MqttToWebSocket(object):
    def on_thing_message(self, thing_id, topic, parsed_msg):
        flask_socketio.emit('mqtt-thing-message', 
                {'thing': thing_id, 'topic': topic, 'msg': parsed_msg})

    def on_unknown_message(self, topic, payload):
        flask_socketio.emit('non-understood-mqtt-message',
                {'topic': topic, 'msg': str(payload.decode('utf-8'))})

world.set_mqtt_listener(MqttToWebSocket())


from thing_chromecast import ThingChromecast
for cc in ThingChromecast.scan_network('192.168.2.101'):
    world.register_thing(cc)

import json
with open('config.json', 'r') as fp:
    cfg = json.loads(fp.read())

from thing_spotify import ThingSpotify
world.register_thing(ThingSpotify(cfg))

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
@flask_app.route('/scenes/test')
def flask_endpoint_scenes_5():
    scenes.test()
    return "OK"


@flask_app.route('/webapp/<path:path>')
def flask_endpoint_webapp_root(path):
    return send_from_directory('webapp', path)

@flask_app.route('/world/scan_chromecasts')
def flask_endpoint_world_scan_chromecasts():
    scan_result = {}
    for cc in ThingChromecast.scan_network():
        try:
            world.register_thing(cc)
            scan_result[cc.get_pretty_name()] = 'Found new device'
        except KeyError:
            scan_result[cc.get_pretty_name()] = 'Already registered'
    return json.dumps(scan_result)

flask_socketio.run(flask_app, host='0.0.0.0', port=2000, debug=False)

print("STOPPING")
world.stop_mqtt_connection()
print("EXIT")

