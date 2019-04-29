import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import threading

import logging
logger = logging.getLogger('zigbee2mqtt2flask.mqtt')

class MqttProxy(object):
    """
    Bridge between thing's messages and mqtt
    """

    TOPIC_DELIM = '/'

    def __init__(self, mqtt_ip, mqtt_port, mqtt_topic_prefix, message_handler_list):
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.info("Connected to MQTT broker {}:{}".format(mqtt_ip, mqtt_port))
            else:
                logger.warning("Connected to MQTT broker {}:{}, error code {}".format(mqtt_ip, mqtt_port, rc))
            client.subscribe("#", qos=1)

        def on_unsubscribe(client, userdata, msg_id):
            client.disconnect()

        self.mqtt_ip = mqtt_ip
        self.mqtt_port = mqtt_port
        self.mqtt_topic_prefix = mqtt_topic_prefix
        self.message_handler_list = []
        self.message_handler_list.extend(message_handler_list)
        self.ignore_topics = ['zigbee2mqtt/bridge/state', 'zigbee2mqtt/bridge/config']

        self.client = mqtt.Client()
        self.client.on_non_json_msg = None
        self.client.on_connect = on_connect
        self.client.on_unsubscribe = on_unsubscribe
        self.client.on_message = self._on_mqtt_message
        self.client.connect(mqtt_ip, mqtt_port, 10)

    def register_listener(self, l):
        self.message_handler_list.append(l)

    def bg_run(self):
        self.bg_thread = threading.Thread(target=self.run)
        self.bg_thread.start()

    def run(self):
        logger.debug("Running MQTT listener thread")
        self.client.loop_forever()

    def stop(self):
        logger.debug("Stopping MQTT listener thread...")
        self.client.unsubscribe('#')
        self.bg_thread.join()
        logger.debug("MQTT listener thread stopped")

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
                    logger.exception("UnknownMsgHandler {} found an error while handling message {}".
                                        format(str(handler), str(msg.payload), exc_info=True))
            return

        parsed_msg = None
        try:
            decoded_msg = msg.payload.decode('utf-8')
        except Exception as ex:
            logger.error("Ignoring mqtt message with decoding error in channel {}: {}:".\
                            format(msg.topic, msg.payload), exc_info=True)
            return

        try:
            parsed_msg = json.loads(decoded_msg)
        except Exception as ex:
            if self.on_non_json_msg is not None:
                return self.on_non_json_msg(msg.topic, decoded_msg)
            else:
                logger.error("Ignoring non-json message in channel {}: {}:".\
                                    format(msg.topic, msg.payload), exc_info=True)
                return

        for handler in self.message_handler_list:
            try:
                handler.on_thing_message(thing_id, msg.topic, parsed_msg)
            except Exception as ex:
                logger.exception("Handler {} found error while handling MQTT message {}".
                                    format(str(handler), str(msg.payload), exc_info=True))

    def broadcast(self, topic, msg):
        topic = self.mqtt_topic_prefix + topic
        publish.single(qos=1, hostname=self.mqtt_ip, port=self.mqtt_port, topic=topic, payload=msg)



