""" All non-Zigbee specific MQTT logic """

import datetime
from json import JSONDecodeError
import json
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler

from paho.mqtt import publish
import paho.mqtt.client as mqtt

import logging
logger = logging.getLogger(__name__)

_SCHEDULER = BackgroundScheduler()
_SCHEDULER.start()

# Period to check if Zigbee2Mqtt is alive
_Z2M_PING_INTERVAL = 5 * 60
# If Zigbee2Mqtt has sent any messages in last $PING_TIMEOUT seconds,
# consider it alive
_Z2M_PING_TIMEOUT = 10 * 60
# If Zigbee2Mqtt has sent no messages in last $ALIVE_TIMEOUT seconds,
# consider it dead
_Z2M_ALIVE_TIMEOUT = 15 * 60
# Message to send Z2M as a ping
_Z2M_ALIVE_REQUEST_TOPIC = 'zigbee2mqtt/bridge/request/health_check'
_Z2M_ALIVE_RESPONSE_TOPIC = 'zigbee2mqtt/bridge/response/health_check'


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
    """ Thin wrapper for an MQTT client listening to MQTT messages: manages connections, and
    translates messages to json """

    def __init__(self, cfg, topic=None):
        if "mqtt_skip_connect_for_dev" in cfg and \
                cfg["mqtt_skip_connect_for_dev"]:
            logger.warning('Skipping MQTT for dev server. Stuff may break')
            return

        self._mqtt_ip = cfg['mqtt_ip']
        self._mqtt_port = cfg['mqtt_port']
        self._topic = f'{topic}/#'

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
                'Connected to MQTT broker [%s]:%d topic %s',
                self._mqtt_ip,
                self._mqtt_port,
                self._topic)
        else:
            logger.warning(
                'Connected to MQTT broker [%s]:%d topic %s with error code %d.',
                self._mqtt_ip,
                self._mqtt_port,
                self._topic,
                ret_code)

        if self._topic is not None:
            client.subscribe(self._topic, qos=1)
        logger.info('Running MQTT topic %s listener thread', self._topic)

    def _on_unsubscribe(self, client, _userdata, _msg_id):
        logger.info('MQTT client [%s]:%d %s unsubscribed, will disconnect',
                    self._mqtt_ip,
                    self._mqtt_port,
                    self._topic)
        client.disconnect()

    def _on_disconnect(self, _client, _userdata, _ret_code):
        logger.info(
            'Disconnected from MQTT broker [%s]:%d topic %s',
            self._mqtt_ip,
            self._mqtt_port,
            self._topic)

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
            'Connecting to MQTT broker [%s]:%d topic %s...',
            self._mqtt_ip,
            self._mqtt_port,
            self._topic)
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
        logger.info('Requesting MQTT topic %s client disconnect...', self._topic)
        self.client.unsubscribe(self._topic)
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


class Zigbee2MqttProxy(MqttProxy):
    """ Thin wrapper for an MQTT client listening to Zigbee2MQTT messages """

    def __init__(self, cfg):
        super().__init__(cfg, topic=cfg['mqtt_topic_zigbee2mqtt'])

        # last_seen = now() - ping_timeout, so that we'll ping the server on the
        # first try. Also, last_seen > now() - alive_timeout, so that we don't
        # declare it dead just yet
        self._z2m_last_seen = time.time() - _Z2M_PING_TIMEOUT
        _SCHEDULER.add_job(
            func=self._ping_z2m,
            trigger="interval",
            next_run_time=datetime.datetime.now(),
            seconds=_Z2M_PING_INTERVAL)

    def _on_message(self, _client, _userdata, msg):
        self._z2m_last_seen = time.time()
        if msg.topic == _Z2M_ALIVE_RESPONSE_TOPIC:
            return
        super()._on_message(_client, _userdata, msg)

    def _ping_z2m(self):
        now = time.time()
        last_seen_delta = now - self._z2m_last_seen
        if last_seen_delta < _Z2M_PING_TIMEOUT:
            # We've seen Zigbee2Mqtt in the last period, skip ping
            return

        self.start_zigbee2mqtt_ping()
        if last_seen_delta < _Z2M_ALIVE_TIMEOUT:
            # Ping Z2M and wait a bit more
            return

        # Z2M hasn't sent any messages for a long time, it's probably down
        logger.error(
            'Zigbee2Mqtt is down: no response for %s seconds',
            last_seen_delta)

    def start_zigbee2mqtt_ping(self):
        """ Send a ping to Z2M (the response is async, will be delivered on
        _Z2M_ALIVE_RESPONSE_TOPIC """
        self.broadcast(_Z2M_ALIVE_REQUEST_TOPIC, '')

    def broadcast(self, topic, msg):
        last_seen_delta = time.time() - self._z2m_last_seen
        if last_seen_delta > _Z2M_ALIVE_TIMEOUT:
            logger.critical(
                "Zigbee2Mqtt may be down: Sending message on topic %s, "
                "but Z2M hasn't sent replies for %s seconds", topic, last_seen_delta)
        super().broadcast(topic, msg)
