
class MqttToWebSocket(object):
    @staticmethod
    def build_and_register(socketio, world):
        o = MqttToWebSocket(socketio)
        world.set_mqtt_listener(o)
        return o

    def __init__(self, socketio):
        self.socketio = socketio

    def on_thing_message(self, thing_id, topic, parsed_msg):
        self.socketio.emit('mqtt-thing-message', 
                {'thing': thing_id, 'topic': topic, 'msg': parsed_msg})

    def on_unknown_message(self, topic, payload):
        self.socketio.emit('non-understood-mqtt-message',
                {'topic': topic, 'msg': str(payload.decode('utf-8'))})

