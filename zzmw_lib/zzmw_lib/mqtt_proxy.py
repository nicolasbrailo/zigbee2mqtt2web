from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from json import JSONDecodeError
import json
import random
import threading

from paho.mqtt import publish
import paho.mqtt.client as mqtt

from apscheduler.schedulers.background import BackgroundScheduler

import logging
from .service_runner import build_logger

# Configure third-party library log levels (they use root logger's handlers)
logging.getLogger('paho').setLevel(logging.INFO)
logging.getLogger("tzlocal").setLevel(logging.ERROR)
logging.getLogger("apscheduler.executors.default").setLevel(logging.ERROR)
logging.getLogger("apscheduler.scheduler").setLevel(logging.ERROR)

log = build_logger("MqttProxy", logging.INFO)

class FakeMqttProxy:
    """ Mqtt mock, for dev server """

    def __init__(self, _cfg):
        log.warning('Skipping MQTT for dev server. Stuff may break')

    def start(self):
        """ See real MqttProxy """

    def on_mqtt_json_msg(self, topic, payload):
        """ See real MqttProxy """
        log.warning('FakeMqttProxy::on_mqtt_json_msg(%s, %s)', topic, payload)

    def on_mqtt_non_json_msg(self, topic, payload):
        """ See real MqttProxy """
        log.warning(
            'FakeMqttProxy::on_mqtt_non_json_msg(%s, %s)',
            topic,
            payload)

    def stop(self):
        """ See real MqttProxy """

    def broadcast(self, topic, msg):
        """ See real MqttProxy """
        log.warning('FakeMqttProxy::broadcast(%s, %s)', topic, msg)


class MqttProxy(ABC):
    """ Thin wrapper for an MQTT client listening to MQTT messages: manages connections, and
    translates messages to json """

    def __init__(self, cfg, topic=None):
        super().__init__()

        if "mqtt_skip_connect_for_dev" in cfg and \
                cfg["mqtt_skip_connect_for_dev"]:
            log.warning('Skipping MQTT for dev server. Stuff may break')
            return

        self._mqtt_ip = cfg['mqtt_ip']
        self._mqtt_port = cfg['mqtt_port']
        self._topic = topic
        self._topics_with_cb = {}

        if self._topic is not None and type(self._topic) not in [type(''), type([])]:
            raise RuntimeError(f"Can't subscribe to channel, invalid topic {type(self._topic)}")

        # Global topic to announce services are alive
        self._global_svc_discovery_ping_topic = "svc_ping_bcast"
        self._global_svc_discovery_announce_topic = "svc_announce_bcast"
        self._global_svc_discovery_leaving_topic = "svc_leaving_bcast"

        self.bg_thread = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        # self.client.enable_log(log=log)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_unsubscribe = self._on_unsubscribe
        self.client.on_message = self._on_message

    def _on_connect(self, client, _userdata, _flags, ret_code, _props):
        if ret_code == 0:
            log.info(
                'Connected to MQTT broker [%s]:%d topic %s',
                self._mqtt_ip,
                self._mqtt_port,
                self._topic)
        else:
            log.warning(
                'Connected to MQTT broker [%s]:%d topic %s with error code %d.',
                self._mqtt_ip,
                self._mqtt_port,
                self._topic,
                ret_code)

        if self._topic is None:
            pass
        elif type(self._topic) == type(''):
            client.subscribe(self._global_svc_discovery_ping_topic, qos=1)
            client.subscribe(f'{self._topic}/#', qos=1)
            log.info('Running MQTT topic %s listener thread', f'{self._topic}/#')
        elif type(self._topic) == type([]):
            for topic in self._topic:
                client.subscribe(f'{topic}/#', qos=1)
            log.info('Running MQTT listener thread, topics: %s', self._topic)
        else:
            log.error(f"Can't subscribe to channel, invalid topic {type(self._topic)}")

        self.on_mqtt_connected()
        # Announce we're up and running
        self.on_service_discovery_ping()

    def _on_disconnect(self, _client, _userdata, _disconnect_flags, _ret_code, _props):
        log.info(
            'Disconnected from MQTT broker [%s]:%d topic %s',
            self._mqtt_ip,
            self._mqtt_port,
            str(self._topic))

    def _on_subscribe(self, client, _userdata, _mid, _reason_code, _props):
        log.debug('MQTT client [%s]:%d subscribed',
                    self._mqtt_ip,
                    self._mqtt_port)

    def _on_unsubscribe(self, client, _userdata, _mid, reason_code, _props):
        log.info('MQTT client [%s]:%d %s unsubscribed (reason %s)',
                    self._mqtt_ip,
                    self._mqtt_port,
                    str(self._topic),
                    str(reason_code))

    def _on_message(self, _client, _userdata, msg):
        is_json = True
        try:
            parsed_msg = json.loads(msg.payload)
        except (TypeError, JSONDecodeError):
            is_json = False

        topic = msg.topic
        if topic.startswith(self._global_svc_discovery_ping_topic):
            self.on_service_discovery_ping()
            return

        if type(self._topic) == type(''):
            if not msg.topic.startswith(self._topic + '/'):
                log.error(f"Received message with unexpected topic {topic}, expected only '{self._topic}'")
                return
            topic = topic[len(self._topic + '/'):]

        match topic:
            case "ping":
                return self.on_ping()
            case "pong":
                # Ignore self pongs
                return

        try:
            if not is_json:
                return self.on_mqtt_non_json_msg(topic, msg.payload)

            for (t, cb) in self._topics_with_cb.items():
                if topic.startswith(t):
                    subtopic = topic[len(t) + len('/'):]
                    return cb(subtopic, parsed_msg)

            # Catch-all
            return self.on_mqtt_json_msg(topic, parsed_msg)
        except Exception as ex:  # pylint: disable=broad-except
            log.critical(
                'Error on MQTT message handling. Topic %s, payload %s. '
                'Ex: {%s}', msg.topic, msg.payload, ex, exc_info=True)

    def loop_forever(self):
        """ Connects to MQTT and starts the net loop. Doesn't return until stop is called """
        log.info(
            'Connecting to MQTT broker [%s]:%d topic %s...',
            self._mqtt_ip,
            self._mqtt_port,
            str(self._topic))
        self.client.connect(self._mqtt_ip, self._mqtt_port, 10)
        self.client.loop_forever()

    def loop_forever_bg(self):
        """ Launches a bg thread that calls self.loop_forever """
        self.bg_thread = threading.Thread(target=self.loop_forever)
        self.bg_thread.start()

    def on_ping(self):
        """ Received ping for this service """
        topic = self._topic if type(self._topic) == type('') else "GenericMqttClient"
        self.broadcast(f"{topic}/pong", "")
        log.debug("Pong")

    def on_service_discovery_ping(self):
        """ Global request for service announcements """
        m = self.get_service_meta()
        if m is not None:
            self.broadcast(self._global_svc_discovery_announce_topic, m)

    @abstractmethod
    def on_mqtt_json_msg(self, topic, payload):
        """ Called when an MQTT JSON message arrives. Override this method for custom behaviour """
        pass

    @abstractmethod
    def get_service_meta(self):
        """ Called on the global service discovery channel to let this service describe itself """
        pass

    def on_mqtt_connected(self):
        pass

    def on_mqtt_non_json_msg(self, topic, payload):
        """ Called when an MQTT message can't be parsed as JSON (an error, for this app) """
        log.error(
            'Received non-parseable MQTT message. Topic %s payload %s - [%s]:%d',
            topic,
            payload,
            self._mqtt_ip,
            self._mqtt_port)

    def stop(self):
        """ Starts disconnect process """
        log.info('Requesting MQTT topic %s client disconnect...', str(self._topic))

        # If running in server mode, announce this service is leaving
        if self.get_service_meta() is not None:
            self.broadcast(self._global_svc_discovery_leaving_topic,
                           self.get_service_meta())

        self.client.disconnect()
        if self.bg_thread:
            self.bg_thread.join()

    def subscribe_with_cb(self, topic, cb):
        if topic in self._topics_with_cb:
            raise KeyError(f"Topic {topic} already has a callback")

        if not self._topic:
            self._topic = [topic]
        elif type(self._topic) == type(''):
            self._topic = [self._topic, topic]
        else:
            self._topic.append(topic)
        self._topics_with_cb[topic] = cb
        self.client.subscribe(topic)

    def broadcast(self, topic, msg):
        """ JSONises and broadcasts a message to MQTT """
        msg = json.dumps(msg)
        publish.single(
            qos=1,
            hostname=self._mqtt_ip,
            port=self._mqtt_port,
            topic=topic,
            payload=msg)

class MqttServiceClient(MqttProxy):
    """ An MQTT client that doesn't provide a service, only listens to services """

    def __init__(self, cfg, svc_deps):
        self._known_services = {}
        self._first_start_ran = False
        self._all_deps_alive = False
        self._svc_deps = svc_deps
        super().__init__(cfg, ["svc_announce_bcast", "svc_leaving_bcast"])

        wait_for_deps_first_run = 5
        # Add a random (prime) delay to pings, to minimize chances we're syncing pings with other services
        random_delay = random.choice([2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59])
        self._deps_ping = 3 * 60 + random_delay
        # Number of missed pings before marking a dep as down
        self._dep_stale_timeout = self._deps_ping * 3
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        if wait_for_deps_first_run <= 1:
            raise RuntimeError("Bad timeout")
        self._scheduler.add_job(
                self.check_deps_alive,
                trigger='date',
                run_date=datetime.now() + timedelta(seconds=1))
        self._scheduler.add_job(
                self._check_deps_alive_first_run,
                trigger='date',
                run_date=datetime.now() + timedelta(seconds=wait_for_deps_first_run))

    def _check_deps_alive_first_run(self):
        deps = self.get_missing_deps()
        if len(deps) != 0:
            self.on_startup_fail_missing_deps(deps)

        self._check_deps_job = self._scheduler.add_job(
            func=self.check_deps_alive,
            trigger="interval",
            seconds=self._deps_ping)

    def check_deps_alive(self):
        """
        Check if service dependencies are still responding.

        Marks services as stale if they haven't sent pings within the timeout period.
        Called periodically by the scheduler. Also broadcasts a ping request to
        trigger responses from all services.
        """
        # Mark deps without pings for a long time as stale
        stales = []
        now = datetime.now()
        for name, info in self._known_services.items():
            last_seen = info.get('last_seen')
            if not last_seen or ((now - last_seen) > timedelta(seconds=self._dep_stale_timeout)):
                stales.append(name)
        for name in stales:
            self.on_dep_became_stale(name)
            self._known_services.pop(name, None)

        log.debug("Pinging global service discovery")
        self.broadcast(self._global_svc_discovery_ping_topic, {})

    def on_mqtt_connected(self):
        # Subscribe to service discovery ping topic so we can respond to discovery requests
        self.client.subscribe(self._global_svc_discovery_ping_topic, qos=1)
        # Announce ourselves to any listening service monitors
        self.on_service_discovery_ping()

    def on_mqtt_json_msg(self, topic, payload):
        match topic:
            case "svc_announce_bcast":
                self._on_service_up(payload)
                return
            case "svc_leaving_bcast":
                self._on_service_down(payload)
                return

        # Identify which service generated this message
        for name, info in self._known_services.items():
            if info['mqtt_topic'] is not None and topic.startswith(info['mqtt_topic']):
                subtopic = topic[len(info['mqtt_topic']) + len('/'):]
                self.on_service_message(name, subtopic, payload)
                return

        # Message from unknown service, ignore
        log.debug("Ignoring message from unknown service, topic '%s'", topic)


    def _on_service_up(self, svc_meta):
        self._on_service_updown(True, svc_meta)

    def _on_service_down(self, svc_meta):
        self._on_service_updown(False, svc_meta)

    def _on_service_updown(self, up, svc_meta):
        if svc_meta is None:
            # A service responds to pings, but doesn't actually serve anything
            return
        if 'name' not in svc_meta:
            log.error('Ignoring service up notification with bad format, missing service name. Message: %s', str(svc_meta))
            return
        if svc_meta['name'] not in self._svc_deps:
            # We don't care about this service
            log.debug('Uninteresting service "%s" is %s', svc_meta['name'], "up" if up else "down")
            return
        if up:
            name = svc_meta['name']
            if 'mqtt_topic' not in svc_meta:
                log.debug('Required service "%s" is up, but it doesn\'t have an MQTT topic. Won\'t receive messages from this service.', name)
                return

            if name in self._known_services and self._known_services[name]['mqtt_topic'] == svc_meta['mqtt_topic']:
                self._known_services[name]['last_seen'] = datetime.now()
                log.debug('Ping from service dep %s, mark as not stale', name)
                return

            if name in self._known_services and self._known_services[name]['mqtt_topic'] != svc_meta['mqtt_topic']:
                log.warning("Service %s changed it's mqtt_topic from '%s' to '%s'. Will resubscribe, but weird things may happen",
                            name, self._known_services[name]['mqtt_topic'], svc_meta['mqtt_topic'])
                # Fallthrough: follow the normal subscription logic

            if svc_meta['mqtt_topic'] is None:
                log.debug('Dependency "%s" is now running, but doesn\'t publish to MQTT.', name)
            else:
                topic = f"{svc_meta['mqtt_topic']}/#"
                log.info('Dependency "%s" is now running, subscribing to "%s"', name, topic)
                self.client.subscribe(topic)

            svc_just_came_up = name not in self._known_services
            self._known_services[name] = svc_meta
            self._known_services[name]['last_seen'] = datetime.now()
            if svc_just_came_up:
                self.on_service_came_up(name)
        else:
            log.info('Dependency "%s" is now down', svc_meta['name'])
            self._known_services.pop(svc_meta['name'], None)

        missing_svcs = self.get_missing_deps()
        now_healthy = (len(missing_svcs) == 0)
        healthy_changed = (now_healthy != self._all_deps_alive)
        if not healthy_changed:
            return
        self._all_deps_alive = now_healthy
        if self._all_deps_alive and not self._first_start_ran:
            self._first_start_ran = True
            self.on_all_service_deps_running()
        else:
            self.on_service_deps_missing(missing_svcs)

    def get_known_services(self):
        """ List of known and alive services """
        return self._known_services

    def get_missing_deps(self):
        """
        Get list of required dependencies that are not currently running.
        """
        return [dep for dep in self._svc_deps if not dep in self._known_services]

    def on_dep_became_stale(self, name):
        """
        Called when a service dependency hasn't been seen for too long.

        Override this method to handle stale dependencies. Default implementation
        logs an error.

        Args:
            name: Name of the service that became stale
        """
        log.error("No pings from %s in over %d seconds, marking dep as down", name, self._dep_stale_timeout)

    def message_svc(self, service, subtopic, payload):
        """
        Send a message to a known service via MQTT.

        Args:
            service: Name of the service to message (must be in dependencies)
            subtopic: Subtopic to append to service's base topic (e.g., "command")
            payload: Python object to JSON-encode and send

        Raises:
            RuntimeError: If service is unknown or doesn't have an mqtt_topic

        Example:
            self.message_svc("mqtt_telegram", "send_text", {"msg": "Hello"})
            # Publishes to: mqtt_telegram/send_text
        """
        if service not in self._known_services:
            raise RuntimeError(f"Unknown service {service}")
        topic = self._known_services[service]['mqtt_topic']
        if topic is None:
            raise RuntimeError(f"Service {service} doesn't have an mqtt_topic, it can't be messaged")
        self.broadcast(f"{topic}/{subtopic}", payload)

    def on_startup_fail_missing_deps(self, deps):
        """
        Called during startup if required dependencies are not running.

        Override this method to handle startup failures. Default implementation
        logs an error.

        Args:
            deps: List of missing service names
        """
        log.error("Service missing deps %s", deps)

    def on_all_service_deps_running(self):
        """
        Called when all required service dependencies are running.

        Override this method to perform initialization that requires all
        dependencies. Default implementation logs a debug message.
        """
        log.debug("All monitored deps are alive, service healthy")

    def on_service_deps_missing(self, deps):
        """
        Called when some required dependencies go missing after startup.

        Override this method to handle dependency failures. Default implementation
        logs a warning.

        Args:
            deps: List of missing service names
        """
        log.warning("Some monitored deps are missing, service unhealthy %s", str(deps))

    def on_service_came_up(self, service_name):
        """ Let user take an action on level up, but replies may not work yet. Replies rely on
        subscriptions being setup, and when a service cames up we're only guaranteed to have started
        the subscription process, but the subscription is not guaranteed to have completed """
        log.info("Service dep %s is now running", service_name)

    def on_service_message(self, service_name, msg_topic, msg):
        """
        Called when a message is received from a known service dependency.

        Override this method to handle messages from services. Default implementation
        logs a debug message.

        Args:
            service_name: Name of the service that sent the message
            msg_topic: Subtopic (after the service's base topic)
            msg: Parsed JSON message payload
        """
        log.debug("Received message %s", msg)

