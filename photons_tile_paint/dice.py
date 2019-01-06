from photons_tile_paint.animation import Animation, put_characters_on_canvas, coords_for_horizontal_line, Finish
from photons_tile_paint.options import AnimationOptions, ColorOption
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

class TileDiceRollOptions(AnimationOptions):
    num_iterations = dictobj.Field(sb.integer_spec, default=1)

    roll_time = dictobj.Field(sb.float_spec, default=2)
    dice_color = dictobj.Field(ColorOption(200, 1, 1, 3500))

class TileDiceRollAnimation(Animation):
    acks = True
    coords = coords_for_horizontal_line

    def setup(self):
        self.remaining = self.options.num_iterations

    def next_state(self, prev_state, coords):
        state = prev_state

        if prev_state is None and self.options.num_iterations == 0:
            return {"chars": -1}

        if prev_state and prev_state["chars"] == -1:
            return {"chars": -2}

        if prev_state and prev_state["chars"] == -2:
            self.remaining -= 1
            if self.remaining <= 0 and self.options.num_iterations != -1:
                raise Finish()
            else:
                self.every = 0.01
                self.duration = 0
                prev_state = None

        if prev_state is None or time.time() - prev_state["last_state"] > 0.05:
            chs = []
            while len(chs) < len(coords):
                chs.extend(random.sample(list(dice.values()), k=5))

            state = {
                  "chars": random.sample(chs, k=len(coords))
                , "last_state": time.time()
                , "started": time.time() if prev_state is None else prev_state["started"]
                }

        if time.time() - state["started"] > self.options.roll_time:
            return {"chars": -1}

        return state

    def make_canvas(self, state, coords):
        chars = state["chars"]

        if state["chars"] == -1:
            self.every = 0.5
            chars = [full_character] * len(coords)

        if state["chars"] == -2:
            self.duration = 0.5
            self.every = 1.5
            chars = [random.choice(list(dice.values()))] * len(coords)

        canvas = Canvas()
        put_characters_on_canvas(canvas, chars, coords, self.options.dice_color.color)
        return canvas
