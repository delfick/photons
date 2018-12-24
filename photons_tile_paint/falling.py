from photons_tile_paint.animation import Animation, Finish
from photons_tile_paint.options import BackgroundOption
from photons_themes.theme import ThemeColor as Color
from photons_themes.canvas import Canvas

from input_algorithms.errors import BadSpecValue
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import random

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

class TileFallingOptions(dictobj.Spec):
    background = dictobj.Field(BackgroundOption.FieldSpec())
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)

    hue_ranges = dictobj.NullableField(split_by_comma(hue_range_spec()), default=[])
    line_tip_hue = dictobj.NullableField(hue_range_spec(), default=HueRange(60, 60))
    blinking_pixels = dictobj.Field(sb.boolean, default=True)

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
        self.rate = (random.randrange(0, 100) + 10) / 100

        self.blank_lines = state.options.hue_ranges is None

        if not self.blank_lines:
            self.hue_ranges = state.options.hue_ranges or [HueRange(90, 110)]

        if self.blank_lines and state.options.line_tip_hue is None:
            self.line_tip_hue = HueRange(60, 60)
        else:
            self.line_tip_hue = state.options.line_tip_hue

        self.jump = 1
        self.fill()

    def point_for(self, i):
        count = self.bottom
        point = (len(self.parts) - 1, len(self.parts[-1]) - 1)

        while count < i:
            count += 1
            p, pp = point
            pp -= 1
            if pp == -1:
                p -= 1
                pp = len(self.parts[p]) - 1
            point = (p, pp)

        return point

    def __getitem__(self, i):
        point = self.point_for(i)
        return self.parts[point[0]][point[1]]

    def fill(self):
        top = self.bottom
        for part in self.parts:
            top += len(part)

        while top < self.state.top:
            part = list(self.make_part())
            self.parts.insert(0, part)
            top += len(part)

    @property
    def next_amount(self):
        if self.jump >= 1:
            self.jump -= 1
            return 1

        self.jump += self.rate
        return 0

    def progress(self):
        self.bottom -= self.next_amount
        if self.bottom + len(self.parts[-1]) < self.state.bottom:
            self.bottom += len(self.parts.pop())
        self.fill()

    def make_part(self):
        length = random.randrange(0, self.state.top - self.state.bottom) + 5
        if random.randrange(0, 100) < 50:
            for _ in range(length):
                yield Color(0, 0, 0, 3500)
            return

        brightness = 0
        increment = 0.6 / length

        if not self.blank_lines:
            hue_range = random.choice(self.hue_ranges)

        for i in range(length):
            if self.blank_lines:
                hue = 0
                brightness = 0
            else:
                hue = hue_range.make_hue()

            tip = False
            if i == length - 1 and self.line_tip_hue is not None:
                hue = self.line_tip_hue.make_hue()
                brightness = 0.8
                tip = True

            color = Color(hue, 1, brightness, 3500)
            color.tip = tip
            yield color

            brightness += increment

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

    def tick(self):
        for line in self.lines.values():
            line.progress()
        return self

    def make_canvas(self):
        canvas = Canvas()
        for (left, top), (width, height) in self.coords:
            for i in range(left, left + width):
                line = self.lines[i]
                for j in range(top - height, top):
                    got = line[j]
                    if self.options.blinking_pixels:
                        if not getattr(got, "tip", False) and random.randrange(0, 100) < 5:
                            got = Color(got.hue, got.saturation, got.brightness, got.kelvin)
                            got.brightness = 0
                    canvas[(i, j)] = got
        return canvas

class TileFallingAnimation(Animation):
    def setup(self):
        self.iteration = 0

    def next_state(self, prev_state, coords):
        if prev_state is None:
            return TileFallingState(coords, self.options)

        self.iteration += 1
        if self.options.final_iteration(self.iteration):
            raise Finish("Reached max iterations")

        return prev_state.tick()

    def make_canvas(self, state, coords):
        return state.make_canvas()
