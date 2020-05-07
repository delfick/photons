from photons_canvas.animations import Animation, Finish, an_animation, options
from photons_canvas import Canvas, point_helpers as php
from photons_canvas.animations.lines import LineOptions

from delfick_project.norms import dictobj
import random


class Options(LineOptions):
    rate = dictobj.Field(options.range_spec((1.5, 2), minimum_mn=0.01, maximum_mx=False, rate=True))


class State:
    def __init__(self, options):
        self.lines = {}
        self.rates = {}
        self.start = {}
        self.canvas = Canvas()
        self.options = options

    def add_points(self, bounds):
        for point in php.Points.col(0, bounds):
            row = point[1]
            if row not in self.lines:
                self.start[row] = bounds[0][1]
                self.rates[row] = -self.options.rate()
                self.lines[row] = self.options.make_line(random.randrange(1, 5))

    def progress(self, full_canvas):
        pixels = {}
        (left_x, _), _, _ = full_canvas.bounds

        for row, line in list(self.lines.items()):
            line.progress(self.rates[row])

            px = list(line.pixels(self.start[row], reverse=True))
            if not px or px[0][0] < left_x:
                del self.lines[row]
            else:
                pixels[row] = px

        return pixels


@an_animation("swipe", Options)
class Animation(Animation):
    async def process_event(self, event):
        if not event.state:
            event.state = State(self.options)

        if event.is_new_device:
            event.state.add_points(event.canvas.bounds)
            return

        if not event.is_tick:
            return

        pixels = event.state.progress(event.canvas)

        if not pixels and event.canvas.is_parts(brightness=0):
            raise Finish("Swipe complete")

        def apply_swipe(point, canvas):
            col, row = point

            if row in pixels:
                for i, c in pixels[row]:
                    if col == i:
                        return c
                    elif col < i:
                        return canvas.points.get(point)

            return canvas.dim(point, self.options.fade_amount)

        return apply_swipe
