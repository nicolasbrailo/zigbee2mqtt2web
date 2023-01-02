""" Helper base class for non-MQTT based extras, to help them behave like MQTT things """

from dataclasses import dataclass
from typing import Callable

from zigbee2mqtt2web import Zigbee2MqttAction


@dataclass(frozen=False)
class PhonyZMWThing:
    """ Base class with minimal behaviour to mimic a ZMW thing """
    name: str
    description: str
    thing_type: str
    actions: dict = None
    is_zigbee_mqtt: bool = False
    manufacturer: str = "ZMW"

    def _add_action(self, name, description, getter=None, setter=None):
        @dataclass(frozen=True)
        class _PhonyActionValue:
            get: Callable = None
            set: Callable = None

        new_value = _PhonyActionValue(get=getter, set=setter)
        new_action = Zigbee2MqttAction(
            name=name,
            description=description,
            can_set=(setter is None),
            can_get=(getter is None),
            value=new_value)

        if self.actions is None:
            self.actions = {}
        self.actions[name] = new_action

    def get_json_state(self):
        """ The state for custom things is usually empty: retrieving the actual
        state may depend on an external server, which is slow and may break if
        there is no connectivity, so state is only retrivable by calling
        each action .get() """
        return {}

    def get(self, action):
        """ Dummy forward getter """
        try:
            return self.actions[action].value.get()
        except TypeError as exc:
            raise AttributeError(
                f'Thing {self.name} has no getter for action {action}') from exc

    def set(self, action, value):
        """ Dummy forward setter """
        try:
            return self.actions[action].value.set(value)
        except TypeError as exc:
            raise AttributeError(
                f'Thing {self.name} has no setter for action {action}') from exc
