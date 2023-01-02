""" A collection of random, simple, monkeypatches """


from zigbee2mqtt2web.zigbee2mqtt_thing import make_user_defined_zigbee2mqttaction


def _add_color_mode_support(thing):
    """ Color mode seems to be set automatically whenever a color is set via XY
    or HS, but it's not one of the actions defined by zigbee2mqtt """
    def cb_set(mode):
        thing.actions['color_mode'].value._current = mode
    thing.actions['color_mode'] = make_user_defined_zigbee2mqttaction(
        thing.name,
        'color_mode',
        "Color mode this light [XY, HS, temp...]",
        setter=cb_set,
        getter=lambda: thing.actions['color_mode'].value._current)


def _if_supports_cie_xy_color(thing):
    return thing.thing_type == 'light' \
        and ('color_xy' in thing.actions
             or 'color_hs' in thing.actions
             or 'color_temp' in thing.actions)


LIKELY_SENSOR_ACTIONS = ['temperature', 'humidity', 'occupancy', 'contact']


def _hack_make_sensor(thing):
    thing.__dict__['thing_type'] = 'sensor'


# Add a sensor type to things that look like sensors
monkeypatch_sensor_classification = \
    'Add sensor thing type, if thing isn\'t classiffied and it looks like a sensor', \
    lambda t: t.thing_type is None \
    and len(set(t.actions.keys()).intersection(LIKELY_SENSOR_ACTIONS)) != 0, \
    _hack_make_sensor


# If a thing doesn't have these actions, it surely isn't a button
BUTTON_MUST_HAVE_ACTIONS = ['battery', 'action']


def _hack_make_button(thing):
    thing.__dict__['thing_type'] = 'button'


def _check_if_button(thing):
    actions = set(thing.actions.keys())
    return actions.intersection(BUTTON_MUST_HAVE_ACTIONS) == set(
        BUTTON_MUST_HAVE_ACTIONS)


def _hack_add_light_helper_methods(thing):
    thing.is_light_on = lambda: thing.get('state')
    thing.is_light_off = lambda: not thing.is_light_on()
    thing.turn_on = lambda: thing.set('state', True)
    thing.turn_off = lambda: thing.set('state', False)

    def _set_brightness_pct(pct):
        min_val = thing.actions['brightness'].value.meta["value_min"]
        max_val = thing.actions['brightness'].value.meta["value_max"]
        val = ((pct / 100.0) * (max_val - min_val)) + min_val
        thing.set('brightness', int(val))

    if 'brightness' in thing.actions:
        thing.set_brightness_pct = _set_brightness_pct


# Things that declare color_* don't always declare color_temp
monkeypatch_add_color_mode_support = \
    'Add color mode support, if color_xy, color_hs or color_temp actions are present', \
    _if_supports_cie_xy_color, \
    _add_color_mode_support


# Philips buttons use some actions they don't declare
monkeypatch_philips_buttons = \
    'Add actions not declared in herdsman to Philips button', \
    lambda t: t.manufacturer == 'Philips' and t.model == '324131092621', \
    lambda t: t.actions['action'].value.meta['values']\
    .extend(['up_press_release', 'down_press_release', 'on_press_release', 'off_press_release'])


# Adds thing_type to things that looks like buttons
monkeypatch_button_classification = \
    'Add button thing type, if thing isn\'t classiffied and it looks like a button', \
    _check_if_button, \
    _hack_make_button


# Adds is_light_on() helper to things that look like lights
monkeypatch_add_light_helper_methods = \
    'Add helper methods like turn_on(), is_light_on(), etc to thing that looks like light', \
    lambda t: t.thing_type == 'light', \
    _hack_add_light_helper_methods
