from zigbee2mqtt2flask.things import ColorDimmableLamp, Button
from zigbee2mqtt2flask import Zigbee2Mqtt2Flask
from flask import Flask
from flask_socketio import SocketIO

flask_app = Flask(__name__)
flask_socketio = SocketIO(flask_app)
mqtt_ip, mqtt_port, mqtt_topic_prefix = '192.168.2.100', 1883, 'zigbee2mqtt/'
world = Zigbee2Mqtt2Flask(flask_app, 'ZMF', mqtt_ip, mqtt_port, mqtt_topic_prefix)

# Describe things and actions
class MyButton(Button):
    def __init__(self, mqtt_id, pretty_name, world):
        super().__init__(mqtt_id, pretty_name)
        self.world = world

    def handle_action(self, action, msg):
        if action == 'up-press':
            self.world.get_thing_by_name('DeskLamp').toggle()
            return True

world.register_thing(ColorDimmableLamp('MyDeskLamp', 'MyDeskLamp', world.mqtt))
world.register_thing(MyButton('MyButton', 'MyButton', world))


# Add a streaming mqtt log
class MqttToWebSocket(object):
    def on_thing_message(self, thing_id, topic, parsed_msg):
        flask_socketio.emit('mqtt-thing-message', 
                {'thing': thing_id, 'topic': topic, 'msg': parsed_msg})

    def on_unknown_message(self, topic, payload):
        flask_socketio.emit('non-understood-mqtt-message',
                {'topic': topic, 'msg': str(payload.decode('utf-8'))})

world.set_mqtt_listener(MqttToWebSocket())


# Start the world. Check http://127.0.0.1:2000/ZMF/webapp/example_app.html
world.start_mqtt_connection()
flask_socketio.run(flask_app, host='0.0.0.0', port=2000, debug=False)
world.stop_mqtt_connection()


