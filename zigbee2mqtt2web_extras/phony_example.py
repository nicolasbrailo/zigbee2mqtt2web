""" An example of how to extend Zigbee2Mqtt2Web with custom, non-MQTT, objects.
This is the bare minimum you'll need to make a usable thing. See phony.py for a
less minimalistic example """

from dataclasses import dataclass


@dataclass(frozen=False)
class PhonyAction:
    """ Example of a minimal action. It may contain any user defined values """
    name: str
    value: int


@dataclass(frozen=False)
class Phony:
    """
    A non-MQTT based object, that can still be used through the interface
    offered by a Zigbee2Mqtt2Web thing. Example of the supported actions
    in this object:
        $ curl  localhost:1234/meta/Phony
        $ curl  localhost:1234/meta/Phony/say_hi
        $ curl  localhost:1234/get/Phony
        $ curl  localhost:1234/get/Phony/say_hi
        $ curl -X PUT localhost:1234/set/Phony -d 'say_bye=42'
        $ curl -X PUT localhost:1234/set/Phony -d 'say_hi=4'
    """
    # This is the minimal set of members required
    name: str = "Phony"
    actions: dict = None
    is_zigbee_mqtt: bool = False
    # But the closer it resembles an MQTT thing, the most likely it won't
    # break (your own) code
    description: str = "This is a fake thing"
    thing_type: str = "Phony"
    manufacturer: str = "Phony"

    def __init__(self):
        self.actions = {
            'say_hi': PhonyAction(name='say_hi', value=0),
            'say_bye': PhonyAction(name='say_bye', value=0),
        }

    def get_json_state(self):
        """ Get a phony state; it can be any user defined map """
        return {
            'his': self.actions['say_hi'].value,
            'byes': self.actions['say_bye'].value}

    def get(self, action):
        """ Forward get request to action """
        return self.actions[action].value

    def set(self, action, value):
        """ Forward value to action """
        for _ in range(1, int(value)):
            print(self.actions[action].name)
            self.actions[action].value += 1
