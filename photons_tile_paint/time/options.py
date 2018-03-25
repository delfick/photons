from photons_tile_paint.options import BackgroundOption, ColorOption

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

class TileTimeOptions(dictobj.Spec):
    background = dictobj.Field(BackgroundOption.FieldSpec())
    hour24 = dictobj.Field(sb.boolean, default=True)
    number_color = dictobj.Field(ColorOption(200, 0.24, 0.5, 3500))
    progress_bar_color = dictobj.Field(ColorOption(0, 1, 0.4, 3500))
    full_height_progress = dictobj.Field(sb.boolean, default=False)
