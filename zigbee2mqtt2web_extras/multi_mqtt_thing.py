""" Wrap a set of MQTT things to treat them all as a single instance """

from dataclasses import dataclass

from zigbee2mqtt2web import Zigbee2MqttBridge

import logging
logger = logging.getLogger(__name__)


def _check_actions_same(expected_actions, actual_actions):
    expected = set(expected_actions.keys())
    actual = set(actual_actions.keys())
    # There may be differences in action (eg one may be read only and the other not)
    # but this is probably enough
    return expected.intersection(actual) == expected


@dataclass(frozen=False)
class MultiMqttThing:
    """
    Wrapps a group of MQTT things and forwards all user-side modifications to every
    individual thing under this group. If things are not very very similar (eg same
    make and model) things may behave unexpectedly. If things don't implement the
    same interface, stuff will surely break.
    Note this is just a wrapper, it doesn't hold any logic. The MQTT bridge still
    needs to "own" the things it controls, and the bridge is still responsible for
    broadcasting the state of each thing.
    """
    name: str
    broken: bool
    manufacturer: str
    model: str
    description: str
    thing_type: str
    actions: dict
    group_has_same_metadata: bool
    group_has_same_actions: bool
    is_zigbee_mqtt: bool = False
    # We need a default value for these two, because there are use cases where
    # something may create this object without actually calling __init__(). For
    # example, dataclasses.asdict does this: it will deep-copy an object, then
    # try to serialize it (using pickle?) to a string, bypassing __init__. If
    # we don't initialize it to None, it will try to deep-copy the entire
    # registry, which likely also has a copy of this object and failing after
    # reaching the recursion limit.
    _registry: Zigbee2MqttBridge = None
    _wrapped_things_names: list = None

    def __init__(self, registry, group_name, wrapped_things_names):
        wrapped_things = [registry.get_thing(x) for x in wrapped_things_names]
        if len(wrapped_things) == 0:
            raise RuntimeError(
                'A MultiMqttThing needs at least one thing to wrap')

        self._registry = registry
        self._wrapped_things_names = wrapped_things_names

        self.name = group_name
        self.broken = wrapped_things[0].broken
        self.manufacturer = wrapped_things[0].manufacturer
        self.model = wrapped_things[0].model
        self.description = wrapped_things[0].description
        self.thing_type = wrapped_things[0].thing_type
        self.actions = wrapped_things[0].actions

        for thing in wrapped_things[1:]:
            differences = []
            if thing.broken != self.broken:
                differences.append('broken')
            if thing.manufacturer != self.manufacturer:
                differences.append('manufacturer')
            if thing.model != self.model:
                differences.append('model')
            if thing.description != self.description:
                differences.append('description')
            if thing.thing_type != self.thing_type:
                differences.append('thing_type')

            self.group_has_same_metadata = len(differences) == 0
            if not self.group_has_same_metadata:
                logger.warning(
                    'Group %s is wrapping thing %s with different state. Non matching fields: %s',
                    group_name,
                    thing.name,
                    ','.join(differences))

            self.group_has_same_actions = _check_actions_same(
                self.actions, thing.actions)
            if not self.group_has_same_actions:
                logger.error(
                    'Group %s is wrapping thing %s, with actions different from expected.',
                    group_name,
                    thing.name)

    def get_broadcast_names(self):
        """ Return the MQTT-broadcast names under control of this group """
        return self._wrapped_things_names

    def __getattr__(self, name):
        """ If a method or attribute is called in this object just forward to
        of the wrapped objects """

        # Don't mess with Py's default methods
        if name[0:2] == '__':
            return object.__getattribute__(self, name)

        # _wrapped_things_names is initialized in init(), but copying doesn't have
        # to call init. When this field has its default attribute, it just means
        # someone copied us and is trying to do something (eg serializing to string)
        # so we need to avoid any further getattr calls that may trigger recursion
        if self._wrapped_things_names is None:
            return None

        # Re-fetch all things, in case the underlying object changed
        wrapped_things = [self._registry.get_thing(thing_name)
                          for thing_name in self._wrapped_things_names]

        def funcwrapper(*args, **kwargs):
            last_ex = None
            last_res = None
            first_call = True
            for obj in wrapped_things:
                # Try to find method on this sub-thing; all sub things should
                # be the same type, so fail all calls if this fails
                underlying_function = None
                try:
                    underlying_function = getattr(obj, name)
                except AttributeError as ex:
                    logger.error(
                        "Thing %s: Method %s doesn't exist", self.name, name)
                    raise ex
                except TypeError as ex:
                    logger.error(
                        "Thing %s: Can't call %s for the supplied args",
                        self.name,
                        name)
                    raise ex

                # Invoke method on sub-thing. If one fails, continue executing
                # and raise error on last one.
                this_res = None
                try:
                    #logger.debug(
                    #    "Multi-MQTT dispatch: call %s[%d].%s(%s)",
                    #    obj.name,
                    #    obj.thing_id,
                    #    name,
                    #    args)
                    this_res = underlying_function(*args, **kwargs)
                except Exception as ex:  # pylint: disable=broad-except
                    logger.error(
                        "Thing %s: Exception on %s for sub-thing %s[%d]",
                        self.name,
                        name,
                        obj.name,
                        obj.thing_id,
                        exc_info=True)
                    last_ex = ex

                # All ret vals should be the same, otherwise we don't know how to wrap this.
                # Default to returning whatever was last + printing an error
                if first_call:
                    first_call = False
                else:
                    if last_res != this_res:
                        pass
                    last_res = this_res

            # If there were errors, pick an arbitrary exception to raise
            if last_ex is not None:
                raise last_ex

            # If there were no errors, pick an arbitrary value to return.
            # Hopefully all values are the same
            return last_res

        # Pretend everything is fine if we don't wrap any objects
        if len(self._wrapped_things_names) == 0:
            return None

        # Requested a function-like member, wrap it
        if callable(getattr(wrapped_things[0], name)):
            return funcwrapper

        # Requested a variable-like member, read all of them in case there are
        # side-effects and return the last
        val = None
        for obj in wrapped_things:
            val = getattr(obj, name)
        return val
