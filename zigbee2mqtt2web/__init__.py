""" Zigbee2Mqtt2Web: facade for all wrappers over thing registry + ZMW """

from .flask_bridge import FlaskBridge
from .mqtt_proxy import Zigbee2MqttProxy, FakeMqttProxy
from .thing_registry import ThingRegistry
from .zigbee2mqtt_bridge import Zigbee2MqttBridge
from .zigbee2mqtt_thing import Zigbee2MqttAction
from .zigbee2mqtt_thing import Zigbee2MqttActionValue

import logging
logger = logging.getLogger(__name__)

logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)


class Zigbee2Mqtt2Web:
    """ Global wrapper for Z2M2W """

    def __init__(self, cfg):
        self._monkeypatch_rules = []

        if "mqtt_skip_connect_for_dev" in cfg and \
                cfg["mqtt_skip_connect_for_dev"]:
            self._mqtt = FakeMqttProxy(cfg)
        else:
            self._mqtt = Zigbee2MqttProxy(cfg)

        self._mqtt_topic_zmw = cfg['mqtt_topic_zmw'] if 'mqtt_topic_zmw' in cfg else None
        self._mqtt_registry = Zigbee2MqttBridge(cfg, self._mqtt)
        self._mqtt_registry.on_mqtt_network_discovered(self._monkey_patch)
        self.registry = ThingRegistry(self._mqtt_registry)
        self.webserver = FlaskBridge(cfg, self.registry)

    def start_and_block(self):
        """ Starts all relevant services and blocks() on a net-listen loop until stop()ed """
        self._mqtt_registry.start()
        self.webserver.start()

    def stop(self):
        """ Stops blocking """
        self._mqtt_registry.stop()

    def add_thing_monkeypatch_rule(self, name, matcher, callback):
        """ Add a rule to be called when a network discovery message is published """
        self._monkeypatch_rules.append((name, matcher, callback))

    def announce_system_event(self, json_like_map_evt):
        if self._mqtt_topic_zmw is None:
            logger.critical('Requested system announcement, but feature is disabled.'
                            'Announcement: %s', json_like_map_evt)
        else:
            logger.debug('Broadcasting system event: %s', json_like_map_evt)
            self._mqtt.broadcast(self._mqtt_topic_zmw, json_like_map_evt)

    def _monkey_patch(self):
        for name in self.registry.get_thing_names():
            thing = self.registry.get_thing(name)
            for patch_name, matches, patch in self._monkeypatch_rules:
                if thing.is_zigbee_mqtt and matches(thing):
                    logger.info(
                        'Applying patch to %s: %s',
                        thing.name,
                        patch_name)
                    patch(thing)
                    self.registry.replace(thing)
