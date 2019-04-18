from zigbee2mqtt2flask.things import ColorDimmableLamp, Button
from zigbee2mqtt2flask import Zigbee2Mqtt2Flask
from zigbee2mqtt2flask.zigbee2mqtt2flask.mqtt_web_socket_streamer import MqttToWebSocket

from flask import Flask
from flask_socketio import SocketIO

flask_app = Flask(__name__)
mqtt_ip, mqtt_port, mqtt_topic_prefix = '192.168.2.100', 1883, 'zigbee2mqtt/'
world = Zigbee2Mqtt2Flask(flask_app, 'ZMF', mqtt_ip, mqtt_port, mqtt_topic_prefix)

# Optional: Add streaming mqtt log endpoints (see http://127.0.0.1:2000/ZMF/webapp/mqtt_log_example.html)
flask_socketio = SocketIO(flask_app)
MqttToWebSocket.build_and_register(flask_socketio, world)

# Describe things and actions
class MyButton(Button):
    def __init__(self, mqtt_id, world):
        super().__init__(mqtt_id)
        self.world = world

    def handle_action(self, action, msg):
        if action == 'up-press':
            self.world.get_thing_by_name('DeskLamp').toggle()
            return True

world.register_thing(ColorDimmableLamp('MyDeskLamp', world.mqtt))
world.register_thing(MyButton('MyButton', world))

# Start the world. Check http://127.0.0.1:2000/ZMF/webapp/example_app.html
world.start_mqtt_connection()
flask_socketio.run(flask_app, host='0.0.0.0', port=2000, debug=False)
world.stop_mqtt_connection()


