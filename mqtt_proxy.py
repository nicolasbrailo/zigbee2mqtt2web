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

    """ Likely end of prefix to try to guess a new thing's ID. Eg of expected topics:
         zigbee2mqtt/0x00123456789
         homeassistant/sensor/0x000b57fffe137990/linkquality/config
     """
    THING_ID_PREFIX = '0x'
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
        # Try to guess a thing ID from the topic
        if msg.topic.find(self.TOPIC_DELIM + self.THING_ID_PREFIX) == -1:
            if msg.topic in self.ignore_topics:
                return
            else:
                for handler in self.message_handler_list:
                    try:
                        handler.on_unknown_message(msg.topic, msg.payload)
                    except Exception as ex:
                        print('UnknownMsgHandler {} error while handling: {}'.format(str(handler), str(ex)))
                return

        id_start = msg.topic.find(self.TOPIC_DELIM + self.THING_ID_PREFIX) \
                        + len(self.TOPIC_DELIM)
        id_end = msg.topic.find(self.TOPIC_DELIM, id_start)
        id_end = None if id_end == -1 else id_end
        thing_id = msg.topic[id_start : id_end]

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



