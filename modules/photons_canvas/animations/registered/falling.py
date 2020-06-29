from photons_canvas.animations import Animation, an_animation, options
from photons_canvas.animations.lines import LineOptions
from photons_canvas import point_helpers as php

from delfick_project.norms import dictobj
import random


class Options(LineOptions):
    rate = dictobj.Field(options.range_spec((0.3, 0.6), rate=True))


class Line:
    def __init__(self, line, rate, start, blank, tail):
        self.line = line
        self.tail = tail
        self.rate = rate
        self.start = start
        self.blank = blank

    @classmethod
    def make(kls, options, top_y):
        rate = -options.rate()
        blank = random.randrange(0, 100) < 50
        tail = random.randrange(10, 15)
        line = options.make_line(random.randrange(3, 6))
        start = top_y + random.randrange(6, 10)
        return Line(line, rate, start, blank, tail)

    def pixels(self, col, onto):
        self.line.progress(self.rate)
        pixels = list(self.line.pixels(self.start, reverse=True))

        top = None
        for row, color in pixels:
            top = row
            if self.blank:
                color = None
            onto[(col, row)] = color

        return top


class State:
    def __init__(self, options):
        self.done = {}
        self.lines = {}
        self.rates = {}
        self.start = {}
        self._bounds = None
        self.options = options

        self.extreme_top = None
        self.extreme_bottom = None

    @property
    def bounds(self):
        return self._bounds

    @bounds.setter
    def bounds(self, bounds):
        _, (self.extreme_top, self.extreme_bottom), _ = bounds

        for point in php.Points.row(0, bounds):
            col = point[0]
            if col not in self.lines:
                self.lines[col] = []

    @property
    def next_layer(self):
        pixels = {}

        for col, lines in list(self.lines.items()):
            remove = []

            most_top = None
            for line in lines:
                top = line.pixels(col, pixels)
                if most_top is None or top > most_top:
                    most_top = top

                if top < self.extreme_bottom:
                    remove.append(line)

            self.lines[col] = [l for l in self.lines[col] if l not in remove]

            if most_top is None or self.extreme_top - most_top > random.randrange(3, 7):
                self.lines[col].append(Line.make(self.options, self.extreme_top))

        self.done.update(pixels)

        def layer(point, canvas):
            p1 = pixels.get(point)
            p2 = canvas.points.get(point)
            if not p1 and not p2:
                return
            elif p1 and not p2:
                return p1
            elif p2 and not p1:
                if point not in self.done:
                    return p2
                else:
                    return canvas.dim(point, self.options.fade_amount)
            else:
                c = canvas.dim(point, self.options.fade_amount)
                if not c:
                    return p1

                return php.average_color([p1, c])

        return layer


@an_animation("falling", Options)
class FallingAnimation(Animation):
    """
    Make lines fall from the top of the tiles and wipe out everything below them.

    There will be multiple lines of varying length per column of the canvas with
    gaps spread throughout.

    The following options are allowed:

    rate - :range: of pixels - default between 0.3 and 0.6
        This is the number of pixels that are progressed each tick of the
        animation. This can be less than one and the animation will use tricks
        to make the progression appear smooth.

        The minimum is 0.01 and there is no maximum.

    line_hues - :color_range: - default rainbow
        The colours used to give to each line when they are created

    fade_amount - float - default 0.1
        The amount to fade the lines each tick. A small number will produce a
        longer line as it fades slower.
    """

    def setup(self):
        self.duration = self.every

    async def process_event(self, event):
        if not event.state:
            event.state = State(self.options)

        if event.is_new_device:
            event.state.bounds = event.canvas.bounds

        elif event.is_tick:
            return event.state.next_layer
