""" Groups a set of actions under an easy to access name """

from apscheduler.schedulers.background import BackgroundScheduler
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Callable


@dataclass(frozen=False)
class Scene:
    """ Template for a scene """
    description: str
    apply_scene: Callable

def _make_scene_all_things_off(registry):
    def all_things_off(all_except=None):
        shutdown_transition_secs = 3

        if all_except is None:
            all_except = []

        changes = set()

        # Get things
        brightness_things = registry.get_thing_names_with_actions([
                                                                  'brightness'])
        state_things = registry.get_thing_names_with_actions(['state'])
        stop_things = registry.get_thing_names_with_actions(['stop'])

        # Filter out exceptions
        if len(all_except) != 0:
            brightness_things = [
                name for name in brightness_things if name not in all_except]
            state_things = [
                name for name in state_things if name not in all_except]
            stop_things = [
                name for name in stop_things if name not in all_except]

        for offable_thing in brightness_things:
            thing = registry.get_thing(offable_thing)
            try:
                thing.set('brightness', 0)
                changes.add(thing.name)
            except AttributeError:
                pass

        for offable_thing in state_things:
            thing = registry.get_thing(offable_thing)
            try:
                val = thing.actions['state'].value.meta['value_off']
                thing.set('state', val)
                changes.add(thing.name)
            except AttributeError:
                pass

        for offable_thing in stop_things:
            thing = registry.get_thing(offable_thing)
            try:
                thing.set('stop', True)
                changes.add(thing.name)
            except AttributeError:
                pass

        for changed_thing_name in changes:
            thing = registry.get_thing(changed_thing_name)
            if 'transition' in thing.actions:
                thing.set('transition', shutdown_transition_secs)
            registry.broadcast_thing(thing)

        scheduler = BackgroundScheduler()
        def ensure_all_off():
            # Some (Ikea) things get confused with transition time, so loop 
            # once more at the end with state=off
            for changed_thing_name in changes:
                thing = registry.get_thing(changed_thing_name)
                if 'state' in thing.actions:
                    val = thing.actions['state'].value.meta['value_off']
                    thing.set('state', val)
                    registry.broadcast_thing(thing)
            scheduler.stop()

        scheduler.start()
        scheduler.add_job(
            func=ensure_all_off,
            trigger="date",
            run_date=(datetime.now() + timedelta(seconds=shutdown_transition_secs)))


    return all_things_off


@dataclass(frozen=False)
class SceneManager:
    """
    Holds a list of actions to perform as a shortcut
    """
    name: str = "SceneManager"
    actions: dict = None
    description: str = "Manages scenes and shortcuts"
    thing_type: str = "SceneManager"
    is_zigbee_mqtt: bool = False

    def __init__(self, thing_registry):
        self.actions = {}
        self.add_scene(
            'World off',
            'Turns off everything that looks like it may be turned off',
            _make_scene_all_things_off(thing_registry))
        thing_registry.register(self)

    def add_scene(self, name, description, callback):
        """ Make a new scene public to anyone with access to this thing """
        self.actions[name] = Scene(
            description=description,
            apply_scene=callback)

    def get_json_state(self):
        """ Scene manager has no state """
        return {}

    def get(self, action):
        """ Scene manager has no values to retrieve, but we can return a description """
        return self.actions[action].description

    def set(self, action, _value):
        """ Set will just apply an action, discarding whatever value a user may have set """
        self.actions[action].apply_scene()
