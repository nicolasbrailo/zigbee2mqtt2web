""" Add support for setting rgb color, if XY color is already supported """

from zigbee2mqtt2web import Zigbee2MqttAction
from zigbee2mqtt2web import Zigbee2MqttActionValue


def _rgb_str_to_cie_xy(rgb):
    if not isinstance(rgb, str):
        raise ValueError('_rgb_str_to_cie_xy only works with strings')

    if rgb[0] == '#':
        rgb = rgb[1:]

    if len(rgb) == 3:
        return _rgb_to_cie_xy(
            (int(
                rgb[0], 16), int(
                rgb[1], 16), int(
                rgb[2], 16)))

    if len(rgb) == 6:
        return _rgb_to_cie_xy(
            (int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)))

    raise ValueError(
        'Unrecognized RGB format, expected #RGB, #RRGGBB, RGB or RRGGBB')


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
    # pylint: disable=invalid-name

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

    # Get X,Y
    xy = (x / (x + y + z), y / (x + y + z))

    return xy


def _add_rgb_support(thing):
    def cb_on_get():
        return thing.actions['color_rgb'].value._current

    def cb_on_set(rgb):
        color_x, color_y = _rgb_str_to_cie_xy(rgb)
        thing.actions['color_xy'].set_value({'x': color_x, 'y': color_y})

    thing.actions['color_rgb'] = Zigbee2MqttAction(
        name='color_rgb',
        description='Color of this light in RGB',
        can_set=True,
        can_get=False,
        value=Zigbee2MqttActionValue(
            thing_name=thing.name,
            meta={
                'type': 'user_defined',
                'property': 'color',
                'on_set': cb_on_set,
                'on_get': cb_on_get},
            _current=None,
        ))


def _if_supports_cie_xy_color(thing):
    return thing.thing_type == 'light' \
        and 'color_xy' in thing.actions \
        and 'color_rgb' not in thing.actions


monkeypatch_add_rgb_support = \
    'Add RGB color support if XY color is present', \
    _if_supports_cie_xy_color, \
    _add_rgb_support
