from photons_tile_paint.animation import Animation, Finish
from photons_tile_paint.options import AnimationOptions
from photons_themes.theme import ThemeColor as Color
from photons_themes.canvas import Canvas

from input_algorithms.errors import BadSpecValue
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import random
import math

class HueRange:
    def __init__(self, minimum, maximum):
        self.minimum = minimum
        self.maximum = maximum

    def make_hue(self):
        if self.minimum == self.maximum:
            return self.minimum

        if self.maximum < self.minimum:
            hue = random.randrange(self.minimum, self.maximum + 360)
            if hue > 360:
                hue -= 360
            return hue

        return random.randrange(self.minimum, self.maximum)

class split_by_comma(sb.Spec):
    def setup(self, spec):
        self.spec = spec

    def normalise_empty(self, meta):
        return []

    def normalise_filled(self, meta, val):
        final = []
        if type(val) is list:
            for i, v in enumerate(val):
                final.extend(self.normalise_filled(meta.indexed_at(i), v))
        elif type(val) is str:
            for i, v in enumerate(val.split(",")):
                if v:
                    final.append(self.spec.normalise(meta.indexed_at(i), v))
        else:
            final.append(self.spec.normalise(meta, val))

        return final

class hue_range_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        if val == "rainbow":
            return HueRange(0, 360)

        was_list = False
        if type(val) is list:
            was_list = True
            if len(val) not in (1, 2):
                raise BadSpecValue("A hue range must be 2 or 1 items"
                    , got = val
                    , meta = meta
                    )
            if len(val) == 1:
                val = [val[0], val[0]]

        try:
            val = int(val)
            if val < 0 or val > 360:
                raise BadSpecValue("A hue number must be between 0 and 360", got=val, meta=meta)
            val = [val, val]
        except (ValueError, TypeError):
            pass

        if type(val) is str:
            val = val.split("-", 1)

        for part in val:
            if type(part) is str and (not part or not part.isdigit()):
                msg = "Hue range must be the string 'rainbow' or a string of '<min>-<max>'"
                if was_list:
                    msg = f"{msg} or a list of [<min>, <max>]"
                raise BadSpecValue(msg, got=val, meta=meta)

        rnge = [int(p) for p in val]
        for i, number in enumerate(rnge):
            if number < 0 or number > 360:
                raise BadSpecValue("A hue number must be between 0 and 360"
                    , got=number
                    , meta=meta.indexed_at(i)
                    )

        return HueRange(*rnge)

class TileFallingOptions(AnimationOptions):
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)
    random_orientations = dictobj.Field(sb.boolean, default=False)

    hue_ranges = dictobj.NullableField(split_by_comma(hue_range_spec()), default=[])
    fade_amount = dictobj.Field(sb.float_spec, default=0.1)
    line_tip_hue = dictobj.NullableField(hue_range_spec(), default=HueRange(40, 40))

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
        self.rate = (random.randrange(10, 30) + 10) / 100
        self.max_length = min([self.state.top - self.state.bottom, 20])

        self.blank_lines = state.options.hue_ranges is None

        if not self.blank_lines:
            self.hue_ranges = state.options.hue_ranges or [HueRange(90, 90)]

        if self.blank_lines and state.options.line_tip_hue is None:
            self.line_tip_hue = HueRange(40, 40)
        else:
            self.line_tip_hue = state.options.line_tip_hue

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
            hue_range = random.choice(self.hue_ranges)

        line = [None for i in range(length)]

        if self.line_tip_hue is not None:
            line[-1] = self.line_tip_hue.make_hue()
            length -= 1

        if not self.blank_lines:
            tail_hue = hue_range.make_hue()
            line[length - 1] = tail_hue
            line[length - 2] = tail_hue

            if self.line_tip_hue is None:
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

        for (left, top), (width, height) in self.coords:
            for i in range(left, left + width):
                line = self.lines[i]
                for point, pixel in line.pixels():
                    self.canvas[point] = pixel

        return self.canvas

class TileFallingAnimation(Animation):
    def setup(self):
        self.iteration = 0
        if self.options.random_orientations:
            self.random_orientations = True

    def next_state(self, prev_state, coords):
        if prev_state is None:
            return TileFallingState(coords, self.options)

        self.iteration += 1
        if self.options.final_iteration(self.iteration):
            raise Finish("Reached max iterations")

        return prev_state.tick()

    def make_canvas(self, state, coords):
        return state.make_canvas()
