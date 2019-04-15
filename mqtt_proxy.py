import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import threading

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


class MqttProxy(object):
    """
    Bridge between thing's messages and mqtt
    """

    TOPIC_DELIM = '/'

    def __init__(self, mqtt_ip, mqtt_port, mqtt_topic_prefix, message_handler_list):
        def on_connect(client, userdata, flags, rc):
            print("Connected to MQTT broker with result code "+str(rc))
            client.subscribe("#")

        def on_unsubscribe(client, userdata, msg_id):
            client.disconnect()

        self.mqtt_ip = mqtt_ip
        self.mqtt_port = mqtt_port
        self.mqtt_topic_prefix = mqtt_topic_prefix
        self.message_handler_list = message_handler_list
        self.ignore_topics = ['zigbee2mqtt/bridge/state', 'zigbee2mqtt/bridge/config']

        self.client = mqtt.Client()
        self.client.on_connect = on_connect
        self.client.on_unsubscribe = on_unsubscribe
        self.client.on_message = self._on_mqtt_message
        self.client.connect(mqtt_ip, mqtt_port, 10)

    def bg_run(self):
        self.bg_thread = threading.Thread(target=self.run)
        self.bg_thread.start()

    def run(self):
        self.client.loop_forever()

    def stop(self):
        self.client.unsubscribe('#')
        self.bg_thread.join()

    def _on_mqtt_message(self, _, _2, msg):
        if msg.topic in self.ignore_topics:
            return

        # Try to guess a thing ID from the topic
        if msg.topic.startswith(self.mqtt_topic_prefix):
            thing_id_delim = msg.topic.find(self.TOPIC_DELIM, len(self.mqtt_topic_prefix))
            if thing_id_delim == -1:
                thing_id_delim = None
            thing_id = msg.topic[len(self.mqtt_topic_prefix):thing_id_delim]

        if thing_id is None or len(thing_id) == 0:
            for handler in self.message_handler_list:
                try:
                    handler.on_unknown_message(msg.topic, msg.payload)
                except Exception as ex:
                    print('UnknownMsgHandler {} error while handling: {}'.format(str(handler), str(ex)))
            return

        parsed_msg = None
        try:
            parsed_msg = json.loads(msg.payload.decode('utf-8'))
        except Exception as ex:
            print('Error decoding mqtt message from json in channel {}: {}'.\
                    format(msg.topic, msg.payload))
            return

        # TODO: Repeated msgs -> Close subscription before disconnect?
        #print(msg.timestamp)
        #print(msg.timestamp, "Call thing msg", msg.payload)
        for handler in self.message_handler_list:
            try:
                handler.on_thing_message(thing_id, msg.topic, parsed_msg)
            except Exception as ex:
                print('Handler {} found error while handling MQTT message: {}'.format(str(handler), str(ex)))

    def broadcast(self, topic, msg):
        topic = self.mqtt_topic_prefix + topic
        publish.single(hostname=self.mqtt_ip, port=self.mqtt_port, topic=topic, payload=msg)



