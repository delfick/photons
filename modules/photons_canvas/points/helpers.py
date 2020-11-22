from collections import defaultdict
from functools import wraps
from lru import LRU
import math


BoundCache = defaultdict(lambda: LRU(3000))


class Color:
    ZERO = (0, 0, 0, 0)
    WHITE = (0, 0, 1, 3500)
    EMPTIES = (ZERO, None)

    @classmethod
    def dead(kls, color):
        return color in kls.EMPTIES or color[2] == 0

    @classmethod
    def override(kls, color, hue=None, saturation=None, brightness=None, kelvin=None):
        if hue is None and saturation is None and brightness is None and kelvin is None:
            return color

        hue_change = (hue,) if hue is not None else None
        saturation_change = (saturation,) if saturation is not None else None
        brightness_change = (brightness,) if brightness is not None else None
        kelvin_change = (kelvin,) if kelvin is not None else None

        return kls.adjust(
            color,
            hue_change=hue_change,
            saturation_change=saturation_change,
            brightness_change=brightness_change,
            kelvin_change=kelvin_change,
        )

    @classmethod
    def adjust(
        kls,
        color,
        hue_change=None,
        saturation_change=None,
        brightness_change=None,
        kelvin_change=None,
    ):
        h, s, b, k = color

        if hue_change is not None and isinstance(hue_change, tuple):
            h = hue_change[0]
        elif hue_change:
            h += hue_change

        if saturation_change is not None and isinstance(saturation_change, tuple):
            s = saturation_change[0]
        elif saturation_change:
            s += saturation_change

        if brightness_change is not None and isinstance(brightness_change, tuple):
            b = brightness_change[0]
        elif brightness_change:
            b += brightness_change

        if kelvin_change is not None and isinstance(kelvin_change, tuple):
            k = kelvin_change[0]
        elif kelvin_change:
            k += kelvin_change

        if hue_change:
            if h < 0:
                h = 0
            elif h > 360:
                h = 360

        if saturation_change:
            if s < 0:
                s = 0
            elif s > 1:
                s = 1

        if brightness_change:
            if b < 0:
                b = 0
            elif b > 1:
                b = 1

        if kelvin_change:
            if k < 0:
                k = 0
            elif k > 0xFFFF:
                k = 0xFFFF
            else:
                k = int(k)

        return h, s, b, k


def average_color(colors):
    colors = [c for c in colors if c is not None]

    if not colors:
        return None

    if len(set(colors)) == 1:
        return colors[0]

    hue_x_total = 0
    hue_y_total = 0
    saturation_total = 0
    brightness_total = 0
    kelvin_total = 0

    for color in colors:
        if isinstance(color, tuple):
            h, s, b, k = color
        else:
            h = color.hue
            s = color.saturation
            b = color.brightness
            k = color.kelvin

        hue_x_total += math.sin(h * 2.0 * math.pi / 360)
        hue_y_total += math.cos(h * 2.0 * math.pi / 360)
        saturation_total += s
        brightness_total += b

        if k == 0:
            kelvin_total += 3500
        else:
            kelvin_total += k

    hue = math.atan2(hue_x_total, hue_y_total) / (2.0 * math.pi)
    if hue < 0.0:
        hue += 1.0
    hue *= 360

    number_colors = len(colors)
    saturation = saturation_total / number_colors
    brightness = brightness_total / number_colors
    kelvin = int(kelvin_total / number_colors)

    return (hue, saturation, brightness, kelvin)


def _points_bound_cache(func):
    name = func.__name__

    if name in ("row", "col"):

        @wraps(func)
        def wrapped(kls, *args, **kwargs):
            key = None
            if len(args) == 2:
                key = args

            cached = None
            if key is not None:
                cached = BoundCache[name].get(key)

            if cached is None:
                cached = list(func(kls, *args, **kwargs))
                if key is not None:
                    BoundCache[name][key] = cached

            return cached

    else:

        @wraps(func)
        def wrapped(kls, *args, **kwargs):
            bounds = None
            if len(args) == 1:
                bounds = args[0]

            cached = None
            if bounds is not None:
                cached = BoundCache[name].get(bounds)

            if cached is None:
                result = func(kls, *args, **kwargs)
                if name != "count_points":
                    result = list(result)
                cached = BoundCache[name][bounds] = result

            return cached

    return wrapped


class Points:
    @classmethod
    @_points_bound_cache
    def cols(kls, bounds):
        (l, r), _, _ = bounds
        for col in range(l, r):
            yield kls.col(col, bounds)

    @classmethod
    @_points_bound_cache
    def rows(kls, bounds):
        _, (t, b), _ = bounds
        for row in range(t, b, -1):
            yield kls.row(row, bounds)

    @classmethod
    @_points_bound_cache
    def all_points(kls, bounds):
        for row in kls.rows(bounds):
            yield from row

    @classmethod
    @_points_bound_cache
    def count_points(kls, bounds):
        return sum(len(row) for row in kls.rows(bounds))

    @classmethod
    @_points_bound_cache
    def row(kls, row, bounds):
        (l, r), _, _ = bounds
        return [(col, row) for col in range(l, r)]

    @classmethod
    @_points_bound_cache
    def col(kls, col, bounds):
        _, (t, b), _ = bounds
        return [(col, row) for row in range(t, b, -1)]

    @classmethod
    def expand(kls, bounds, amount):
        (l, r), (t, b), (w, h) = bounds
        return (l - amount, r + amount), (t + amount, b - amount), (w + amount * 2, h + amount * 2)

    @classmethod
    def relative(kls, point, bounds):
        (l, _), (t, _), _ = bounds
        return point[0] - l, t - point[1]

    @classmethod
    def bottom_row(kls, bounds):
        _, (_, b), _ = bounds
        return b

    @classmethod
    def top_row(kls, bounds):
        _, (t, _), _ = bounds
        return t
