"""
The canvas is class for storing the 2d grid of colours for tiles. The canvas is
usually the colours across multiple tiles and then the TileApplier is able to
extract each tile from the canvas

.. autoclass:: photons_themes.canvas.Canvas
    :members:
"""
from photons_themes.theme import ThemeColor

import operator
import random

def color_weighting(distances):
    """
    Return an array of colors where there is more of a color the closest it is.

    distances
        An array of ``(distance, color)`` where distance is a number representing
        how far away the color is.
    """
    if not distances:
        return

    greatest_distance = max(dist for dist, _ in distances)

    for dist, color in distances:
        if dist == 0:
            for _ in range(int(greatest_distance)):
                yield color
        else:
            for _ in range(int(greatest_distance / dist)):
                yield color

def shuffle_point(i, j):
    """
    Return a new (i, j) value that is the current (i, j) value plus or minus
    a random amount
    """
    newX = random.randint(i - 3, i + 3)
    newY = random.randint(j - 3, j + 3)
    return newX, newY

class Canvas:
    """
    This is just a collection of points with methods for interacting with those
    points.

    The points are stored as (i, j) in a dictionary. Ideally the points values
    are ``photons_themes.theme.ThemeColor`` objects.
    """
    def __init__(self):
        self.points = {}
        self.color_func = None
        self.default_color_func = None

    def set_color_func(self, color_func):
        """
        Add a color func to the canvas

        This will override any points that are on the canvas
        on getting those points.
        """
        self.color_func = color_func

    def set_default_color_func(self, default_color_func):
        """
        Add a default color func to the canvas

        This will be used when getting points on the canvas that aren't filled.
        """
        self.default_color_func = default_color_func

    @property
    def width(self):
        """
        The distance between the left most x value in the points and the right
        most x value.
        """
        if not self.points:
            return 0
        return int(self.max_x - self.min_x + 1)

    @property
    def height(self):
        """
        The distance between the left most y value in the points and the right
        most y value.
        """
        if not self.points:
            return 0
        return int(self.max_y - self.min_y + 1)

    @property
    def center(self):
        if not self.points:
            return (0, 0)
        return (int(self.width / 2) + self.min_x, int(self.height / 2) + self.min_y)

    @property
    def max_x(self):
        if not self.points:
            return 0
        return max([x for (x, y) in self.points])

    @property
    def min_x(self):
        if not self.points:
            return 0
        return min([x for (x, y) in self.points])

    @property
    def max_y(self):
        if not self.points:
            return 0
        return max([y for (x, y) in self.points])

    @property
    def min_y(self):
        if not self.points:
            return 0
        return min([y for (x, y) in self.points])

    def set_all_points_for_tile(self, left_x, top_y, tile_width, tile_height, get_color):
        """
        Translates x, y points relative to a single tile to the tile position on the canvas

        So let's say a tile is at (10, 2) then get_color will be called with (x, y) from
        0 to tile_width, 0 to tile_height and those points get translated to start from (10, 2)

        NOTE: get_color gets y where higher y means moving down, whereas the coordinates on the canvas
            is higher y means moving up.

        So let's say you have a 4 by 4 tile, get_color will be called with the following points:

        .. code-block:: none

            (0, 0) (1, 0) (2, 0) (3, 0)
            (0, 1) (1, 1) (2, 1) (3, 1)
            (0, 2) (1, 2) (2, 2) (3, 2)
            (0, 3) (1, 3) (2, 3) (3, 3)

        And if you have left_x, top_y of (10, 4), it'll set the following points on the canvas:

        .. code-block:: none

            (10, 4) (11, 4) (12, 4) (13, 4)
            (10, 3) (11, 3) (12, 3) (13, 3)
            (10, 2) (11, 2) (12, 2) (13, 2)
            (10, 1) (11, 1) (12, 1) (13, 1)

        if get_color returns None, then no point is set for that turn
        """
        for j in range(top_y, top_y - tile_height, -1):
            for i in range(left_x, left_x + tile_width):
                color = get_color(i - left_x, (tile_height - 1) - (j - top_y + tile_height - 1))
                if color is not None:
                    self[(i, j)] = color

    def add_points_for_tile(self, left_x, top_y, tile_width, tile_height, theme):
        """
        Create points on the canvas around where a tile is.

        We create an area that's half the tile width/height beyond the boundary
        of the tile.

        We also spread the points out in a random manner and try to avoid having
        points next to each other.

        Multiple calls to this function will not override existing points on the
        canvas
        """
        from_x = int(left_x - tile_width * 1.5)
        to_x = int(left_x + tile_width * 1.5)
        from_y = int(top_y - tile_height * 1.5)
        to_y = int(top_y + tile_height * 1.5)

        i = from_x
        while i < to_x:
            j = from_y
            while j < to_y:
                if (i, j) not in self.points:
                    if not self.has_neighbour(i, j):
                        self[(i, j)] = theme.random()
                j += random.choice([i + 1 for i in range(3)])
            i += random.choice([i + 1 for i in range(3)])

    def surrounding_colors(self, i, j):
        """
        Return the colors that surround this (i, j) point.

        This will only return points that exist.
        """
        return [self[(x, y)] for x, y in self.surrounding_points(i, j) if (x, y) in self]

    def surrounding_points(self, i, j):
        """Return the co-ordinates that are neighbours of this point"""
        return [
            (i - 1, j + 1)
          , (i    , j + 1)
          , (i + 1, j + 1)
          , (i - 1, j    )
          , (i + 1, j    )
          , (i - 1, j - 1)
          , (i    , j - 1)
          , (i + 1, j - 1)
          ]

    def has_neighbour(self, i, j):
        """Return whether there are any points around this (i, j) position"""
        return any(self.surrounding_colors(i, j))

    def shuffle_points(self):
        """
        Take all the points and move them around a random amount
        """
        new_points = {}
        for (i, j), color in self.points.items():
            new_points[shuffle_point(i, j)] = color

        self.points = new_points

    def blur(self):
        """
        For each point, find the average colour of that point plus all surrounding
        points.
        """
        new_points = {}
        for (i, j), original in self:
            colors = [original for _ in range(2)]
            for color in self.surrounding_colors(i, j):
                colors.append(color)
            new_points[(i, j)] = ThemeColor.average(colors)
        self.points = new_points

    def blur_by_distance(self):
        """
        Similar to blur but will find the 8 closest points as opposed to the 8
        surrounding points.
        """
        new_points = {}
        for (i, j), original in self:
            distances = self.closest_points(i, j, 8)
            weighted = list(color_weighting(distances))
            new_points[(i, j)] = ThemeColor.average(weighted)
        self.points = new_points

    def points_for_tile(self, left_x, top_y, tile_width, tile_height):
        """
        Return a list of 64 hsbk values for this tile

        For any point on the tile that doesn't have a corresponding point on the
        canvas return a grey value. This is useful for when we tell the applier
        to not fill in the gaps.
        """
        result = []
        grey = ThemeColor(0, 0, 0.3, 3500)

        for j in range(top_y, top_y - tile_height, -1):
            for i in range(left_x, left_x + tile_width):
                result.append(self.get((i, j), grey))

        return result

    def fill_in_points(self, canvas, left_x, top_y, tile_width, tile_height):
        """
        Fill in the gaps on this canvas by blurring the points on the provided
        canvas around where our tile is.

        We blur by finding the 4 closest points for each point on our tile and
        averaging them.
        """
        for j in range(top_y, top_y - tile_height, -1):
            for i in range(left_x, left_x + tile_width):
                distances = canvas.closest_points(i, j, 4)
                weighted = list(color_weighting(distances))
                self[(i, j)] = ThemeColor.average(weighted)

    def closest_points(self, i, j, consider):
        """
        Return ``[(distance, color), ...]`` for ``consider`` closest points to (i, j)
        """
        distances = []

        for (x, y), color in self:
            distances.append(((x - i) ** 2 + (y - j) ** 2, color))

        def get_key(dc):
            return (dc[0], (dc[1].hue, dc[1].saturation, dc[1].brightness, dc[1].kelvin))
        distances = sorted(distances, key=get_key)
        return distances[:consider]

    def __iter__(self):
        """Yield ``((i, j), color)`` pairs for all our points"""
        for pair in self.points.items():
            yield pair

    def __len__(self):
        """Return how many points are in the canvas"""
        return len(self.points)

    def get(self, point, dflt=None):
        """
        Get a point or the passed in ``dflt`` value if the point doesn't exist

        If this canvas has a default_color_func then dflt is ignored and the
        default_color_func is used instead
        """
        if self.color_func:
            return self.color_func(*point)
        if point not in self.points and self.default_color_func:
            return self.default_color_func(*point)
        return self.points.get(point, dflt)

    def __getitem__(self, point):
        """Return the color at ``point`` where ``point`` is ``(i, j)``"""
        if self.color_func:
            return self.color_func(*point)
        if point not in self.points and self.default_color_func:
            return self.default_color_func(*point)
        return self.points[point]

    def __setitem__(self, key, color):
        """Set the color at ``point`` where ``point`` is ``(i, j)``"""
        self.points[key] = color

    def __delitem__(self, key):
        """Remove a key from our points"""
        del self.points[key]

    def __contains__(self, point):
        """Return whether this ``point`` has a color where ``point`` is ``(i, j)``"""
        return point in self.points
