from photons_tile_paint.options import AnimationOptions

from delfick_project.norms import dictobj, sb


class TilePacmanOptions(AnimationOptions):
    user_coords = dictobj.Field(sb.boolean, default=False)
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration
