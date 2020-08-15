from photons_canvas.points import helpers as php

from textwrap import dedent


def Space(width):
    return Character("_" * width)


class Character:
    colors = {}

    def __init__(self, char, colors=None):
        if colors is not None:
            self.colors = colors

        char = dedent(char).strip()
        self.rows = char.split("\n")

        self.pixels = []
        for row in self.rows:
            self.pixels.extend(row)

        self.width = max([0, *[len(r) for r in self.rows]])
        self.height = len(self.rows)

    def pairs(self, left_x, top_y, fill_color):
        top_y = round(top_y)
        left_x = round(left_x)

        bounds = (
            (left_x, left_x + self.width),
            (top_y, top_y - self.height),
            (self.width, self.height),
        )

        for point, pixel in zip(php.Points.all_points(bounds), self.pixels):
            if pixel == "#":
                pixel = fill_color
            elif pixel in self.colors:
                pixel = self.colors[pixel]
            else:
                pixel = None

            yield point, pixel

    def layer(self, left_x, top_y, fill_color):
        by_point = dict(self.pairs(left_x, top_y, fill_color))

        def lay(point, canvas):
            return by_point.get(point)

        return lay


class Characters:
    def __init__(self, *characters):
        self.characters = list(characters)
        self.width = sum(ch.width for ch in self.characters)

    def pairs(self, left_x, top_y, fill_color):
        top_y = round(top_y)
        left_x = round(left_x)

        for character in self.characters:
            for point, pixel in character.pairs(left_x, top_y, fill_color):
                yield point, pixel

            left_x += character.width

    def layer(self, left_x, top_y, fill_color):
        by_point = dict(self.pairs(left_x, top_y, fill_color))

        def lay(point, canvas):
            return by_point.get(point)

        return lay
