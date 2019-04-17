from .thing_registry import ThingRegistry
from .mqtt_proxy import MqttProxy

from flask import send_from_directory

class Zigbee2Mqtt2Flask(object):
    """ Interface between Zigbee/Mqtt and Flask: objects implementing the Thing
    interface can be registered in Zigbee2Mqtt2Flask and their interface will
    be available in endpoints in flask_app. See Zigbee2Mqtt2Flask.things for
    examples. """

    def __init__(self, flask_app, flask_endpoint_prefix, mqtt_ip, mqtt_port, mqtt_topic_prefix):
        self.thing_registry = ThingRegistry(flask_app, flask_endpoint_prefix)
        self.mqtt = MqttProxy(mqtt_ip, mqtt_port, mqtt_topic_prefix, [self.thing_registry])

        print("Registered {} for webapp endpoint".format('/' + flask_endpoint_prefix + '/webapp/<path:path>'))
        @flask_app.route('/' + flask_endpoint_prefix + '/webapp/<path:path>')
        def flask_endpoint_webapp_root(path):
            return send_from_directory('zigbee2mqtt2flask/webapp', path)


    def start_mqtt_connection(self):
        """ Start listening for mqtt messages in a background thread. Recommended
        (but not mandatory) to call after registering known MQTT things. Must call
        stop_mqtt_connection for a clean shutdown. """
        self.mqtt.bg_run()

    def stop_mqtt_connection(self):
        """ Call to shutdown any background threads """
        self.mqtt.stop()

    def set_mqtt_listener(self, l):
        """ l will be called for every mqtt message. Must implement:
                on_thing_message(thing_id, topic, parsed_msg)
                on_unknown_message(topic, payload)
        """
        return self.mqtt.register_listener(l)

    def register_thing(self, thing):
        """ Make a Thing part of the world. Needs to implement at least
        the same interface as Zigbee2Mqtt2Flask.Thing """
        return self.thing_registry.register_thing(thing)

    def get_thing_by_name(self, name):
        return self.thing_registry.get_by_name_or_id(name)


