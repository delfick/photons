from photons_app.errors import PhotonsAppError

from photons_messages import LightMessages, Waveform

from option_merge_addons import option_merge_addon_hook
from input_algorithms import spec_base as sb
from option_merge import MergedOptions
from input_algorithms.meta import Meta
import colorsys
import logging
import random
import re

log = logging.getLogger("photons_colour")

__shortdesc__ = "Colour conversion functionality"

__doc__ = """
This module knows about colour.

.. autoclass:: photons_colour.Effects
    :members:

.. autoclass:: photons_colour.Parser
"""

regexes = {
      "whitespace": re.compile(r"\s+")
    , "10_random_component": re.compile(r"random")
    , "07_kelvin_component": re.compile(r"\Akelvin:([\d]+)\Z")
    , "06_brightness_component": re.compile(r"\Abrightness:([\d.]+%?)\Z")
    , "05_saturation_component": re.compile(r"\Asaturation:([\d.]+%?)\Z")
    , "04_hue_component": re.compile(r"\Ahue:([\d.]+)\Z")
    , "03_hex_component": re.compile(r"\A(?:hex:)?#?([0-9a-fA-F]{6})\Z")
    , "02_rgb_component": re.compile(r"\Argb:(\d+,\d+,\d+)\Z")
    , "01_hsb_component": re.compile(r"\Ahsb:([\d\.]+),([\d\.]+%?),([\d\.]+%?)\Z")
    }

@option_merge_addon_hook(extras=(("lifx.photons", "messages")))
def __lifx__(collector, *args, **kwargs):
    pass

class NoSuchEffect(PhotonsAppError):
    desc = "No such effect"

class BadColor(PhotonsAppError):
    pass

class ValueOutOfRange(PhotonsAppError):
    pass

class InvalidValue(PhotonsAppError):
    pass

class InvalidColor(PhotonsAppError):
    pass

def split_color_string(color_string):
    """Split a ``color_string`` by whitespace into a list of it's ``components``. """
    if not color_string:
        return []
    return [thing for thing in regexes["whitespace"].split(color_string) if thing]

class Parser(object):
    """
    Class for converting valid colour specifiers into the options for a
    ``SetWaveformOptional`` device command.

    .. note:: http://colorizer.org/ and http://colormine.org/ are amazing!

    The valid colour names are:

    .. show_list:: photons_colour.Parser
        named_colors

    And valid colour specifiers are as follows:

    .. show_regexes:: photons_colour.regexes

    This class also has some classmethods for your use:

    .. automethod:: photons_colour.Parser.hsbk

    .. automethod:: photons_colour.Parser.color_to_msg
    """
    named_colors = {
          "white" : [None, 0, None, None]
        , "red"   : [0, 1, None, None]
        , "orange": [36, 1, None, None]
        , "yellow": [60, 1, None, None]
        , "cyan"  : [180, 1, None, None]
        , "green" : [120, 1, None, None]
        , "blue"  : [250, 1, None, None]
        , "purple": [280, 1, None, None]
        , "pink"  : [325, 1, None, None]
        }

    @classmethod
    def hsbk(kls, components, overrides=None):
        """
        Return ``(h, s, b, k)`` given a list of colour components

        Take into account hue, saturation, brightness and kelvin keys in overrides if provided
        """
        h, s, b, k = kls().parse_color_string(components)
        if overrides:
            h = h if "hue" not in overrides else overrides["hue"]
            s = s if "saturation" not in overrides else overrides["saturation"]
            b = b if "brightness" not in overrides else overrides["brightness"]
            k = k if "kelvin" not in overrides else overrides["kelvin"]
        return h, s, b, k

    @classmethod
    def color_to_msg(kls, components, overrides=None):
        """
        Create a ``SetWaveformOptional`` message that may be used to change the
        state of a device to what has been specified.
        """
        h, s, b, k = kls.hsbk(components, overrides)

        colour = dict(
              hue = 0 if h is None else h
            , set_hue = h is not None

            , saturation = 0 if s is None else s
            , set_saturation = s is not None

            , brightness = 0 if b is None else b
            , set_brightness = b is not None

            , kelvin = 0 if k is None else int(k)
            , set_kelvin = k is not None
            )

        other = dict(
              transient = 0
            , cycles = 1
            , skew_ratio = 0
            , waveform = Waveform.SAW
            , period = 0 if not overrides else overrides.get("duration", 0)
            )

        other_override = Effects.make(**(overrides or {}))
        options = MergedOptions.using(other, other_override, overrides or {}, colour)
        return LightMessages.SetWaveformOptional.normalise(Meta.empty(), options)

    def parse_color_string(self, components):
        if type(components) is str:
            components = split_color_string(components)

        if not components:
            return [None, None, None, None]

        gathered = []
        for component in components:
            gathered.append(self.parse_color_component(component))

        final = []
        for i in range(4):
            for found in gathered:
                if len(final) <= i:
                    final.append(found[i])
                else:
                    final[i] = found[i] if found[i] is not None else final[i]

        return final

    def parse_color_component(self, color_string):
        if color_string in self.named_colors:
            return self.named_colors[color_string]

        try:
            for regex in sorted(regexes):
                if regex.endswith("_component"):
                    m = regexes[regex].match(color_string)
                    if m:
                        func_name = "parse_{0}_component".format(regex.split("_")[1])
                        return getattr(self, func_name)((color_string, ) + m.groups())
        except PhotonsAppError as error:
            raise InvalidColor("Unable to parse color!", got=color_string, error=error.as_dict())
        except Exception as error:
            raise InvalidColor("Unable to parse color!", got=color_string, error=error)

        raise InvalidColor("Unable to parse color!", got=color_string)

    def parse_string(self, s, minimum=0, maximum=1, label=None):
        if s.endswith("%"):
            res = float(s[:-1]) / 100
        else:
            res = float(s)

        if minimum > res or res > maximum:
            raise ValueOutOfRange("Value was not within bounds", minimum=minimum, maximum=maximum, value=res, component=label)

        return res

    def parse_hsb_component(self, groups):
        return [
              self.parse_decimal_string(groups[1], label="hue", minimum=0, maximum=360)
            , self.parse_string(groups[2], label="saturation")
            , self.parse_string(groups[3], label="brightness")
            , None
            ]

    def parse_rgb_component(self, groups):
        r, g, b = groups[1].split(",", 3)
        r = self.parse_string(r, label="r", minimum=0, maximum=255)
        g = self.parse_string(g, label="g", minimum=0, maximum=255)
        b = self.parse_string(b, label="b", minimum=0, maximum=255)
        return [*self.hex_to_hsb(r, g, b), None]

    def parse_hex_component(self, groups):
        first_group = groups[1]
        values = []
        for i in range(0, 6, 2):
            values.append(int(first_group[i:i + 2], 16))
        return [*self.hex_to_hsb(*values), None]

    def parse_hue_component(self, groups):
        return [self.parse_decimal_string(groups[1], label="hue", minimum=0, maximum=360), None, None, None]

    def parse_saturation_component(self, groups):
        return [None, self.parse_string(groups[1], label="saturation", minimum=0, maximum=1), None, None]

    def parse_brightness_component(self, groups):
        return [None, None, self.parse_string(groups[1], label="brightness", minimum=0, maximum=1), None]

    def parse_kelvin_component(self, groups):
        return [None, 0, None, self.parse_decimal_string(groups[1], label="kelvin", minimum=1500, maximum=9000)]

    def parse_random_component(self, groups):
        return [random.randrange(0, 360), 1, None, None]

    def parse_decimal_string(self, s, label=None, minimum=0, maximum=1):
        if s is None:
            raise InvalidColor("Decimal was provided as empty")

        value = float(s)
        if value < minimum or value > maximum:
            raise ValueOutOfRange("Value was not within bounds", component=label, minimum=minimum, maximum=maximum, value=value)

        return value

    def parse_percentage_string(s, label=None, minimum=0, maximum=1):
        if not s:
            raise InvalidColor("Percentage was provided as empty")

        value = float(s.rstrip("%")) / 100.0
        if value < minimum or value > maximum:
            raise ValueOutOfRange("Value was not within bounds", component=label, minimum=minimum, maximum=maximum, value=value)

        return value

    def hex_to_rgb(self, hex_r, hex_g, hex_b):
        """
        Converts a color from RGB with a range of 0-255 to RGB with a 0-1 range
        """
        r = hex_r / 255.0
        g = hex_g / 255.0
        b = hex_b / 255.0
        return (r, g, b)

    def rgb_to_hex(self, r, g, b):
        """
        Converts a color from RGB with a range of 0-1 to a range of 0-255
        """
        hex_r = r * 255.0
        hex_g = g * 255.0
        hex_b = b * 255.0
        return (hex_r, hex_g, hex_b)

    def hex_to_hsb(self, hex_r, hex_g, hex_b):
        """
        RGB with the range 0-255 to hsb.
        """
        r, g, b = self.hex_to_rgb(hex_r, hex_g, hex_b)
        return self.rgb_to_hsb(r, g, b)

    def hsb_to_hex(self, h, s, b):
        """
        HSB to RGB with a 0-255 range
        """
        r, g, b = self.hsb_to_rgb(h, s, b)
        return self.rgb_to_hex(r, g, b)

    def clamp(self, value, minv, maxv):
        """
        This would be nice in the std library.
        """
        if value > maxv:
            return maxv
        if value < minv:
            return minv
        return value

    def clamp_rgb(self, r, g, b):
        """
        Clamp for RGB colors, clamping should never be done on HSB
        """
        r = self.clamp(r, 0, 1)
        g = self.clamp(g, 0, 1)
        b = self.clamp(b, 0, 1)
        return (r, g, b)

    def rgb_to_hsb(self, r, g, b):
        h, s , b = colorsys.rgb_to_hsv(r, g, b)
        return h * 360, s, b

    def hsb_to_rgb(self, h, s, b):
        return colorsys.hsv_to_rgb(h / 360, s, b)

def effect(func):
    func._is_effect = True
    return func

class Effects(object):
    """Class for making options related to special waveform effects"""
    @classmethod
    def make(kls, effect=None, **kwargs):
        if effect is None:
            return {}
        if not hasattr(kls, effect):
            raise NoSuchEffect(effect=effect)
        func = getattr(kls, effect)
        if not getattr(func, "_is_effect", None):
            log.warning("Trying to get an effect that's on Effect, but isn't an effect\teffect=%s", effect)
            raise NoSuchEffect(effect=effect)
        return getattr(kls(), effect)(**kwargs)

    @effect
    def pulse(self, cycles=1, duty_cycle=0.5, transient=1, period=1.0, skew_ratio=sb.NotSpecified, **kwargs):
        """Options to make the light(s) pulse `color` and then back to its original color"""
        if skew_ratio is sb.NotSpecified:
            skew_ratio = 1 - duty_cycle
        return dict(waveform=Waveform.PULSE, cycles=cycles, skew_ratio=skew_ratio, transient=transient, period=period)

    @effect
    def sine(self, cycles=1, period=1.0, peak=0.5, transient=1, skew_ratio=sb.NotSpecified, **kwargs):
        """Options to make the light(s) transition to `color` and back in a smooth sine wave"""
        if skew_ratio is sb.NotSpecified:
            skew_ratio = peak
        return dict(waveform=Waveform.SINE, cycles=cycles, skew_ratio=skew_ratio, transient=transient, period=period)

    @effect
    def half_sine(self, cycles=1, period=1.0, transient=1, **kwargs):
        """Options to make the light(s) transition to `color` smoothly, then immediately back to its original color"""
        return dict(waveform=Waveform.HALF_SINE, cycles=cycles, transient=transient, period=period)

    @effect
    def triangle(self, cycles=1, period=1.0, peak=0.5, transient=1, skew_ratio=sb.NotSpecified, **kwargs):
        """Options to make the light(s) transition to `color` linearly and back"""
        if skew_ratio is sb.NotSpecified:
            skew_ratio = peak
        return dict(waveform=Waveform.TRIANGLE, cycles=cycles, skew_ratio=skew_ratio, transient=transient, period=period)

    @effect
    def saw(self, cycles=1, period=1.0, transient=1, **kwargs):
        """Options to make the light(s) transition to `color` linearly, then instantly back"""
        return dict(waveform=Waveform.SAW, cycles=cycles, transient=transient, period=period)

    @effect
    def breathe(self, cycles=1, period=1, peak=0.5, transient=1, skew_ratio=sb.NotSpecified, **kwargs):
        if skew_ratio is sb.NotSpecified:
            skew_ratio = peak
        return dict(waveform=Waveform.SINE, cycles=cycles, skew_ratio=skew_ratio, transient=transient, period=period)
