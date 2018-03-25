from photons_tile_paint.pacman import font

def start(coords):
    return L2RState(0, 0).swap_state(coords)

class State:
    def coords_for(self, original):
        coords = []

        (left_x, top_y), (width, height) = original[0]
        left_x = left_x + self.x

        for char in self.characters:
            coords.append(((left_x, top_y), (char.width, height)))
            left_x += char.width

        return coords

    @property
    def length(self):
        return sum(char.width for char in self.characters)

class R2LState(State):
    def __init__(self, start_x, x):
        self.x = x
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
        return self.__class__(self.start_x, self.x - amount)

    @property
    def finished(self):
        return self.x == self.start_x - self.length * 2

    def swap_state(self, coords):
        (user_x, top_y), (width, height) = coords[0]
        left_x = user_x - self.length
        return L2RState(left_x, left_x)

class L2RState(State):
    def __init__(self, start_x, x):
        self.x = x
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
        return self.__class__(self.start_x, self.x + amount)

    @property
    def finished(self):
        return self.x == self.start_x + self.length * 2

    def swap_state(self, coords):
        right_x = 0
        for (user_x, top_y), (width, height) in coords:
            if user_x + width > right_x:
                right_x = user_x + width
        return R2LState(right_x, right_x)
