from photons_themes.theme import ThemeColor as Color

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

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
