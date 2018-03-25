from photons_tile_paint.animation import Animation, coords_for_horizontal_line, put_characters_on_canvas
from photons_tile_paint.font.alphabet import characters as alphabet

from photons_themes.canvas import Canvas

import time

class TileTimeAnimation(Animation):
    every = 1.5
    duration = 1
    coords = coords_for_horizontal_line

    class State:
        def __init__(self, time_string, second):
            self.time_string = time_string
            self.second = second

    def next_state(self, prev_state, coords):
        localtime = time.localtime(time.time())
        second = localtime.tm_sec
        minute = localtime.tm_min
        hour = localtime.tm_hour
        if not self.options.hour24 and (hour > 12):
            hour = hour - 12
        if not self.options.hour24 and hour == 0:
            hour = 12

        return self.State("{:02d}:{:02d}".format(hour, minute), second)

    def make_canvas(self, state, coords):
        canvas = Canvas()

        line_length = (8 * 5) * (state.second / 60)
        (user_x, user_y), (width, height) = coords[0]
        if not self.options.full_height_progress:
            user_y  = user_y - height + 1
            height = 1

        def get_color(x, y):
            if x < line_length:
                return self.options.progress_bar_color.color
        canvas.set_all_points_for_tile(user_x, user_y, width * 5, height, get_color)

        time_characters = [alphabet[ch] for ch in list(state.time_string)]
        put_characters_on_canvas(canvas, time_characters, coords, self.options.number_color.color)
        return canvas
