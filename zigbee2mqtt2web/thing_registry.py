""" Functionality for registering, managing and looking up MQTT based things """

from ctypes import c_int32

import logging
logger = logging.getLogger(__name__)


class ThingRegistry:
    """
    Wraps an MQTT bridge, adding the ability of operating on non-MQTT based
    things. This lets the MQTT bridge handle the state of MQTT based entities,
    while letting users have their own logic mostly independent of MQTT.

    For an example of the interface a non-MQTT object must follow, see
    zmw_things/phony.py
    """

    def __init__(self, mqtt):
        self._known_things = {}
        self._shadowed_mqtt_things = []
        self._mqtt = mqtt

    def __getstate__(self):
        # This is called when a dataclass object is deepcopied to be serialized
        # Some things may hold a reference to the registry, so things break
        # unless we return a dummy dict for serializing (ie that can be picked:
        # https://docs.python.org/3/library/pickle.html#object.__getstate__)
        return {'thing_registry': 'Non-serializable'}

    def start_mqtt_networkmap(self):
        """ See Zigbee2MqttBridge.start_networkmap """
        return self._mqtt.start_networkmap()

    def get_world(self):
        """ Get the state of all the world """
        return [{name: self.get_thing(name).get_json_state()}
                for name in self.get_thing_names()]

    def get_thing_names(self):
        """ Returns the name of 'normal' things (eg not broken or hidden) """
        things = self._mqtt.get_thing_names()
        things.extend(self._known_things.keys())
        for shadowed in self._shadowed_mqtt_things:
            things.remove(shadowed)
        return things

    def get_all_known_thing_names(self):
        """ Returns the name of all things, including broken or hidden """
        things = self._mqtt.get_all_known_thing_names()
        things.extend(self._known_things.keys())
        return things

    def get_known_things_hash(self):
        """ Returns a 32 bit hash of the names of all known things, to let clients determine if the
        network of known devices has changed. Note this doesn't update on actions change. """
        sorted_names = sorted(self.get_thing_names())
        nethash = 0
        for name in sorted_names:
            chr_list = list(name)
            for chr_as_int in list(map(ord, chr_list)):
                nethash = c_int32((nethash << 2) - nethash + chr_as_int).value
        return nethash

    def get_thing(self, name):
        """
        Returns a single thing, or raises a KeyError exception. Non-MQTT things
        take precedence, if a duplicate exists. Don't cache the result: an
        instance of a thing may be replaced by the registry.
        """
        if name in self._known_things:
            return self._known_things[name]
        return self._mqtt.get_thing(name)

    def get_thing_names_of_type(self, type_of_thing):
        """ Returns all things declaring to be of type_of_thing type """
        return [name for name in self.get_thing_names()
                if self.get_thing(name).thing_type == type_of_thing]

    def get_thing_names_with_actions(self, action_list):
        """ Retrieve a list of names of things which support a certain action """
        found = []
        for name in self.get_thing_names():
            thing = self.get_thing(name)
            for action in action_list:
                if action in thing.actions:
                    found.append(name)
                    break
        return found

    def broadcast_things(self, thing_names):
        """ Wrapper over broadcast_thing, when multiple things are updated """
        for name in thing_names:
            self.broadcast_thing(name)

    def update_thing_state(self, thing_or_name):
        """ Force trigger a status update from the mqtt server """
        return self._mqtt.update_thing_state(thing_or_name)

    def broadcast_thing(self, thing_or_name):
        """
        Notify the MQTT registry to update a thing, if it's an MQTT thing (or a
        group of things)
        """
        if isinstance(thing_or_name, str):
            thing_name = thing_or_name
        else:
            thing_name = thing_or_name.name

        if thing_name not in self._known_things:
            # This is an MQTT thing: let the MQTT bcaster handle it
            self._mqtt.broadcast_thing(thing_name)
            return

        # This is not (directly) an MQTT thing, but wraps other MQTT things
        # (and can generate an MQTT status update, so it needs b-cast)
        try:
            thing = self._known_things[thing_name]
            logger.debug(
                'Broadcasting state of multi-MQTT thing %s:',
                thing_name)
            for wrapped_thing_name in thing.get_broadcast_names():
                logger.debug(
                    'Broadcasting state of sub-MQTT thing %s',
                    wrapped_thing_name)
                self._mqtt.broadcast_thing(wrapped_thing_name)
        except AttributeError:
            # This is not an MQTT thing, it's one of our phony things, and
            # it produces no MQTT broadcasts
            logger.debug(
                'Ignore attempt to bcast non MQTT based thing %s',
                thing_name)
            return

    def on_mqtt_network_discovered(self, *k, **kv):
        """ See Zigbee2MqttBridge.on_mqtt_network_discovered """
        return self._mqtt.on_mqtt_network_discovered(*k, **kv)

    def cb_for_mqtt_topic(self, *k, **kv):
        """ See Zigbee2MqttBridge.cb_for_mqtt_topic """
        return self._mqtt.cb_for_mqtt_topic(*k, **kv)

    def register_and_shadow_mqtt_thing(self, multi_thing):
        """
        Adds a thing that wraps other MQTT things. The wrapped objects
        will be hidden from the normal list of things (ie get_thing_names)
        Will register the multi_thing as a normal (non-MQTT) object.
        """
        # This will throw if key is a duplicate or exactly the same as an MQTT
        # thing
        self.register(multi_thing)
        self._shadowed_mqtt_things.extend(multi_thing.get_broadcast_names())

    def register(self, thing):
        """
        Register a new non-MQTT thing. Throws if the thing is known, or if
        an MQTT thing with the same name already exists
        """
        if thing.name in self._known_things:
            raise KeyError(
                f'Non-MQTT thing {thing.name} is already registered.')

        if thing.name in self._mqtt.get_thing_names():
            raise KeyError(
                f'Registering non-MQTT thing {thing.name} would shadow MQTT thing.')

        logger.info('Registering non-MQTT thing %s', thing.name)
        self._known_things[thing.name] = thing

    def replace(self, thing):
        """
        Replaces a non-MQTT thing, if it exists, or forwards the call to the
        MQTT registry (if it's not known by this registry).
        """
        if thing.name in self._known_things:
            self._known_things[thing.name] = thing
        return self._mqtt.replace(thing)
