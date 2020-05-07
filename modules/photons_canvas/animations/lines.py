from photons_canvas import point_helpers as php
from photons_canvas.animations import options

from delfick_project.norms import dictobj, sb
import math


def clamp(val, mn=0, mx=1):
    if val < mn:
        return mn
    elif val > mx:
        return mx
    return val


class LineOptions(dictobj.Spec):
    rate = dictobj.Field(options.range_spec((0.2, 0.4), rate=True))
    line_hues = dictobj.Field(options.color_range_spec("rainbow"))
    fade_amount = dictobj.Field(sb.float_spec, default=0.1)

    def make_line(self, length):
        return Line(length, self.line_hues.color)


class Line:
    def __init__(self, length, color1):
        self.color1 = color1
        self.length = length

        self.tip = []
        self.position = 0
        self.body_pixels = [color1 for _ in range(length)]

    def progress(self, rate):
        self.position += rate

        brightness = clamp(1 - (self.position - math.floor(self.position)))
        if brightness <= 0:
            self.tip = []
        else:
            self.tip = [php.Color.adjust(self.color1, brightness_change=(brightness,))]

    def pixels(self, start, reverse=False, tail=None):
        start = start + math.floor(self.position)

        pixels = self.body_pixels + self.tip
        if reverse:
            pixels = reversed(pixels)

        for _ in range(tail or 0):
            yield start, None
            start += 1

        for pixel in pixels:
            yield start, pixel
            start += 1
