import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import threading

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

    class DummyHandler(object):
        def on_unknown_message(self, topic, payload):
            pass

        def on_thing_message(self, thing_id, topic, msg):
            pass

    def __init__(self, mqtt_ip, mqtt_port, mqtt_topic_prefix):
        def on_connect(client, userdata, flags, rc):
            print("Connected to MQTT broker with result code "+str(rc))
            client.subscribe("#")

        self.mqtt_ip = mqtt_ip
        self.mqtt_port = mqtt_port
        self.mqtt_topic_prefix = mqtt_topic_prefix
        self.message_handler = MqttProxy.DummyHandler()

        self.client = mqtt.Client()
        self.client.on_connect = on_connect
        self.client.on_message = self._on_mqtt_message
        self.client.connect(mqtt_ip, mqtt_port, 10)

    def register_handler(self, handler):
        self.message_handler = handler

    def bg_run(self):
        self.bg_thread = threading.Thread(target=self.run)
        self.bg_thread.start()

    def run(self):
        self.client.loop_forever()

    def stop(self):
        self.client.disconnect()
        self.bg_thread.join()

    def _on_mqtt_message(self, _, _2, msg):
        # Try to guess a thing ID from the topic
        if msg.topic.find(self.TOPIC_DELIM + self.THING_ID_PREFIX) == -1:
            return self.message_handler.on_unknown_message(msg.topic, msg.payload)

        id_start = msg.topic.find(self.TOPIC_DELIM + self.THING_ID_PREFIX) \
                        + len(self.TOPIC_DELIM)
        id_end = msg.topic.find(self.TOPIC_DELIM, id_start)
        id_end = None if id_end == -1 else id_end
        thing_id = msg.topic[id_start : id_end]

        parsed_msg = None
        try:
            parsed_msg = json.loads(msg.payload.decode('utf-8'))
        except Exception as ex:
            print('Error decoding mqtt message from json')
            return

        try:
            self.message_handler.on_thing_message(thing_id, msg.topic, parsed_msg)
        except Exception as ex:
            print('Found error while handling MQTT message: {}'.format(str(ex)))

    def broadcast(self, topic, msg):
        topic = self.mqtt_topic_prefix + topic
        publish.single(hostname=self.mqtt_ip, port=self.mqtt_port, topic=topic, payload=msg)



class ThingRegistry(object):
    def __init__(self, mqtt_proxy):
        self.known_things = {}
        self.name_to_id = {}
        self.unknown_things = set()
        self.mqtt_proxy = mqtt_proxy
        mqtt_proxy.register_handler(self)

    def on_unknown_message(self, topic, payload):
        print('Received message that can\'t be understood:' +\
                    '\t{}\n\t{}'.format(topic, payload))

    def get_known_things_names(self):
        return list(self.name_to_id.keys())

    def get_unknown_ids(self):
        return list(self.unknown_things)

    def on_thing_message(self, thing_id, topic, json_msg):
        if thing_id in self.known_things.keys():
            self.known_things[thing_id].on_message(topic, json_msg)
        else:
            if thing_id not in self.unknown_things:
                self.unknown_things.add(thing_id)
                print('Thing {} added to registry of unknown things'.format(thing_id))

    def send_message_to_thing(self, pretty_name, msg):
        topic = self.name_to_id[pretty_name] + '/set'
        self.mqtt_proxy.broadcast(topic, msg)


    def register_thing(self, id, obj):
        self.known_things[id] = obj
        if obj.pretty_name in self.name_to_id.keys():
            raise Exception('Thing {} ({}) already registered'.format(obj.pretty_name, id))
        self.name_to_id[obj.pretty_name] = id

    def get_by_name_or_id(self, name_or_id):
        if name_or_id in self.name_to_id.keys():
            id = self.name_to_id[name_or_id]
            return self.known_things[id]

        # If it's not a name it must be an id. Else fail
        return self.known_things[name_or_id]


