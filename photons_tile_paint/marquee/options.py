from photons_tile_paint.options import BackgroundOption, ColorOption
from photons_tile_paint.marquee.animation import MarqueeDirection
from photons_protocol.types import enum_spec

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

class TileMarqueeOptions(dictobj.Spec):
    background = dictobj.Field(BackgroundOption.FieldSpec())
    text_color = dictobj.Field(ColorOption(200, 0.24, 0.5, 3500))
    text = dictobj.Field(sb.string_spec, wrapper=sb.required)
    user_coords = dictobj.Field(sb.boolean, default=False)
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)
    direction = dictobj.Field(enum_spec(None, MarqueeDirection, unpacking=True), default=MarqueeDirection.LEFT)

    @property
    def text_width(self):
        return len(self.text) * 8

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration
