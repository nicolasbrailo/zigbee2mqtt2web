from .thing import Zigbee2MqttAction
from .thing import Zigbee2MqttActionValue

import time

from zzmw_common.service_runner import build_logger
log = build_logger("Z2M")

def _rgb_to_cie_xy(rgb_color):
    """
https://github.com/PhilipsHue/PhilipsHueSDK-iOS-OSX/commit/f41091cf671e13fe8c32fcced12604cd31cceaf3

# Conversion between RGB and xy in the CIE 1931 colorspace for hue
The conversion between RGB and xy in the CIE 1931 colorspace is not something
Philips invented, but we have an optimized conversion for our different light
types, like hue bulbs and LivingColors. It is important to differentiate between
the various light types, because they do not all support the same color gamut.
For example, the hue bulbs are very good at showing nice whites, while the
LivingColors are generally a bit better at colors, like green and cyan. In the
PHUtility class contained in the Hue iOS SDK [
https://github.com/PhilipsHue/PhilipsHueSDKiOS] you can see our Objective-C
implementation of these transformations, which is used in our iOS SDK for hue.

The method signature for converting from xy values and brightness to a color is:
 + (UIColor *)colorFromXY:(CGPoint)xy andBrightness:(float)brightness
       forModel:(NSString*)model

The method signature for converting from a color to xy and brightness values:
 + (void)calculateXY:(CGPoint *)xy andBrightness:(float *)brightness
       fromColor:(UIColor *)color forModel:(NSString*)model

The color to xy/brightness does not return a value, instead takes two pointers
to variables which it will change to the appropriate values. The model parameter
of both methods is the modelNumber value of a PHLight object. The advantage of
this model being settable is that you can decide if you want to limit the color
of all lights to a certain model, or that every light should do the colors
within its own range.

Current Philips lights have a color gamut defined by 3 points, making it a
triangle. For the hue bulb the corners of the triangle are:
* Red: 0.675, 0.322
* Green: 0.4091, 0.518
* Blue: 0.167, 0.04

For LivingColors Bloom, Aura and Iris the triangle corners are:
* Red: 0.704, 0.296
* Green: 0.2151, 0.7106
* Blue: 0.138, 0.08

If you have light which is not one of those, you should use:
* Red: 1.0, 0
* Green: 0.0, 1.0
* Blue: 0.0, 0.0

# Color to XY
We start with the color to xy conversion, which we will do in a couple of steps:

1. Get the RGB values from your color object and convert them to be between 0
   and 1. So the RGB color (255, 0, 100) becomes (1.0, 0.0, 0.39)

2. Apply a gamma correction to the RGB values, which makes the color more vivid
   and more the like the color displayed on the screen of your device.

This gamma correction is also applied to the screen of your computer or phone,
thus we need this to create the same color on the light as on screen. This is
done by the following formulas:

* float red = (red   > 0.04045f) ?
              pow((red   + 0.055f) / (1.0f + 0.055f), 2.4f) : (red   / 12.92f);
* float green = (green > 0.04045f) ?
              pow((green + 0.055f) / (1.0f + 0.055f), 2.4f) : (green / 12.92f);
* float blue = (blue  > 0.04045f) ?
              pow((blue  + 0.055f) / (1.0f + 0.055f), 2.4f) : (blue  / 12.92f);

3. Convert the RGB values to XYZ using the Wide RGB D65 conversion formula
   The formulas used:
    float X = red * 0.649926f + green * 0.103455f + blue * 0.197109f;
    float Y = red * 0.234327f + green * 0.743075f + blue * 0.022598f;
    float Z = red * 0.0000000f + green * 0.053077f + blue * 1.035763f;

4. Calculate the xy values from the XYZ values
    float x = X / (X + Y + Z);
    float y = Y / (X + Y + Z);

5. Check if the found xy value is within the color gamut of the light, if not
   continue with step 6, otherwise step 7. When we sent a value which the light
   is not capable of, the resulting color might not be optimal. Therefor we try
    to only sent values which are inside the color gamut of the selected light.

6. Calculate the closest point on the color gamut triangle and use that as xy
   value. The closest value is calculated by making a perpendicular line to one
   of the lines the triangle consists of and when it is then still not inside
   the triangle, we choose the closest corner point of the triangle.

7. Use the Y value of XYZ as brightness. The Y value indicates the brightness of
   the converted color.

# XY to color

The xy to color conversion is almost the same, but in reverse order.

1. Check if the xy value is within the color gamut of the lamp, if not continue
   with step 2, otherwise step 3. We do this to calculate the most accurate
   color the given light can actually do.

2. Calculate the closest point on the color gamut triangle and use that as xy
   value. See step 6 of color to xy.

3. Calculate XYZ values. Convert using the following formulas:
    float x = x; // the given x value
    float y = y; // the given y value
    float z = 1.0f - x - y;
    float Y = brightness; // The given brightness value
    float X = (Y / y) * x;
    float Z = (Y / y) * z;

4. Convert to RGB using Wide RGB D65 conversion (THIS IS A D50 conversion
   currently):
    float r = X  * 1.4628067f - Y * 0.1840623f - Z * 0.2743606f;
    float g = -X * 0.5217933f + Y * 1.4472381f + Z * 0.0677227f;
    float b = X  * 0.0349342f - Y * 0.0968930f + Z * 1.2884099f;

5. Apply reverse gamma correction
    r = r <= 0.0031308f ?
            12.92f * r : (1.0f + 0.055f) * pow(r, (1.0f / 2.4f)) - 0.055f;
    g = g <= 0.0031308f ?
            12.92f * g : (1.0f + 0.055f) * pow(g, (1.0f / 2.4f)) - 0.055f;
    b = b <= 0.0031308f ?
            12.92f * b : (1.0f + 0.055f) * pow(b, (1.0f / 2.4f)) - 0.055f;

6. Convert the RGB values to your color object

The rgb values from the above formulas are between 0.0 and 1.0.

# Further Information
The following links provide further useful related information
* sRGB: http://en.wikipedia.org/wiki/Srgb
* A Review of RGB Color Spaces:
    http://www.babelcolor.com/download/A%20review%20of%20RGB%20color%20spaces.pdf
"""
    def gamma_correct(color_elm):
        if color_elm > 0.04045:
            return pow((color_elm + 0.055) / (1.0 + 0.055), 2.4)
        return color_elm / 12.92

    # Convert RGB to %, then gamma correct
    rgb_gamma_pct = tuple(gamma_correct(color_elm / 255.0)
                          for color_elm in rgb_color)

    # Do magic to get XYZ (aka "Wide RGB D65 conversion formula")
    r, g, b = rgb_gamma_pct
    x = r * 0.649926 + g * 0.103455 + b * 0.197109
    y = r * 0.234327 + g * 0.743075 + b * 0.022598
    z = r * 0.000000 + g * 0.053077 + b * 1.035763

    if (x + y + z) == 0:
        # Technically this should be the center of the XY triangle, but because
        # lights can't display black it doesn't mater what color we choose, something's broken
        return {'x': 0, 'y': 0}

    return {'x': x / (x + y + z),
            'y': y / (x + y + z)}


def _rgb_str_to_cie_xy(rgb):
    if not isinstance(rgb, str):
        raise ValueError('_rgb_str_to_cie_xy only works with strings')

    if rgb[0] == '#':
        rgb = rgb[1:]

    if len(rgb) == 3 or len(rgb) == 4:
        # For len == 4 it's likely to be RGBA. We don't support alpha, so ignore it.
        return _rgb_to_cie_xy(
            (int(
                rgb[0], 16), int(
                rgb[1], 16), int(
                rgb[2], 16)))

    if len(rgb) == 6:
        return _rgb_to_cie_xy(
            (int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)))

    raise ValueError(f'Unrecognized RGB format, expected #RGB, #RRGGBB, RGB or RRGGBB, got "{rgb}"')



def _monkeypatch_light(light):
    light.is_light_on = lambda: light.get('state')
    light.is_light_off = lambda: not light.is_light_on()
    light.turn_on = lambda: light.set('state', True)
    light.turn_off = lambda: light.set('state', False)
    light.toggle = lambda: light.set('state', False if light.is_light_on() else True)

    def _set_brightness_pct(pct):
        min_val = light.actions['brightness'].value.meta["value_min"]
        max_val = light.actions['brightness'].value.meta["value_max"]
        val = ((pct / 100.0) * (max_val - min_val)) + min_val
        light.set('brightness', int(val))
    def _get_brightness_pct():
        min_val = light.actions['brightness'].value.meta["value_min"]
        max_val = light.actions['brightness'].value.meta["value_max"]
        v = light.get('brightness')
        if v is None:
            return 0
        return 100.0 * (v - min_val) / (max_val - min_val)
    if 'brightness' in light.actions:
        light.set_brightness_pct = _set_brightness_pct
        light.get_brightness_pct = _get_brightness_pct

    light.actions['level_config'] = Zigbee2MqttAction(
        name='level_config',
        description='State after powerloss, schema is buggy',
        can_set=False, # It should be settable, but we don't expose it
        can_get=False,
        value=Zigbee2MqttActionValue(
            thing_name=light.name,
            meta={
                'type': 'user_defined',
                'on_set': lambda x: None,
                'on_get': lambda: None,
            },
        ))
    if 'transition' not in light.actions:
        light.actions['transition'] = Zigbee2MqttAction(
            name='transition',
            description='Adds a transition time for state changes',
            can_set=True,
            can_get=False,
            value=Zigbee2MqttActionValue(
                thing_name=light.name,
                meta={'type': 'numeric', 'value_min': 0, 'value_max': 10}
            ))
    if 'color_temp' not in light.actions and light.manufacturer == 'Philips' and light.model == "7299760PH":
        light.actions['color_temp'] = Zigbee2MqttAction(
            name='color_temp',
            description='Color temperature; this is sent by the z2m server, but not in schema',
            can_set=False,
            can_get=False,
            value=Zigbee2MqttActionValue(
                thing_name=light.name,
                meta={'type': 'numeric', 'value_min': 0, 'value_max': 255}
            ))
    if ('color_xy' in light.actions) and ('color_rgb' not in light.actions):
        light.actions['color_rgb'] = Zigbee2MqttAction(
            name='color_rgb',
            description='Color of this light in RGB',
            can_set=True,
            can_get=False,
            value=Zigbee2MqttActionValue(
                thing_name=light.name,
                meta={
                    'type': 'user_defined',
                    'on_set': lambda rgb: light.actions['color_xy'].set_value(_rgb_str_to_cie_xy(rgb)),
                    'on_get': lambda: light.actions['color_rgb'].value._current,
                },
                _current=None,
            ))
    supports_color = ('color_xy' in light.actions) or ('color_hs' in light.actions) or ('color_temp' in light.actions)
    if supports_color and ('color_mode' not in light.actions):
        def color_mode_set(x):
            light.actions['color_mode'].value._current = x
        light.actions['color_mode'] = Zigbee2MqttAction(
            name='color_mode',
            description='Color mode of this light [XY, HS, temp...]',
            can_set=True,
            can_get=True,
            value=Zigbee2MqttActionValue(
                thing_name=light.name,
                meta={
                    'type': 'user_defined',
                    'on_set': color_mode_set,
                    'on_get': lambda: light.actions['color_mode'].value._current,
                },
                _current=None,
            ))

def monkeypatch_lights(z2m):
    """ Look for all lights in an instance of z2m and apply useful monkeypatches """
    for light in z2m.get_things_if(lambda t: t.thing_type == 'light'):
        log.debug("Thing %s is a light, will monkeypatch", light.name)
        _monkeypatch_light(light)

def any_light_on(z2m, light_names):
    """ Returns true if any of the lights in light_names is turned on. Will
    throw an error if any of the things in light_names is not a light. Will throw if not a light, or thing doesn't exist """
    for name in light_names:
        if z2m.get_thing(name).is_light_on():
            return True
    return False

def light_group_toggle_brightness_pct(z2m, light_group):
    """ Will toggle a set of lights as if they were a group (ie all on, or all
    off). If any of the lights in the group are on, it will try to turn them
    all off. """
    light_names = [name for name, _ in light_group]
    turned_on = None
    if any_light_on(z2m, light_names):
        for name, _ in light_group:
            log.debug('Group toggle: turn off %s', name)
            z2m.get_thing(name).turn_off()
        turned_on = False
    else:
        for name, brightness in light_group:
            log.debug('Group toggle: turn on %s', name)
            z2m.get_thing(name).set_brightness_pct(brightness)
        turned_on = True

    z2m.broadcast_things(light_names)
    return turned_on

def turn_all_lights_off(z2m, transition_secs=None):
    """ Turns ALL lights off (even lights that are already off, just in case) """
    lights = z2m.get_things_if(lambda t: t.thing_type == 'light')
    for light in lights:
        light.set('state', False)
        if 'brightness' in light.actions:
            light.set_brightness_pct(0)
        if transition_secs is not None:
            light.set('transition', transition_secs)
    z2m.broadcast_things(lights)

    # Restore transition if one was set
    if transition_secs is not None:
        log.debug("Implementing advanced MQTT b-cast synchronization mechanism to avoid race conditions on MQTT vs user-set values")
        time.sleep(1)

        for light in lights:
            light.set('state', False)
            light.set('transition', 0)
        z2m.broadcast_things(lights)

