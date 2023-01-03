""" Groups helper methods to make working on group of lights easier """

import logging
logger = logging.getLogger(__name__)


def any_light_on(registry, light_names):
    """ Returns true if any of the lights in light_names is turned on. Will
    throw an error if any of the things in light_names is not a light """
    for name in light_names:
        if registry.get_thing(name).is_light_on():
            return True
    return False


def any_light_on_in_the_house(registry):
    """ Gets all of the registered lights, and returns true if any of them
    are currently on """
    return any_light_on(registry, registry.get_thing_names_of_type('light'))


def light_group_toggle_brightness_pct(registry, light_group):
    """ Will toggle a set of lights as if they were a group (ie all on, or all
    off). If any of the lights in the group are on, it will try to turn them
    all off. """
    light_names = [name for name, _ in light_group]
    turned_on = None
    if any_light_on(registry, light_names):
        for name, _ in light_group:
            logger.debug('Group toggle: turn off %s', name)
            registry.get_thing(name).turn_off()
        turned_on = False
    else:
        for name, brightness in light_group:
            logger.debug('Group toggle: turn on %s', name)
            registry.get_thing(name).set_brightness_pct(brightness)
        turned_on = True

    registry.broadcast_things(light_names)
    return turned_on
