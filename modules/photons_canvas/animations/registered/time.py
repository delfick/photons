from photons_canvas.animations import options, Animation, an_animation
from photons_canvas import font, point_helpers as php

from delfick_project.norms import dictobj, sb
import time
import math


class Options(dictobj.Spec):
    hour24 = dictobj.Field(sb.boolean, default=True)
    ignore_coordinates = dictobj.Field(sb.boolean, default=False)

    progress_times = dictobj.Field(sb.integer_spec, default=8)
    number_color_range = dictobj.Field(options.color_range_spec("0,0,0.8,6000"))
    progress_color_range = dictobj.Field(options.color_range_spec("0-360,1,0.2,3500"))


class Divider(font.Character):
    def __init__(self, percent, height, color):
        width = 8
        cols = math.ceil(width * percent)
        rows = math.ceil(height * percent)

        self.colors["%"] = color
        row = (["%"] * cols) + (["_"] * (width - cols))
        super().__init__("\n".join(["".join(row) for _ in range(rows)]))


class State:
    def __init__(self, options):
        self.line = None
        self.options = options
        self.time_string = None
        self.dim_side = "right"

    def change_colors(self):
        self.number_color = self.options.number_color_range.color
        self.progress_color = self.options.progress_color_range.color

        self.divider_color = (0, 1, 0.5, 6000)
        self.divider_color = ((self.progress_color[0] - 110) % 360, *self.divider_color[1:])

        self.step = self.progress_color[2] / self.options.progress_times
        self.seconds_per_line = 60 / self.options.progress_times

    def character_left(self, chars, canvas):
        (left_x, _), (top_y, _), (width, _) = canvas.bounds
        width_diff = width - chars.width
        left = left_x
        if width_diff > 0:
            left += int(width_diff / 2)

        prev_right = None
        right = left + chars.width

        for bounds in reversed(sorted([p.bounds for p in canvas.parts], key=lambda b: b[0][1])):
            (left_x, right_x), _, (width, _) = bounds
            if right > right_x:
                if prev_right:
                    left = prev_right - chars.width
                break
            prev_right = right_x

        return left

    def next_layer(self, canvas):
        (left_x, _), (top_y, _), (width, height) = canvas.bounds

        second, time_string, chars = self.make_time(height)
        chars_layer = chars.layer(self.character_left(chars, canvas), top_y, self.number_color)

        line = int(self.options.progress_times - ((60 - second) / self.seconds_per_line))
        if line != self.line:
            self.dim_side = "left" if self.dim_side == "right" else "right"
        self.line = line

        percent = (second % self.seconds_per_line) / self.seconds_per_line
        position = left_x + (width * percent)
        upto = math.floor(position)

        next_c = self.progress_color
        prev_c = (next_c[0], next_c[1], 0.01, next_c[3])
        tip_c = php.average_color([next_c, prev_c])

        self.time_string = time_string

        def layer(point, canvas):
            ch = chars_layer(point, canvas)
            if ch:
                return ch

            _, rr = php.Points.relative(point, canvas.bounds)

            if point[0] == upto:
                return php.average_color([tip_c, canvas[point]])

            if self.dim_side == "right" and point[0] > upto:
                return prev_c

            if self.dim_side == "left" and point[0] < upto:
                return prev_c

            return php.average_color([next_c, canvas[point]])

        return layer

    def make_time(self, height):
        now = time.time()
        localtime = time.localtime(time.time())
        second = localtime.tm_sec + (now - int(now))
        minute = localtime.tm_min
        hour = localtime.tm_hour
        if not self.options.hour24 and (hour > 12):
            hour = hour - 12
        if not self.options.hour24 and hour == 0:
            hour = 12

        time_string = f"{hour:02d}:{minute:02d}"

        if self.time_string is None or time_string != self.time_string:
            self.change_colors()
            self.time_string = time_string

        chs = [font.alphabet_8[ch] for ch in list(time_string)]
        chs[2] = Divider(second / 60, height, self.divider_color)
        chars = font.Characters(*chs)
        return second, time_string, chars


@an_animation("time", Options)
class TileTimeAnimation(Animation):
    """Print time to the tiles"""

    align_parts_vertically = True

    def setup(self):
        self.original_every = self.every
        self.original_duration = self.duration

        if self.options.ignore_coordinates:
            self.align_parts_straight = True
            self.align_parts_vertically = False

    async def process_event(self, event):
        if not event.state:
            event.state = State(self.options)

        if not event.is_tick:
            return

        return event.state.next_layer(event.canvas)
