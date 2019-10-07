from textwrap import dedent


class Character:
    colors = {}

    def __init__(self, char):
        self.char = dedent(char).strip()

    @property
    def width(self):
        return len(self.char.split("\n")[0])

    @property
    def height(self):
        return len(self.char.split("\n"))

    def get_color_func(self, fill_color):
        pixels = self.char.split("\n")

        def get_color(x, y):
            pixel = pixels[y][x]
            if pixel == "#":
                return fill_color
            elif pixel in self.colors:
                return self.colors[pixel]

        return get_color


def Space(width, height=8):
    rows = []
    for _ in range(height):
        rows.append("_" * width)
    return Character("\n".join(rows))
