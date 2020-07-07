from photons_canvas.animations import Animation, an_animation
from photons_canvas import point_helpers as php

from delfick_project.norms import dictobj, sb
from collections import defaultdict
import random
import math

changers = {}


class changer:
    def __init__(self, name):
        self.name = name

    def __call__(self, kls):
        changers[self.name] = kls
        return kls


class Options(dictobj.Spec):
    changer = dictobj.Field(lambda: sb.string_choice_spec(list(changers)), default="vertical_morph")
    brightness = dictobj.Field(sb.float_spec, default=0.5)
    saturation = dictobj.Field(sb.float_spec, default=1)


class Changer:
    def __init__(self, options):
        self.options = options
        self.setup()

    def setup(self):
        pass

    def _new_device(self, event, state):
        self.point_to_part = {}
        return self.new_device(event, state)

    def new_device(self, event, state):
        pass

    def initial_iteration(self, animation):
        animation.every = 1
        animation.duration = 1

    def change_iterations(self, animation):
        pass

    def progress(self, event, state):
        pass

    def key(self, point, state, canvas):
        raise NotImplementedError()

    def color(self, point, canvas, event, state):
        raise NotImplementedError()

    def part(self, point, canvas):
        part = self.point_to_part.get(point)
        if part is None:
            part = self.point_to_part[point] = list(canvas.point_to_parts[point])[0]
        return part

    def from_hue(self, hue):
        return (hue, self.options.saturation, self.options.brightness, 3500)

    def from_mod_hue(self, hue):
        return (hue % 360, self.options.saturation, self.options.brightness, 3500)


@changer("vertical_morph")
class VerticalMorph(Changer):
    def setup(self):
        self.i = random.randrange(0, 360)

    def new_device(self, event, state):
        num_parts = len(event.canvas.parts)
        divs = ((1, num_parts), (0, num_parts * 2), (0, num_parts * 6))
        return {"divs": divs}

    def change_iterations(self, animation):
        animation.every = 0.2
        animation.duration = 0.3

    def progress(self, event, state):
        self.i = (self.i + 30) % 360

    def key(self, point, state, canvas):
        return (point, self.i)

    def color(self, point, canvas, event, state):
        vs = []
        col, row = point

        for divthentimes, div in state["divs"]:
            if divthentimes:
                col1 = col / div
                row1 = row * div
            else:
                col1 = col * div
                row1 = row / div
            vs.append(col1 + row1)

        colors = []
        for v in vs:
            h = (v + self.i) % 360
            colors.append((h, self.options.saturation, self.options.brightness, 3500))

        return php.average_color(colors)


@changer("cycle")
class Cycle(Changer):
    def setup(self):
        self.i = random.randrange(0, 360)

    def change_iterations(self, animation):
        animation.every = 0.5
        animation.duration = 0.5

    def progress(self, event, state):
        self.i = (self.i + 20) % 360

    def key(self, point, state, canvas):
        return (point, self.i)

    def color(self, point, canvas, event, state):
        return self.from_hue(self.i)


@changer("cycle_parts")
class CycleParts(Changer):
    def new_device(self, event, state):
        if state is None:
            state = {}

        for part in event.canvas.parts:
            if part not in state:
                state[part] = [random.randrange(0, 360), random.randrange(5, 10)]

        return state

    def change_iterations(self, animation):
        animation.every = 0.2
        animation.duration = 0.2

    def progress(self, event, state):
        for p in state.values():
            p[0] = (p[0] + p[1]) % 360

    def key(self, point, state, canvas):
        return (point, tuple(state[self.part(point, canvas)]))

    def color(self, point, canvas, event, state):
        return self.from_hue(state[self.part(point, canvas)][0])


@changer("wave")
class Wave(Changer):
    def setup(self):
        self.i = random.randrange(0, 360)

    def change_iterations(self, animation):
        animation.every = 2
        animation.duration = 2

    def progress(self, event, state):
        self.i = self.i + 200

    def key(self, point, state, canvas):
        return (point, self.i)

    def color(self, point, canvas, event, state):
        col, row = point
        return self.from_mod_hue(col * row + self.i)


@changer("patches")
class Patches(Changer):
    def setup(self):
        self.i = random.randrange(0, 360)
        self.size = 4
        self.points = defaultdict(lambda: random.randrange(0, 360))

    def change_iterations(self, animation):
        animation.every = 2
        animation.duration = 2

    def progress(self, event, state):
        count = 1
        (left_x, right_x), (top_y, bottom_y), (width, height) = event.canvas.bounds
        bounds = (left_x - self.size, right_x), (top_y, bottom_y - self.size), (width, height)
        for point in php.Points.all_points(bounds):
            col, row = point
            if col % self.size == 0 and row % self.size == 0:
                self.i = (self.i + math.sin(count * self.i) + random.randrange(0, 360)) % 360
                self.points[point] = self.i
                count += 1

    def key(self, point, state, canvas):
        return

    def color(self, point, canvas, event, state):
        col, row = point
        col = col - (col % self.size)
        row = row - (row % self.size)
        return self.from_mod_hue(self.points[(col, row)])


class Layer:
    def __init__(self, changer):
        self.event = None
        self.changer = changer

    def layer(self, point, canvas):
        key = self.changer.key(point, self.event.state["state"], canvas)
        if key is not None:
            c = self.event.state["colors"].get(key)

        if key is None or c is None:
            c = self.event.state["colors"][key] = self.changer.color(
                point, canvas, self.event, self.event.state["state"]
            )

        return c

    def next_layer(self, changer, event):
        self.event = event
        changer.progress(event, event.state["state"])
        return self.layer


@an_animation("color_cycle", Options)
class TileColorCycleAnimation(Animation):
    """
    Display pretty colour transitions on the tiles. This animation is a bit
    special in that it's many animations in one.

    Note that for simplification of the code, there are no options per animation.

    The following are the options:

    changer - the animation to run - default vertical_morph
        This is the style off the animation

        * vertical_morph
            The closest to a the MORPH firmware effect I could create.
            Maths is hard.

        * cycle
            The entire canvas cycles between colours.

        * cycle_parts
            Each panel will cycle between colours.

        * wave
            Such a pretty wave of colours.

        * patches
            Each panel is split into 4 patches, which will each cycle colours.

    brightness - float - default 0.5
        The brightness of the colours

    saturation - float - default 1
        The saturation of the colors

    This is a good set of options for this animation:
    https://gist.github.com/delfick/22e984ff9587401a255b175f4db6b309

    run with::

        lifx lan:animate -- file://instructions.json
    """

    Cache = {}

    def setup(self):
        self.changer = changers[self.options.changer](self.options)
        self.changer.initial_iteration(self)

        self.layer = Layer(self.changer)
        self.counter = 0

    async def process_event(self, event):
        if event.is_new_device:
            key = (tuple(sorted(event.canvas.parts)), self.changer.__class__)

            existing_state = (event.state or {}).get("state")
            event.state = TileColorCycleAnimation.Cache[key] = {
                "colors": {},
                "state": self.changer._new_device(event, existing_state),
            }

        elif event.is_tick:
            if self.counter == 1:
                self.changer.change_iterations(self)
                self.counter += 1
            elif self.counter == 0:
                self.counter += 1

            return self.layer.next_layer(self.changer, event)
