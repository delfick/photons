from photons_tile_paint.options import AnimationOptions, split_by_comma, hue_range_spec, HueRange, normalise_speed_options
from photons_tile_paint.animation import Animation, Finish
from photons_themes.theme import ThemeColor as Color
from photons_themes.canvas import Canvas

from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import random
import math

class Empty:
    pass

class TileFallingOptions(AnimationOptions):
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)
    random_orientations = dictobj.Field(sb.boolean, default=False)

    line_hues = dictobj.NullableField(split_by_comma(hue_range_spec()), default=Empty)
    fade_amount = dictobj.Field(sb.float_spec, default=0.1)
    line_tip_hues = dictobj.NullableField(split_by_comma(hue_range_spec()), default=Empty)

    min_speed = dictobj.Field(sb.float_spec, default=0.2)
    max_speed = dictobj.Field(sb.float_spec, default=0.4)

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration

class Line:
    def __init__(self, column, state):
        self.state = state
        self.parts = []
        self.column = column
        self.bottom = state.bottom - random.randrange(10)
        self.max_length = min([self.state.top - self.state.bottom, 20])

        self.blank_lines = state.options.line_hues is None

        if not self.blank_lines:
            self.line_hues = state.options.line_hues or [HueRange(90, 90)]

        if self.blank_lines and state.options.line_tip_hues is None:
            self.line_tip_hues = [HueRange(40, 40)]
        else:
            self.line_tip_hues = state.options.line_tip_hues

        self.jump = 1
        self.fill()

    def pixels(self):
        j = self.bottom + sum(len(p) for p in self.parts)
        for part in self.parts:
            info = {"hues": []}
            for hue in part:
                j -= 1
                if hue is not None:
                    if "position" not in info:
                        info["position"] = j
                    info["hues"].insert(0, hue)

            hues = info["hues"]
            if not hues:
                continue

            position = info["position"]

            if len(hues) == 1:
                hue = hues[0]
                brightness = 1.0 - (position - math.floor(position))
                color = Color(hue, 1, brightness, 3500)
                yield (self.column, math.floor(position)), color

            else:
                closeness = 1.0 - (position - math.floor(position))
                head_color = Color(hues[0], 1, closeness, 3500)
                middle_hue = hues[0] + min([10, (hues[2] - hues[0]) * closeness])
                if middle_hue > 360:
                    middle_hue -= 360

                middle_color = Color(middle_hue, 1, 1, 3500)
                body_color = Color(hues[2], 1, 1, 3500)

                for i, color in enumerate((head_color, middle_color, body_color)):
                    yield (self.column, math.floor(position) + i), color

    def fill(self):
        top = self.bottom
        for part in self.parts:
            top += len(part)

        while top < self.state.top:
            part = list(self.make_part())
            self.parts.insert(0, part)
            top += len(part)

    @property
    def rate(self):
        if self.state.options.min_speed == self.state.options.max_speed:
            return self.state.options.min_speed

        mn = int(self.state.options.min_speed * 100)
        mx = int(self.state.options.max_speed * 100)
        return random.randint(mn, mx) / 100

    def progress(self):
        self.bottom -= self.rate
        bottom = math.floor(self.bottom)
        if bottom + len(self.parts[-1]) < self.state.bottom:
            self.bottom += len(self.parts.pop())
        self.fill()

    def make_part(self):
        length = random.randrange(0, self.max_length) + 5
        if random.randrange(0, 100) < 50:
            for _ in range(length):
                yield None
            return

        if not self.blank_lines:
            hue_range = random.choice(self.line_hues)

        line = [None for i in range(length)]

        if self.line_tip_hues is not None:
            line[-1] = random.choice(self.line_tip_hues).make_hue()
            length -= 1

        if not self.blank_lines:
            tail_hue = hue_range.make_hue()
            line[length - 1] = tail_hue
            line[length - 2] = tail_hue

            if self.line_tip_hues is None:
                line[length - 3] = tail_hue

        yield from line

class TileFallingState:
    def __init__(self, coords, options):
        self.options = options

        self.coords = coords

        self.left = coords[0][0][0]
        self.right = coords[0][0][0]
        self.top = coords[0][0][1]
        self.bottom = coords[0][0][1]

        for (left, top), (width, height) in coords:
            self.left = min(left, self.left)
            self.right = max(left + width, self.right)
            self.bottom = min(top - height, self.bottom)
            self.top = max(top, self.top)

        self.lines = {}

        for (left, top), (width, height) in self.coords:
            for i in range(width):
                column = left + i
                if column not in self.lines:
                    self.lines[column] = Line(column, self)

        self.canvas = Canvas()

    def tick(self):
        for line in self.lines.values():
            line.progress()
        return self

    def make_canvas(self):
        for point, pixel in list(self.canvas):
            pixel.brightness -= self.options.fade_amount
            if pixel.brightness < 0:
                del self.canvas[point]

        drawn = set()
        for (left, top), (width, height) in self.coords:
            for i in range(left, left + width):
                if i in drawn:
                    continue

                line = self.lines[i]
                for point, pixel in line.pixels():
                    self.canvas[point] = pixel
                drawn.add(i)

        return self.canvas

class TileFallingAnimation(Animation):
    def setup(self):
        self.iteration = 0
        if self.options.random_orientations:
            self.random_orientations = True
        normalise_speed_options(self.options)

        if self.options.line_hues == []:
            self.options.line_hues = None

        if self.options.line_tip_hues == []:
            self.options.line_tip_hues = None

        if self.options.line_hues is Empty:
            self.options.line_hues = [HueRange(90, 90)]

        if self.options.line_tip_hues is Empty:
            self.options.line_tip_hues = [HueRange(40, 40)]

    def next_state(self, prev_state, coords):
        if prev_state is None:
            return TileFallingState(coords, self.options)

        self.iteration += 1
        if self.options.final_iteration(self.iteration):
            raise Finish("Reached max iterations")

        return prev_state.tick()

    def make_canvas(self, state, coords):
        return state.make_canvas()
