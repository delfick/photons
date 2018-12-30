from photons_tile_paint.options import AnimationOptions

from photons_themes.theme import ThemeColor as Color

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import random

class TileGameOfLifeOptions(AnimationOptions):
    user_coords = dictobj.Field(sb.boolean, default=True)
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)
    new_color_style = dictobj.Field(sb.string_choice_spec(["random", "average"]), default="average")
    iteration_delay = dictobj.Field(sb.float_spec, default=0.1)

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration

    def make_new_color(self, surrounding):
        if self.new_color_style == "random":
            return Color(random.randrange(0, 360), 1, 1, 3500)
        else:
            return Color.average(surrounding)
