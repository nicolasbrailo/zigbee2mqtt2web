""" All non-Zigbee specific MQTT logic """

import threading
import json
from json import JSONDecodeError

from paho.mqtt import publish
import paho.mqtt.client as mqtt

import logging
logger = logging.getLogger(__name__)


class FakeMqttProxy:
    """ Mqtt mock, for dev server """

    def __init__(self, _cfg):
        logger.warning('Skipping MQTT for dev server. Stuff may break')

    def start(self):
        """ See real MqttProxy """

    def on_message(self, topic, payload):
        """ See real MqttProxy """
        logger.warning('FakeMqttProxy::on_message(%s, %s)', topic, payload)

    def on_non_json_msg(self, topic, payload):
        """ See real MqttProxy """
        logger.warning(
            'FakeMqttProxy::on_non_json_msg(%s, %s)',
            topic,
            payload)

    def stop(self):
        """ See real MqttProxy """

    def broadcast(self, topic, msg):
        """ See real MqttProxy """
        logger.warning('FakeMqttProxy::broadcast(%s, %s)', topic, msg)


class MqttProxy:
    """ Thin wrapper for an MQTT client: manages connections, and translates messages to json """

    def __init__(self, cfg):
        if "mqtt_skip_connect_for_dev" in cfg and \
                cfg["mqtt_skip_connect_for_dev"]:
            logger.warning('Skipping MQTT for dev server. Stuff may break')
            return

        self._mqtt_ip = cfg['mqtt_ip']
        self._mqtt_port = cfg['mqtt_port']

        self.bg_thread = None
        self.client = mqtt.Client()
        # self.client.enable_logger(logger=logger)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_unsubscribe = self._on_unsubscribe
        self.client.on_message = self._on_message

    def _on_connect(self, client, _userdata, _flags, ret_code):
        if ret_code == 0:
            logger.info(
                'Connected to MQTT broker [%s]:%d',
                self._mqtt_ip,
                self._mqtt_port)
        else:
            logger.warning(
                'Connected to MQTT broker [%s]:%d with error code %d.',
                self._mqtt_ip,
                self._mqtt_port,
                ret_code)

        client.subscribe("#", qos=1)
        logger.info('Running MQTT listener thread')

    def _on_unsubscribe(self, client, _userdata, _msg_id):
        logger.info('MQTT client [%s]:%d unsubscribed, will disconnect',
                    self._mqtt_ip,
                    self._mqtt_port)
        client.disconnect()

    def _on_disconnect(self, _client, _userdata, _ret_code):
        logger.info(
            'Disconnected from MQTT broker [%s]:%d',
            self._mqtt_ip,
            self._mqtt_port)

    def _on_message(self, _client, _userdata, msg):
        is_json = True
        try:
            parsed_msg = json.loads(msg.payload)
        except (TypeError, JSONDecodeError):
            is_json = False

        try:
            if is_json:
                self.on_message(msg.topic, parsed_msg)
            else:
                self.on_non_json_msg(msg.topic, msg.payload)
        except Exception as ex:  # pylint: disable=broad-except
            logger.critical(
                'Error on MQTT message handling. Topic %s, payload %s. '
                'Ex: {%s}', msg.topic, msg.payload, ex, exc_info=True)

    def start(self):
        """ Connects to MQTT and launches a bg thread for the net loop """
        logger.info(
            'Connecting to MQTT broker [%s]:%d...',
            self._mqtt_ip,
            self._mqtt_port)
        self.client.connect(self._mqtt_ip, self._mqtt_port, 10)
        self.bg_thread = threading.Thread(target=self.client.loop_forever)
        self.bg_thread.start()

    def on_message(self, topic, payload):
        """ Called when an MQTT JSON message arrives. Override this method for custom behaviour """
        logger.debug(
            'Received MQTT message. Topic %s payload %s - [%s]:%d',
            topic,
            payload, self._mqtt_ip, self._mqtt_port)

    def on_non_json_msg(self, topic, payload):
        """ Called when an MQTT message can't be parsed as JSON (an error, for this app) """
        logger.error(
            'Received non-parseable MQTT message. Topic %s payload %s - [%s]:%d',
            topic,
            payload,
            self._mqtt_ip,
            self._mqtt_port)

    def stop(self):
        """ Starts disconnect process """
        logger.info('Requesting MQTT client disconnect...')
        self.client.unsubscribe('#')
        self.bg_thread.join()

    def broadcast(self, topic, msg):
        """ JSONises and broadcasts a message to MQTT """
        msg = json.dumps(msg)
        publish.single(
            qos=1,
            hostname=self._mqtt_ip,
            port=self._mqtt_port,
            topic=topic,
            payload=msg)
