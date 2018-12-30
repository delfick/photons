from photons_tile_paint.animation import Animation, coords_for_horizontal_line, Finish
from photons_tile_paint.gameoflife.state import State

class TileGameOfLifeAnimation(Animation):
    every = 0.1
    acks = False
    coords = coords_for_horizontal_line
    duration = 0

    def setup(self):
        self.iteration = 0

    def next_state(self, prev_state, coords):
        if prev_state is None:
            return State(coords, self.options.make_new_color)

        self.iteration += 1
        if self.options.final_iteration(self.iteration):
            raise Finish("Reached max iterations")

        return prev_state.iterate(self.options.iteration_delay)

    def make_canvas(self, state, coords):
        return state.canvas
