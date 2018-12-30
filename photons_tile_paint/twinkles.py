from photons_tile_paint.animation import Animation, coords_for_horizontal_line, Finish
from photons_tile_paint.options import AnimationOptions
from photons_themes.theme import ThemeColor as Color
from photons_themes.canvas import Canvas

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import random

# Palettes from https://www.color-hex.com/ (Using HSL)
palettes = {
      "twilight":
      [ (0.65 * 360, 0.53, 0.33, 3500)
      , (0.76 * 360, 0.42, 0.38, 3500)
      , (0.79 * 360, 0.42, 0.73, 3500)
      ]
    , "summertime":
      [ (0.11 * 360, 1   , 0.65, 3500)
      , (0.51 * 360, 0.86, 0.38, 3500)
      , (0.06 * 360, 0.81, 0.54, 3500)
      , (0.58 * 360, 0.82, 0.27, 3500)
      ]
    , "rainbow_dash":
      [ (0.01 * 360, 0.84, 0.57, 3500)
      , (0.06 * 360, 0.89, 0.58, 3500)
      , (0.15 * 360, 0.96, 0.79, 3500)
      , (0.26 * 360, 0.50, 0.51, 3500)
      , (0.55 * 360, 0.97, 0.41, 3500)
      ]
    }

class choose_palette(sb.Spec):
    def normalise_empty(self, meta):
        return None

    def normalise_filled(self, meta, val):
        val = sb.string_choice_spec(list(palettes)).normalise(meta, val)
        return palettes[val]

class TileTwinklesOptions(AnimationOptions):
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)

    palette = dictobj.Field(choose_palette())
    num_twinkles = dictobj.Field(sb.integer_spec, default=20)
    fade_in_speed = dictobj.Field(sb.float_spec, default=0.125)
    fade_out_speed = dictobj.Field(sb.float_spec, default=0.078)

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration

class TwinklesState:
    def __init__(self, coords, options):
        self.options = options

        self.twinkles = {}
        self.directions = {}

        self.left = coords[0][0][0]
        self.right = coords[0][0][0]
        self.top = coords[0][0][1]
        self.bottom = coords[0][0][1]

        for (left, top), (width, height) in coords:
            self.left = min(left, self.left)
            self.right = max(left + width, self.right)
            self.bottom = min(top - height, self.bottom)
            self.top = max(top, self.top)

        self.place_random(random.randrange(0, self.options.num_twinkles / 2))

    def random_coord(self):
        left = random.randrange(self.left, self.right)
        top = random.randrange(self.bottom, self.top)
        return left, top

    def place_random(self, amount):
        for _ in range(amount):
            if self.options.palette:
                hue, saturation, brightness, kelvin = random.choice(self.options.palette)
            else:
                hue = random.randrange(0, 360)
                saturation = random.randrange(5, 10) / 10
                brightness = random.randrange(1, 10) / 10
                kelvin = random.randrange(2500, 9000)

            point = self.random_coord()
            if point not in self.twinkles:
                self.directions[point] = 1 if brightness < 0.6 else 0
                self.twinkles[point] = Color(hue, saturation, brightness, kelvin)

    def tick(self):
        diff = self.options.num_twinkles - len(self.twinkles)
        if diff > 0:
            self.place_random(random.randrange(0, diff))

        for pos, color in list(self.twinkles.items()):
            if color.brightness == 0:
                del self.twinkles[pos]

        for (x, y), color in self.twinkles.items():
            if self.directions[(x, y)] == 0:
                color.brightness -= self.options.fade_in_speed
                if color.brightness < 0:
                    color.brightness = 0
            else:
                color.brightness += self.options.fade_out_speed
                if color.brightness > 1:
                    color.brightness = 1
                    self.directions[(x, y)] = 0

        return self

class TileTwinklesAnimation(Animation):
    coords = coords_for_horizontal_line

    def setup(self):
        self.iteration = 0

    def next_state(self, prev_state, coords):
        if prev_state is None:
            return TwinklesState(coords, self.options)

        self.iteration += 1
        if self.options.final_iteration(self.iteration):
            raise Finish("Reached max iterations")

        return prev_state.tick()

    def make_canvas(self, state, coords):
        canvas = Canvas()
        for point, color in state.twinkles.items():
            canvas[point] = color
        return canvas
