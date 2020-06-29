from photons_canvas.animations import Animation, Finish, an_animation, options
from photons_canvas import point_helpers as php

from delfick_project.norms import dictobj
import random


class Options(dictobj.Spec):
    color_range = dictobj.Field(options.color_range_spec("rainbow"))


class State:
    def __init__(self, color_range):
        self.color = color_range.color

        self.start = {}
        self.changed = {}
        self.remaining = set()

    def add_points(self, parts, canvas):
        for part in parts:
            for point in php.Points.all_points(part.bounds):
                if point not in self.changed:
                    self.start[point] = canvas[point]
                    self.remaining.add(point)

    def progress(self):
        amount = len(self.start) // 15
        next_selection = random.sample(list(self.remaining), k=min(len(self.remaining), amount))

        for point in next_selection:
            self.changed[point] = self.color
            self.remaining.remove(point)

    def finished(self, canvas):
        return not self.remaining and canvas.is_parts(brightness=0)


@an_animation("dots", Options)
class Animation(Animation):
    """
    Slowly fill up the canvas with dots until the whole canvas is full of the
    new colour and then fade to black.

    The positions on the tiles are ignored and tiles are treated as if they
    are all separate to each other.

    This animation has a single option:

    color_range - :color_range: - default rainbow
        The colour to choose for the dots in this animation.
    """

    align_parts_straight = True

    async def process_event(self, event):
        if event.state is None:
            event.state = State(self.options.color_range)

        if event.is_new_device:
            event.state.add_points(event.value, event.canvas)
            return

        if not event.is_tick:
            return

        if event.state.finished(event.canvas):
            raise Finish("Finished dots")

        if not event.state.remaining:
            self.duration = 1
            self.every = 1
            return lambda point, canvas: None

        event.state.progress()

        if not event.state.remaining:
            self.acks = True

        state = event.state

        def dots(point, canvas):
            changed = state.changed.get(point)
            if changed:
                return changed
            return state.start.get(point)

        return dots
