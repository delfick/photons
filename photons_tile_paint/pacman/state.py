from photons_tile_paint.pacman import font

def start(coords):
    return L2RState(0, 0, 0).swap_state(coords)

class State:
    def coords_for(self, original):
        coords = []

        (_, top_y), (_, height) = original[0]
        left_x = self.x

        for char in self.characters:
            coords.append(((left_x, top_y), (char.width, height)))
            left_x += char.width

        return coords

    @property
    def length(self):
        return sum(char.width for char in self.characters)

class R2LState(State):
    def __init__(self, start_x, end_x, x):
        self.x = x
        self.end_x = end_x
        self.start_x = start_x

    @property
    def characters(self):
        return [
              self.pacman
            , font.Space(2)
            , font.Blinky
            , font.Space(2)
            , font.Pinky
            , font.Space(2)
            , font.Inky
            , font.Space(2)
            , font.Clyde
            ]

    @property
    def pacman(self):
        if self.x % 4 < 2:
            return font.PacmanR2LOpen
        else:
            return font.PacmanClosed

    def move(self, amount):
        return self.__class__(self.start_x, self.end_x, self.x - amount)

    @property
    def finished(self):
        return self.x == self.end_x

    def swap_state(self, coords):
        (left_x, _), _ = sorted(coords)[0]
        left_x -= self.length

        (right_x, _), (width, _) = sorted(coords)[-1]
        right_x += width
        return L2RState(left_x, right_x, left_x)

class L2RState(State):
    def __init__(self, start_x, end_x, x):
        self.x = x
        self.end_x = end_x
        self.start_x = start_x

    @property
    def characters(self):
        return [
              self.pacman
            , font.Space(2)
            , font.Ghost
            , font.Space(2)
            , font.Ghost
            , font.Space(2)
            , font.Ghost
            , font.Space(2)
            , font.Ghost
            ]

    @property
    def pacman(self):
        if self.x % 4 < 2:
            return font.PacmanL2ROpen
        else:
            return font.PacmanClosed

    def move(self, amount):
        return self.__class__(self.start_x, self.end_x, self.x + amount)

    @property
    def finished(self):
        return self.x == self.end_x

    def swap_state(self, coords):
        (right_x, _), (width, _) = sorted(coords)[-1]
        right_x += width

        (left_x, _), _ = sorted(coords)[0]
        left_x -= self.length

        return R2LState(right_x, left_x, right_x)
