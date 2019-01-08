from photons_themes.theme import ThemeColor as Color

from input_algorithms.errors import BadSpecValue
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import random

class BackgroundOption(dictobj.Spec):
    type = dictobj.Field(sb.string_choice_spec(["specified", "current"]), default="specified")

    hue = dictobj.Field(sb.float_spec, default=0)
    saturation = dictobj.Field(sb.float_spec, default=0)
    brightness = dictobj.Field(sb.float_spec, default=0)
    kelvin = dictobj.Field(sb.float_spec, default=3500)

    @property
    def default_color(self):
        return Color(self.hue, self.saturation, self.brightness, self.kelvin)

def ColorOption(h, s, b, k):
    class C(dictobj.Spec):
        hue = dictobj.Field(sb.float_spec, default=h)
        saturation = dictobj.Field(sb.float_spec, default=s)
        brightness = dictobj.Field(sb.float_spec, default=b)
        kelvin = dictobj.Field(sb.integer_spec, default=k)

        @property
        def color(self):
            return Color(self.hue, self.saturation, self.brightness, self.kelvin)
    return C.FieldSpec()

class AnimationOptions(dictobj.Spec):
    background = dictobj.Field(BackgroundOption.FieldSpec())
    combine_tiles = dictobj.Field(sb.boolean, default=False)

class HueRange:
    def __init__(self, minimum, maximum):
        self.minimum = minimum
        self.maximum = maximum

    def make_hue(self):
        if self.minimum == self.maximum:
            return self.minimum

        if self.maximum < self.minimum:
            hue = random.randrange(self.minimum, self.maximum + 360)
            if hue > 360:
                hue -= 360
            return hue

        return random.randrange(self.minimum, self.maximum)

class split_by_comma(sb.Spec):
    def setup(self, spec):
        self.spec = spec

    def normalise_empty(self, meta):
        return []

    def normalise_filled(self, meta, val):
        final = []
        if type(val) is list:
            for i, v in enumerate(val):
                final.extend(self.normalise_filled(meta.indexed_at(i), v))
        elif type(val) is str:
            for i, v in enumerate(val.split(",")):
                if v:
                    final.append(self.spec.normalise(meta.indexed_at(i), v))
        else:
            final.append(self.spec.normalise(meta, val))

        return final

class hue_range_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        if val == "rainbow":
            return HueRange(0, 360)

        was_list = False
        if type(val) is list:
            was_list = True
            if len(val) not in (1, 2):
                raise BadSpecValue("A hue range must be 2 or 1 items"
                    , got = val
                    , meta = meta
                    )
            if len(val) == 1:
                val = [val[0], val[0]]

        try:
            val = int(val)
            if val < 0 or val > 360:
                raise BadSpecValue("A hue number must be between 0 and 360", got=val, meta=meta)
            val = [val, val]
        except (ValueError, TypeError):
            pass

        if type(val) is str:
            val = val.split("-", 1)

        for part in val:
            if type(part) is str and (not part or not part.isdigit()):
                msg = "Hue range must be the string 'rainbow' or a string of '<min>-<max>'"
                if was_list:
                    msg = f"{msg} or a list of [<min>, <max>]"
                raise BadSpecValue(msg, got=val, meta=meta)

        rnge = [int(p) for p in val]
        for i, number in enumerate(rnge):
            if number < 0 or number > 360:
                raise BadSpecValue("A hue number must be between 0 and 360"
                    , got=number
                    , meta=meta.indexed_at(i)
                    )

        return HueRange(*rnge)

def normalise_speed_options(options):
    if options.min_speed < 0:
        options.min_speed = 0

    if options.max_speed < 0:
        options.max_speed = 0

    if options.min_speed > options.max_speed:
        options.min_speed, options.max_speed = options.max_speed, options.min_speed

    if options.min_speed == 0 and options.max_speed == 0:
        options.max_speed = 0.1
