from photons_tile_paint.gameoflife.font import characters

from photons_themes.theme import ThemeColor as Color
from photons_themes.canvas import Canvas

import random
import time

class State:
    def __init__(self, coords, make_new_color):
        self.coords = coords
        self.canvas = Canvas()
        self.last_random = time.time()
        self.last_iteration = None
        self.make_new_color = make_new_color

        self.left = coords[0][0][0]
        self.right = coords[0][0][0]
        self.top = coords[0][0][1]
        self.bottom = coords[0][0][1]

        for (left, top), (width, height) in coords:
            self.left = min(left, self.left)
            self.right = max(left + width, self.right)
            self.top = min(top, self.top)
            self.bottom = max(top + height, self.bottom)

        self.width = self.right - self.left
        self.height = self.bottom - self.top

        self.place_random(4)

    def place_random(self, amount):
        for _ in range(amount):
            ch = random.choice(characters)
            left, top = self.random_coord()
            color = Color(random.randrange(0, 360), 1, 1, 3500)
            self.canvas.set_all_points_for_tile(left, top, ch.width, ch.height, ch.get_color_func(color))

    def iterate(self, delay):
        if self.last_iteration is not None and time.time() - self.last_iteration < delay:
            return self

        now = time.time()
        self.last_iteration = now

        if now - self.last_random > 1:
            self.place_random(random.randrange(0, 3))
            self.last_random = now

        removal = []
        addition = []

        points = [c for c, _ in self.canvas]
        dead_points = []
        for i, j in points:
            dead_points.extend([p for p in self.canvas.surrounding_points(i, j)])

        points.extend(dead_points)

        for point in set(points):
            alive = point in self.canvas
            alive_neighbours = len(self.canvas.surrounding_colors(*point))

            if alive:
                if alive_neighbours < 2 or alive_neighbours > 3:
                    removal.append(point)
            else:
                if alive_neighbours == 3:
                    addition.append(point)

        for point in removal:
            del self.canvas[point]

        for point in addition:
            color = self.make_new_color(self.canvas.surrounding_colors(*point))
            self.canvas[point] = color

        for (left, top), _ in list(self.canvas):
            too_far_left = left < self.left - 20
            too_far_right = left > self.right + 20
            too_far_up = top < self.top - 20
            too_far_down = top > self.bottom + 20
            if too_far_left or too_far_right or too_far_up or too_far_down:
                del self.canvas[(left, top)]

        return self

    def random_coord(self):
        left = random.randrange(self.left, self.right)
        top = random.randrange(self.top, self.bottom)
        return left, top
