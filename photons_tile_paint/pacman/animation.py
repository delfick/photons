from photons_tile_paint.animation import Animation, coords_for_horizontal_line, put_characters_on_canvas, Finish
from photons_tile_paint.pacman import state

from photons_themes.canvas import Canvas

class TilePacmanAnimation(Animation):
    every = 0.075
    acks = False
    coords = coords_for_horizontal_line
    duration = 0

    def setup(self):
        self.iteration = 0
        if self.options.user_coords:
            self.coords = None

    def next_state(self, prev_state, coords):
        if prev_state is None:
            return state.start(coords)

        if prev_state.finished:
            self.iteration += 1
            if self.options.final_iteration(self.iteration):
                raise Finish("Reached max iterations")
            return prev_state.swap_state(coords)

        return prev_state.move(1)

    def make_canvas(self, state, coords):
        canvas = Canvas()
        put_characters_on_canvas(canvas, state.characters, state.coords_for(coords))
        return canvas
