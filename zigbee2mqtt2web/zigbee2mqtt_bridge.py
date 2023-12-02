""" All Zigbee specific MQTT logic """

from .zigbee2mqtt_thing import parse_from_zigbee2mqtt
import logging
logger = logging.getLogger(__name__)


def _ignore_msg(_topic, _payload):
    pass


def _debug_msg(topic, payload):
    logger.debug('DEBUG MQTT topic %s payload %s', topic, payload)


class Zigbee2MqttBridge:
    """
    Creates a registry of all things known to zigbee2mqtt, and lets users
    propagate back to MQTT-land the state of devices, when they are changed
    locally.
    """

    def __init__(self, cfg, mqtt):
        self._mqtt_topic_prefix = cfg['mqtt_topic_prefix']
        self._aliases = cfg['mqtt_device_aliases']
        self._known_things = {}
        self._rules = []
        self._cb_on_device_discovery = []
        self._devices_discovered = False
        # Devices have unique names, but they may get re-registered, or even
        # change names. Having a unique ID helps debugging.
        self._last_device_id = 0

        # Register default rules before registering mqtt on_message callback,
        # so that the first handled message already has some rules
        self._add_default_rules()

        # Now register callback (but mqtt shouldn't be started yet, so even
        # the reverse order should be safe)
        self._mqtt = mqtt
        self._mqtt.on_message = self._on_message

    def _add_default_rules(self):
        self.cb_for_mqtt_topic('bridge/state', _ignore_msg)
        self.cb_for_mqtt_topic('bridge/extensions', _ignore_msg)
        self.cb_for_mqtt_topic('bridge/logging', _ignore_msg)
        self.cb_for_mqtt_topic('bridge/info', _ignore_msg)

        def ignore_group_messages(_topic, payload):
            for group in payload:
                gid = group['id']
                self.cb_for_mqtt_topic(f'{gid}/', _ignore_msg)
                self.cb_for_mqtt_topic(f'{gid}/availability', _ignore_msg)
        self.cb_for_mqtt_topic('bridge/groups', ignore_group_messages)

        def _on_msg_device_list_published(_topic, payload):
            logger.info('Zigbee2Mqtt bridge published list of devices')
            device_added = False
            for jsonthing in payload:
                thing = parse_from_zigbee2mqtt(
                    self._last_device_id, jsonthing, known_aliases=self._aliases)
                self._last_device_id += 1
                if self.register_or_ignore(thing):
                    device_added = True

            if not device_added:
                logger.info(
                    'Bridge published network definition. No new devices were found.')
                return

            logger.info('Zigbee2Mqtt network, device definition published. '
                        'Discovered %d things. Notifying listeners...',
                        len(self._known_things.keys()))
            self._devices_discovered = True
            for cb_dev_found in self._cb_on_device_discovery:
                cb_dev_found()
            logger.info('Registry is ready')
        self.cb_for_mqtt_topic('bridge/devices', _on_msg_device_list_published)

    def start(self):
        """ Starts MQTT client, launches a background thread """
        self._mqtt.start()

    def stop(self):
        """ Signal MQTT client to disconnect """
        self._mqtt.stop()

    def cb_for_mqtt_topic(self, topic, cb_for_topic):
        """
        Register a callback for an MQTT topic. Multiple callbacks can be active
        for the same topic (eg one to update a thing, another to forward the
        exact same message to a websocket
        """
        self._rules.append(
            (f'{self._mqtt_topic_prefix}/{topic}', cb_for_topic))

    def on_mqtt_network_discovered(self, cb_net_ready):
        """
        Registers a new callback, to be invoked whenever the MQTT network is
        discovered and MQTT devices are registered in this bridge. These will
        happen when the bridge first connects, but may happen later too if the
        MQTT server announces all its devices.
        If the network has already been discovered, the callback will be invoked
        immediately. A callback may be invoked multiple times, if a new
        announcement message is received.
        """
        self._cb_on_device_discovery.append(cb_net_ready)
        # If registering a CB after network was discovered, call immediatelly
        if self._devices_discovered:
            cb_net_ready()

    def register_or_replace(self, thing):
        """ Add or replace a thing to the MQTT registry """
        self._known_things[thing.name] = thing
        self.cb_for_mqtt_topic(thing.name, thing.on_mqtt_update)
        self.cb_for_mqtt_topic(thing.address, thing.on_mqtt_update)
        self.cb_for_mqtt_topic(f'{thing.real_name}/set', thing.on_mqtt_update)
        self.cb_for_mqtt_topic(f'{thing.name}/set', thing.on_mqtt_update)
        self.cb_for_mqtt_topic(f'{thing.address}/set', thing.on_mqtt_update)

    def register_or_ignore(self, thing):
        """ Add or replace a thing to the MQTT registry """
        if thing.name in self._known_things:
            if thing.name != thing.real_name and thing.real_name not in self._known_things:
                logger.warning(
                    "Thing with MQTT name %s is being ignored, because it's aliased by %s. "
                    "Aliasing things to the same name is a bad idea.",
                    thing.real_name,
                    thing.name)
            else:
                logger.info(
                    'Ignoring registration for %s, thing already known',
                    thing.name)
            return False

        self.register(thing)
        logger.info(
            'Registered Zigbee2Mqtt device %s ID %d',
            thing.name,
            thing.thing_id)
        return True

    def replace(self, thing):
        """ Replace a thing in the MQTT registry, throws if thing was not known """
        if thing.name not in self._known_things:
            raise KeyError(f'Mqtt thing {thing.name} is not known')
        self._known_things[thing.name] = thing

    def register(self, thing):
        """ Add a thing to the MQTT registry, throws if thing was already known """
        if thing.name in self._known_things:
            raise KeyError(f'Mqtt thing {thing.name} is already registered')
        self.register_or_replace(thing)

    def broadcast_thing(self, thing_or_name):
        """
        Notify the bridge that a thing has been updated, and it's time to have
        its state propagated to MQTT-land. Function accepts either a thing or a
        name as input (if a thing is received, no checks are done to verify it's
        a valid a known thing
        """
        if isinstance(thing_or_name, str):
            thing = self.get_thing(thing_or_name)
        else:
            thing = thing_or_name
        topic = f'{self._mqtt_topic_prefix}/{thing.real_name}/set'
        status = thing.make_mqtt_status_update()
        if len(status.keys()) != 0:
            self._mqtt.broadcast(topic, status)
            logger.debug(
                'Thing %s%s is bcasting update topic[%s]:"%s"',
                thing.name,
                f'(an alias for {thing.real_name})' if thing.real_name != thing.name else '',
                topic,
                status)
        else:
            logger.debug('Thing %s has no updates to bcast', thing.name)

    def _on_message(self, topic, payload):
        # Filter CBs so we can apply them without worrying about a callback
        # changing the rules
        matching_cbs = []
        for rule, cb_for_topic in self._rules:
            if topic == rule:
                #logger.debug('Applying rule %s for topic %s', rule, topic)
                matching_cbs.append(cb_for_topic)

        for cb_for_topic in matching_cbs:
            cb_for_topic(topic, payload)

        if len(matching_cbs) == 0:
            logger.warning('Unhandled MQTT message on topic %s', topic)

    def get_thing_names(self):
        """ Returns the name of 'normal' things (eg not broken or hidden) """
        return [name for name, thing in self._known_things.items()
                if not thing.broken]

    def get_all_known_thing_names(self):
        """ Returns the name of all things, including broken or hidden """
        return list(self._known_things.keys())

    def get_thing(self, name):
        """ Returns a single thing, or raises a KeyError exception """
        return self._known_things[name]

    def start_networkmap(self):
        """ Triggers a zigbee2mqtt request to start a network map. This is a very
        slow operation that scales linearly with the number of devices registered.
        It can take a few minutes to complete. Note this request is async: a
        caller will need to have a handler registered to receive the incoming
        message whenever zigbee2mqtt finishes handling the request. """
        logger.warning(
            'Sending graphviz map request. This will take a few minutes')
        logger.warning('WARNING: this is slow, don\'t do it often!')
        topic = f'{self._mqtt_topic_prefix}/bridge/request/networkmap'
        msg = {'type': 'graphviz', 'routes': False}
        self._mqtt.broadcast(topic, msg)
