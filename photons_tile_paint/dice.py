from photons_tile_paint.animation import Animation, put_characters_on_canvas, coords_for_horizontal_line, Finish
from photons_tile_paint.options import BackgroundOption, ColorOption
from photons_tile_paint.font.base import Character
from photons_tile_paint.font.dice import dice

from photons_themes.canvas import Canvas

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import random
import time

full_character = Character("""
    ########
    ########
    ########
    ########
    ########
    ########
    ########
    ########
    """)

class TileDiceRollOptions(dictobj.Spec):
    background = dictobj.Field(BackgroundOption.FieldSpec())
    num_iterations = dictobj.Field(sb.integer_spec, default=1)

    roll_time = dictobj.Field(sb.float_spec, default=2)
    dice_color = dictobj.Field(ColorOption(200, 1, 1, 3500))

class TileDiceRollAnimation(Animation):
    every = 0.01
    duration = 0
    coords = coords_for_horizontal_line

    def setup(self):
        self.remaining = self.options.num_iterations

    def next_state(self, prev_state, coords):
        state = prev_state

        if prev_state is None and self.options.num_iterations == 0:
            return -1

        if prev_state == -2:
            self.remaining -= 1
            if self.remaining <= 0 and self.options.num_iterations != -1:
                raise Finish()
            else:
                self.every = 0.01
                self.duration = 0

                if hasattr(self, "started"):
                    del self.started

                if hasattr(self, "last_state"):
                    del self.last_state

                prev_state = None

        if prev_state == -1:
            return -2

        if prev_state is None or time.time() - self.last_state > 0.05:
            self.last_state = time.time()
            state = random.sample(list(dice.values()), k=5)

        if not hasattr(self, 'started'):
            self.started = time.time()

        if time.time() - self.started > self.options.roll_time:
            return -1

        return state

    def make_canvas(self, state, coords):
        if state == -1:
            self.every = 0.5
            state = [full_character] * 5

        if state == -2:
            self.duration = 0.5
            self.every = 1.5
            state = [random.choice(list(dice.values()))] * 5

        canvas = Canvas()
        put_characters_on_canvas(canvas, state, coords, self.options.dice_color.color)
        return canvas
