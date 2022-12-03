from .thing_registry import ThingRegistry
from .mqtt_proxy import MqttProxy

from flask import send_from_directory
import os
import time

import logging
logger = logging.getLogger('zigbee2mqtt2flask')

class Zigbee2Mqtt2Flask(object):
    """ Interface between Zigbee/Mqtt and Flask: objects implementing the Thing
    interface can be registered in Zigbee2Mqtt2Flask and their interface will
    be available in endpoints in flask_app. See Zigbee2Mqtt2Flask.things for
    examples. """

    def __init__(self, flask_app, flask_endpoint_prefix,
                 mqtt_ip, mqtt_port, mqtt_topic_prefix,
                 serve_example_webapp=False):
        logger.info("Zigbee2Mqtt2Flask (ZMF) starting up...")
        self.thing_registry = ThingRegistry(flask_app, flask_endpoint_prefix)
        self.mqtt = MqttProxy(mqtt_ip, mqtt_port, mqtt_topic_prefix, [self.thing_registry])

        logger.debug("ZMF serves netmap on /" + flask_endpoint_prefix + '/graphviz_netmap')
        flask_app.add_url_rule('/' + flask_endpoint_prefix + '/graphviz_netmap',
                                     flask_endpoint_prefix + 'graphviz_netmap',
                               self.mk_graphviz_mqtt_network_map)

        if serve_example_webapp:
            try:
                cwd = os.path.dirname(os.path.abspath(__file__))
            except:
                cwd = ''

            # Need to use absolute path in case someone is using this as a module
            filesys_path_to_webdir = cwd + '/webapp'
            logger.debug("ZMF serves webapp from local dir {}".format(filesys_path_to_webdir))
            logger.debug("ZMF serves webapp @ url {}".format('/' + flask_endpoint_prefix + '/webapp/<path:urlpath>'))

            @flask_app.route('/' + flask_endpoint_prefix + '/webapp/<path:urlpath>')
            def flask_endpoint_webapp_root(urlpath):
                return send_from_directory(filesys_path_to_webdir, urlpath)


    def start_mqtt_connection(self):
        """ Start listening for mqtt messages in a background thread. Recommended
        (but not mandatory) to call after registering known MQTT things. Must call
        stop_mqtt_connection for a clean shutdown. """
        logger.info("ZMF running!")
        self.mqtt.bg_run()

    def stop_mqtt_connection(self):
        """ Call to shutdown any background threads """
        logger.info("ZMF shutting down!")
        self.mqtt.stop()

    def set_mqtt_listener(self, l):
        """ l will be called for every mqtt message. Must implement:
                on_thing_message(thing_id, topic, parsed_msg)
                on_unknown_message(topic, payload)
        """
        return self.mqtt.register_listener(l)

    def mk_graphviz_mqtt_network_map(self):
        class MqttGraphvizWaiter(object):
            def __init__(self, sleep_secs=0.5, timeout_secs=30):
                self.msg = None
                self.ready = False
                self.timeout_secs = timeout_secs
                self.sleep_secs = sleep_secs

            def on_msg(self, topic, msg):
                if topic == 'zigbee2mqtt/bridge/networkmap/graphviz':
                    self.msg = msg
                    self.ready = True

            def active_wait(self):
                slept = 0
                while not self.ready and slept < self.timeout_secs:
                    slept += self.sleep_secs
                    time.sleep(self.sleep_secs)


        waiter = MqttGraphvizWaiter()
        self.mqtt.on_non_json_msg = waiter.on_msg
        self.mqtt.broadcast("bridge/networkmap", "graphviz")
        waiter.active_wait()
        self.mqtt.on_non_json_msg = None

        if waiter.ready:
            return waiter.msg
        else:
            logger.error("Requesting network map from mqtt broker timed out")
            return "Network map timed out", 408


    def register_thing(self, thing):
        """ Make a Thing part of the world. Needs to implement at least
        the same interface as Zigbee2Mqtt2Flask.Thing """
        logger.info("ZMF now knows thing {}".format(thing.get_id()))
        return self.thing_registry.register_thing(thing)

    def get_thing_by_name(self, name):
        return self.thing_registry.get_by_name_or_id(name)

    def get_things_supporting(self, actions):
        return self.thing_registry.get_things_supporting(actions)

    def get_things_with_property(self, prop):
        return self.thing_registry.get_things_with_property(prop)

