from photons_tile_paint.animation import (
    Animation,
    coords_for_horizontal_line,
    put_characters_on_canvas,
    Finish,
)
from photons_tile_paint.font.alphabet_16 import characters as alphabet_16
from photons_tile_paint.font.alphabet_8 import characters as alphabet_8

from photons_themes.canvas import Canvas

import enum


class MarqueeDirection(enum.Enum):
    LEFT = "left"
    RIGHT = "right"


class TileMarqueeAnimation(Animation):
    every = 0.075
    acks = False
    coords = coords_for_horizontal_line
    duration = 0

    def setup(self):
        self.iteration = 0

    class State:
        def __init__(self, x):
            self.x = x

        def move_left(self, amount):
            return self.__class__(self.x - amount)

        def move_right(self, amount):
            return self.__class__(self.x + amount)

        def coords_for(self, original, characters, large):
            coords = []

            top_y = sorted(top_y for (_, top_y), _ in sorted(original))[-1]
            height = original[0][1][1]

            if large:
                height *= 2

            left_x = self.x

            for char in characters:
                coords.append(((left_x, top_y), (char.width, height)))
                left_x += char.width

            return coords

    def next_state(self, prev_state, coords):
        if self.options.direction is MarqueeDirection.LEFT:
            return self.next_state_left(prev_state, coords)
        else:
            return self.next_state_right(prev_state, coords)

    def next_state_left(self, prev_state, coords):
        (left_x, _), (_, _) = sorted(coords)[0]
        left_x -= self.options.text_width

        (right_x, _), (width, _) = sorted(coords)[-1]
        right_x += width

        if prev_state is None:
            return self.State(right_x)

        nxt = prev_state.move_left(getattr(self.options, "speed", 1))
        if nxt.x < left_x:
            self.iteration += 1
            if self.options.final_iteration(self.iteration):
                raise Finish("Reached max iterations")
            nxt = self.State(right_x)

        return nxt

    def next_state_right(self, prev_state, coords):
        (left_x, _), (_, _) = sorted(coords)[0]
        left_x -= self.options.text_width

        (right_x, _), (width, _) = sorted(coords)[-1]
        right_x += width

        if prev_state is None:
            return self.State(left_x)

        if prev_state.x > right_x:
            self.iteration += 1
            if self.options.final_iteration(self.iteration):
                raise Finish("Reached max iterations")
            return self.State(left_x)

        return prev_state.move_right(getattr(self.options, "speed", 1))

    def characters(self, state):
        characters = []
        for ch in self.options.text:
            if getattr(self.options, "large_font", False):
                characters.append(alphabet_16[ch])
            else:
                characters.append(alphabet_8[ch])
        return characters

    def make_canvas(self, state, coords):
        canvas = Canvas()
        characters = self.characters(state)
        coords = state.coords_for(coords, characters, getattr(self.options, "large_font", False))
        put_characters_on_canvas(canvas, characters, coords, self.options.text_color.color)
        return canvas
