from photons_tile_paint.options import BackgroundOption

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

class TilePacmanOptions(dictobj.Spec):
    background = dictobj.Field(BackgroundOption.FieldSpec())
    user_coords = dictobj.Field(sb.boolean, default=False)
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration
