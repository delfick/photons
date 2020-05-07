from photons_canvas import point_helpers as php
from photons_app import helpers as hp

import itertools
import asyncio
import random


class Black:
    pass


class PixelBrightness:
    def __init__(self, original):
        self.change = 0.1
        self.original = original[2]
        self.direction = -1

        self.returning = False
        self.in_progress = True

        self.return_handle = None

    def finish(self):
        self.return_handle = asyncio.get_event_loop().call_later(
            0.5, lambda: setattr(self, "returning", True)
        )

    def ensure(self):
        if hasattr(self, "return_handle"):
            self.return_handle.cancel()

        self.returning = False

    @property
    def has_change(self):
        return self.in_progress

    def progress(self, color):
        if not self.in_progress:
            return color

        h, s, b, k = color or php.Color.ZERO

        self.change += 0.1 * self.direction
        if self.change > 1 or self.change < 0:
            self.direction *= -1

        b = self.original * (1 - self.change)
        if b < 0:
            b = 0
        if b > 1:
            b = 1

        if self.returning and abs(self.original - b) <= 0.1:
            self.in_progress = False
            return h, s, self.original, k
        else:
            return h, s, b, k


class PatternLayer:
    def __init__(self, part, pattern, options):
        self.part = part
        self.pattern = pattern
        self.options = options

        self.highlight_row = None
        self.brightness_change = None

        self.started = False

    @property
    def has_change(self):
        return (
            not self.started or self.brightness_change is not None or self.highlight_row is not None
        )

    @hp.memoized_property
    def pattern_canvas(self):
        canvas = {}
        bounds = self.part.bounds
        self.pattern(canvas, bounds, *self.options)

        _, (_, bottom), _ = bounds
        for point in php.Points.row(bottom + 1, bounds):
            canvas[point] = (0, 0, 1, 3500)

        return canvas

    @property
    def layer(self):
        self.started = True

        bounds = self.part.bounds
        _, (top, bottom), _ = bounds

        show_rows = None
        if self.highlight_row is not None:
            direction, row = self.highlight_row
            rows = list(range(bottom, row))
            if direction > 0:
                show_rows = rows
            else:
                show_rows = [row for _, row in php.Points.col(0, bounds) if row not in rows]

        pattern = self.pattern_canvas

        def pattern_layer(point, canvas):
            col, row = point
            if show_rows is not None and row not in show_rows:
                return php.Color.ZERO

            return pattern.get(point)

        def layer(point, canvas):
            parts = canvas.point_to_parts[point]
            if self.part not in parts:
                return

            c = pattern_layer(point, canvas)
            if self.brightness_change is not None:
                if point not in self.brightness_change:
                    self.brightness_change[point] = PixelBrightness(c)
                return self.brightness_change[point].progress(c)
            else:
                return c

        return layer

    def start_highlight(self):
        self.highlight_row = (-1, self.part.bounds[1][1] - 1)

    def is_changing(self):
        if self.brightness_change:
            for b in self.brightness_change.values():
                b.ensure()
        else:
            self.brightness_change = {}

    def changed(self):
        if self.brightness_change is not None:
            for b in self.brightness_change.values():
                b.finish()

    def progress(self):
        if self.highlight_row is not None:
            direction, row = self.highlight_row
            _, (top, bottom), _ = self.part.bounds

            if direction > 0 and row > top:
                self.highlight_row = None

            elif direction < 1 and row > top:
                self.highlight_row = (1, bottom)

            else:
                self.highlight_row = direction, row + 1

        if self.brightness_change is not None:
            if self.brightness_change and not any(
                b.has_change for b in self.brightness_change.values()
            ):
                self.brightness_change = None


class Patterns:
    def __init__(self):
        self.styles = iter(self.compute_styles())

    def make_color(self, hue, dim=False):
        if hue in (None, Black):
            c = (0, 0, 0, 3500)
        else:
            c = (hue, 1, 0.5, 3500)

        if c[1] == 1:
            if not dim:
                c = (c[0], c[1], 1, c[2])
            else:
                c = (c[0], c[1], dim, c[2])

        return c

    def make(self, part):
        typ, options = next(self.styles)
        return PatternLayer(part, getattr(self, f"set_{typ}"), options)

    def compute_styles(self):
        colors = [0, 50, 100, 180, 250, 300]
        options = list(self.options(colors))
        random.shuffle(options)

        os = iter(itertools.cycle(options))

        while True:
            nxt = next(os)
            for sp in nxt:
                yield sp

    def options(self, colors):
        shifted = colors[2:] + colors[:2]

        yield [("color", (color,)) for color in colors]
        yield [("split", (color,)) for color in colors]

        for attr in ("x", "cross", "dot", "hourglass"):
            yield [(attr, (color,)) for color in colors]
            if attr != "x":
                if attr != "dot":
                    yield [(attr, (Black, color)) for color in colors]
                yield [(attr, (h1, h2)) for h1, h2 in zip(colors, shifted)]

    def set_color(self, canvas, bounds, hue):
        for point in php.Points.all_points(bounds):
            canvas[point] = self.make_color(hue, dim=0.5)

    def set_split(self, canvas, bounds, hue):
        (left_x, _), (top_y, _), (width, height) = bounds

        for (col, row) in php.Points.all_points(bounds):
            h = Black
            if col > left_x + width / 2:
                h = hue

            canvas[(col, row)] = self.make_color(h, dim=0.5)

    def quadrants(self, canvas, bounds):
        """
        Split the part into quadrants and return information such that if you
        fill out one quadrant, the others will be the same but mirrored/flipped.

        yields (row, column), set_points

        Where set_points takes in a color to set for all the quadrants
        """
        cols = [col for col, _ in php.Points.row(0, bounds)]
        rows = [row for _, row in php.Points.col(0, bounds)]

        cols_from_left, cols_from_right = (
            cols[len(cols) // 2 :],
            list(reversed(cols[: len(cols) // 2])),
        )

        rows_from_bottom, rows_from_top = (
            rows[len(rows) // 2 :],
            list(reversed(rows[: len(rows) // 2])),
        )

        def make_point_setter(points):
            def set_points(color):
                for point in points:
                    canvas[point] = color

            return set_points

        for col, (left_col, right_col) in enumerate(zip(cols_from_left, cols_from_right)):
            for row, (bottom_row, top_row) in enumerate(zip(rows_from_bottom, rows_from_top)):
                points = [
                    (left_col, top_row),
                    (right_col, top_row),
                    (left_col, bottom_row),
                    (right_col, bottom_row),
                ]

                yield (col, row), make_point_setter(points)

    def set_cross(self, canvas, bounds, hue1, hue2=None):
        def make_color(t):
            h = [hue1, hue2][t]
            return self.make_color(h, dim=0.5 if h is Black or t else False)

        for (row, column), set_points in self.quadrants(canvas, bounds):
            if row == 0 or column == 0:
                set_points(make_color(False))
            else:
                set_points(make_color(True))

    def set_x(self, canvas, bounds, hue1, hue2=None):
        def make_color(t):
            h = [hue1, hue2][t]
            return self.make_color(h, dim=0.5 if h is Black or not t else False)

        for (row, column), set_points in self.quadrants(canvas, bounds):
            s = row * 2 + 2
            if row == s and column == s or column + 1 == row or row + 1 == column:
                set_points(make_color(False))
            else:
                set_points(make_color(True))

    def set_hourglass(self, canvas, bounds, hue1, hue2=None):
        def make_color(t):
            h = [hue1, hue2][t]
            return self.make_color(h, dim=0.3 if h is Black or not t else False)

        for (row, column), set_points in self.quadrants(canvas, bounds):
            s = column * 2 - 2
            if row >= s and column >= s:
                set_points(make_color(False))
            else:
                set_points(make_color(True))

    def set_dot(self, canvas, bounds, hue1, hue2=None):
        def make_color(t):
            h = [hue1, hue2][t]
            return self.make_color(h, dim=0.5 if h is Black or t else False)

        for (row, column), set_points in self.quadrants(canvas, bounds):
            s = row * 2
            if column == s and row >= s:
                set_points(make_color(False))
            else:
                set_points(make_color(True))
