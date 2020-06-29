from photons_canvas.animations import Animation, an_animation, options
from photons_canvas import point_helpers as php

from delfick_project.norms import dictobj
import random


class Options(dictobj.Spec):
    twinkles_color_range = dictobj.Field(options.color_range_spec("rainbow"))
    twinkles_max_percent = dictobj.Field(options.range_spec((0.1, 0.3), rate=True))
    twinkles_percent_added_at_once = dictobj.Field(options.range_spec((0.01, 0.02), rate=True))

    fade_in_speed = dictobj.Field(options.range_spec((0.1, 0.2), rate=True))
    fade_out_speed = dictobj.Field(options.range_spec((0.1, 0.2), rate=True))


class Twinkle:
    def __init__(self, color, fade_in, fade_out):
        brightness = random.randrange(0, 800) / 1000
        self._color = (color[0], color[1], brightness, color[3])
        self.fades = [fade_in, -fade_out]
        self.direction = 0

    @property
    def color(self):
        c = self._color = php.Color.adjust(
            self._color, brightness_change=self.fades[self.direction]
        )

        if c[2] >= 1:
            self.direction = 1
        elif c[2] <= 0:
            return None

        return c


class Points:
    def __init__(self):
        self.parts = {}
        self.points = set()
        self.dim_rate = options.Rate(0.1, 0.3)

    def add_parts(self, parts):
        for part in parts:
            points = php.Points.all_points(part.bounds)
            self.parts[part] = {p: self.dim_rate() for p in points}

    def layer(self, event, state):
        for part in event.canvas.parts:
            for part, points in list(self.parts.items()):
                if all(php.Color.dead(event.canvas[point]) for point in points):
                    ps = set(points)
                    self.points.update(ps)
                    state.ensure_twinkles(ps)
                    del self.parts[part]

        def layer(point, canvas):
            for part in canvas.point_to_parts[point]:
                if part in self.parts:
                    info = self.parts[part]
                    return canvas.dim(point, info[point])

        return layer


class State:
    def __init__(self, options):
        self.points = Points()
        self.options = options

        self.twinkles = {}

    def ensure_twinkles(self, points):
        max_allowed = int(len(points) * self.options.twinkles_max_percent())

        if len(self.twinkles) > max_allowed:
            return []

        perc = self.options.twinkles_percent_added_at_once()
        from_total = int(len(points) * perc)

        remaining = points - set(self.twinkles)
        from_remaining = int(len(remaining) * perc)

        add_now = from_total
        if add_now > len(remaining):
            add_now = from_remaining

        for point in random.sample(remaining, add_now):
            twinkle = Twinkle(
                self.options.twinkles_color_range.color,
                self.options.fade_in_speed(),
                self.options.fade_out_speed(),
            )
            self.twinkles[point] = twinkle

    def next_layer(self, event):
        self.ensure_twinkles(self.points.points)
        points_layer = self.points.layer(event, self)

        def layer(point, canvas):
            c = points_layer(point, canvas)
            if c is not None:
                return c

            if point in self.twinkles:
                c = self.twinkles[point].color
                if c is None:
                    del self.twinkles[point]
                return c

            return php.Color.ZERO

        return layer


@an_animation("twinkles", Options)
class TwinklesAnimation(Animation):
    """
    Twinkles on the tile!

    When this animation starts, the panels will fade away at different times
    to give a smooth transition from whatever is currently on the tile to
    the twinkles.

    Then the animation will shine dots over all the tiles. This will be pretty.

    Options that are recognised:

    twinkles_color_range - :color_range: - default rainbow
        The colours to choose from each time a twinkle is born.

    twinkles_max_percent - :range: - default to between 0.1 and 0.3
        This is a percentage of the total canvas that can have twinkles on it

    twinkles_percent_added_at_once - :range: - default to between 0.01 and 0.02
        This is the percentage of the total canvas that can have new twinkles
        added to it in a tick.

    fade_in_speed - :range: - default between 0.1 and 0.2
        The amount of brightness change per tick when the twinkle is going from
        starting brightness to full brightness

    fade_out_speed - :range: - default between 0.1 and 0.2
        The amount of brightness change per tick when the twinkle is going from
        full brightness to no brightness
    """

    duration = 0.075
    align_parts_separate = True

    async def process_event(self, event):
        if event.state is None:
            event.state = State(self.options)

        if event.is_new_device:
            event.state.points.add_parts(event.value)

        elif event.is_tick:
            return event.state.next_layer(event)
