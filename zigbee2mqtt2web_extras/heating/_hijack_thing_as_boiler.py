from zigbee2mqtt2web import Zigbee2MqttAction, Zigbee2MqttActionValue
import logging

log = logging.getLogger(__name__)

class _BoilerStateAction(Zigbee2MqttAction):
    def __init__(self, thing):
        if 'state' not in thing.actions:
            raise RuntimeError(f'Thing {thing.name} has no action "state", required for boiler control')

        if thing.actions['state'].value.meta['type'] != 'binary':
            raise RuntimeError(f"Thing {thing.name} action 'state' isn't binary, can't use it for a boiler")

        self.off_val = thing.actions['state'].value.meta['value_off']
        self.on_val = thing.actions['state'].value.meta['value_on']
        self.curr_val = None
        self._set(thing.get('state'))

        val = Zigbee2MqttActionValue(
                thing_name=thing.name,
                meta={
                    'type': 'user_defined',
                    'on_set': self._set,
                    'on_get': self._get},
            )
        super().__init__('state', 'Switch boiler on or off',
                         can_set=True, can_get=True, value=val)

    def accepts_value(self, key, val):
        # ZMW will use "accepts_value" to determine if a key matches a thing. Since we hijacked
        # the 'state' key, we need to accept either boiler_state or state.
        return key == 'state' or key == 'boiler_state'

    def _get(self):
        return self.curr_val

    def _set(self, val):
        if val == True or val == 1 or val == self.on_val:
            self.curr_val = self.on_val
        else:
            self.curr_val = self.off_val


def _set_poweron_behaviour(zmw, thing):
    if 'power_on_behavior' not in thing.actions:
        log.info("Boiler %s doesn't support power_on_behavior, not setting", thing.name)
        return

    if thing.get('power_on_behavior') in ['previous', 'off']:
        #log.debug("Boiler %s already has power_on_behavior=%s, not setting", thing.name, thing.get('power_on_behavior'))
        return

    for val in ['previous', 'off']:
        if val in thing.actions['power_on_behavior'].value.meta['values']:
            thing.set('power_on_behavior', val)
            log.info("Set boiler %s power_on_behavior to '%s'", thing.name, val)
            zmw.registry.broadcast_thing(thing)
            return

    opts = ", ".join(thing.actions['power_on_behavior'].value.meta['values'])
    log.error("Can't set boiler %s power_on_behavior, don't know what option to choose. Options: %s", thing.name, opts)


def _hijack_thing_as_boiler(zmw, thing):
    """ Hack a thing so that its type is not that of a normal thing (ie not a light or a switch)
    Removes all methods that can be 'understood' as a light or switch
    This is useful to stop having a boiler in the normal list of things, and also to skip
    it from the scene manager (eg when 'turning world off')
    Note this will not stop anyone from changing the thing's state via mqtt directly """

    thing.thing_type = 'boiler'
    thing.actions['boiler_state'] = _BoilerStateAction(thing)

    # Remove any actions that may make other modules interested in this thing
    rm_actions = ['state', 'brightness', 'effect', 'transition']
    for act in rm_actions:
        if act in thing.actions:
            del thing.actions[act]

    _set_poweron_behaviour(zmw, thing)

