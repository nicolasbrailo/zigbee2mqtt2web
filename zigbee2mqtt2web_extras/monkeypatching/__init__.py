""" Monkeypatching support: When a thing is discovered, it will try to apply
changes to its behaviour, if the classification matches. This lets us extend
actions (eg support color from RGB when only XY is defined) without coupling
any logic to a thing type or model """

from .random_patches import *
from .rgb_monkeypatcher import monkeypatch_add_rgb_support


def add_all_known_monkeypatches(zigbee2mqtt2web_instance):
    """ Apply all registered monkeypatches to a ZMW instance, so that they
    can be used when a new thing is discovered """
    zigbee2mqtt2web_instance.add_thing_monkeypatch_rule(
        *monkeypatch_add_light_helper_methods)
    zigbee2mqtt2web_instance.add_thing_monkeypatch_rule(
        *monkeypatch_add_light_transition_time_methods)
    zigbee2mqtt2web_instance.add_thing_monkeypatch_rule(
        *monkeypatch_add_color_mode_support)
    zigbee2mqtt2web_instance.add_thing_monkeypatch_rule(
        *monkeypatch_button_classification)
    zigbee2mqtt2web_instance.add_thing_monkeypatch_rule(
        *monkeypatch_add_rgb_support)
    zigbee2mqtt2web_instance.add_thing_monkeypatch_rule(
        *monkeypatch_philips_buttons)
    zigbee2mqtt2web_instance.add_thing_monkeypatch_rule(
        *monkeypatch_sensor_classification)
