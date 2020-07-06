from photons_canvas import Canvas, point_helpers as php

from photons_app import helpers as hp

from photons_control.script import FromGenerator
from photons_control.colour import make_hsbk
from photons_messages import LightMessages

from delfick_project.norms import sb, dictobj, Meta
import logging
import kdtree
import random

log = logging.getLogger("photons_canvas.themes.addon")

default_colors = [
    (0, 1, 0.3, 3500),
    (40, 1, 0.3, 3500),
    (60, 1, 0.3, 3500),
    (127, 1, 0.3, 3500),
    (239, 1, 0.3, 3500),
    (271, 1, 0.3, 3500),
    (294, 1, 0.3, 3500),
]


class colors_spec(sb.Spec):
    def normalise_empty(self, meta):
        return default_colors

    def normalise_filled(self, meta, val):
        cs = [make_hsbk(val) for val in val]
        return [(c["hue"], c["saturation"], c["brightness"], c["kelvin"]) for c in cs]


class Overrides(dictobj.Spec):
    hue = dictobj.NullableField(sb.float_spec)
    saturation = dictobj.NullableField(sb.float_spec)
    brightness = dictobj.NullableField(sb.float_spec)
    kelvin = dictobj.NullableField(sb.integer_spec)


class Options(dictobj.Spec):
    colors = dictobj.Field(colors_spec)
    duration = dictobj.Field(sb.float_spec(), default=1)
    power_on = dictobj.Field(sb.boolean, default=True)
    overrides = dictobj.Field(Overrides.FieldSpec)

    @hp.memoized_property
    def override_layer(self):
        def layer(point, canvas):
            c = canvas[point]
            if c is not None:
                return canvas.override(point, **self.overrides)
            else:
                return c

        return layer


class Applier:
    def __init__(self, canvas, colors):
        self.canvas = canvas
        self.colors = colors

    def apply(self):
        if len(self.canvas.points) == 1:
            for point in self.canvas.points:
                self.canvas[point] = random.choice(self.colors)
            return

        tree = kdtree.create([], dimensions=2)

        all_points = set()
        for part in self.canvas.parts:
            for point in php.Points.all_points(php.Points.expand(part.bounds, 3)):
                all_points.add(point)

        all_points = list(all_points)
        random.shuffle(all_points)

        seed_number = int(len(all_points) * 0.3)
        for point in random.choices(all_points, k=seed_number):
            self.canvas[point] = random.choice(self.colors)
            tree.add(tuple(point))

        for point, color in self.fill_and_blur(all_points, tree):
            self.canvas[point] = color
            tree.add(tuple(point))

    def fill_and_blur(self, all_points, tree):
        for point in all_points:
            close_points = self.closest_points(tree, point, 3)
            yield point, php.average_color(self.weighted_points(close_points))

    def closest_points(self, tree, point, consider):
        return [(dist, node.data) for node, dist in tree.search_knn(tuple(point), consider)]

    def weighted_points(self, points):
        greatest_distance = max(dist for dist, _ in points)

        weighted = []

        for dist, point in points:
            if dist == 0:
                weighted.append(self.canvas[point])
            else:
                weighted.extend([self.canvas[point]] * int(greatest_distance / dist))

        return weighted


class ApplyTheme:
    """
    Apply a theme to your devices.

    Usage looks like:

    .. code-block:: python

        options = {"colors": [<color>, <color>, ...]}
        await target.send(ApplyTheme.msg(options))

    The options available are:

    colors
        A list of color specifiers

    duration
        How long the transition takes. Defaults to 1 second

    power_on
        Whether to also power on devices. Defaults to true

    overrides
        A dictionary of ``{"hue": 0-360, "saturation": 0-1, "brightness": 0-1, "kelvin": 2500-9000}``

        Where each property is optional and will override any color set in the theme.
    """

    @classmethod
    def msg(kls, options):
        if not isinstance(options, Options):
            options = Options.FieldSpec().normalise(Meta(options, []), options)

        async def gen(reference, sender, **kwargs):
            serials = []
            canvases = []
            combined_canvas = Canvas()

            plans = sender.make_plans("parts")
            async for serial, _, info in sender.gatherer.gather(plans, reference, **kwargs):
                serials.append(serial)
                for part in info:
                    if part.device.cap.has_chain:
                        combined_canvas.add_parts(part)
                    else:
                        nxt = Canvas()
                        nxt.add_parts(part)
                        canvases.append(nxt)

            if combined_canvas:
                canvases.append(combined_canvas)

            msgs = []

            if options.power_on:
                for serial in serials:
                    msgs.append(
                        LightMessages.SetLightPower(
                            level=65535,
                            duration=options.duration,
                            target=serial,
                            res_required=False,
                        )
                    )

            for canvas in canvases:
                Applier(canvas, options.colors).apply()

                for msg in canvas.msgs(
                    options.override_layer, duration=options.duration, acks=True
                ):
                    msgs.append(msg)

            yield msgs

        return FromGenerator(gen)
