"""
We have classes for storing the final colours for multi color devices.

.. autoclass:: photons_themes.collections.ZoneColors
    :members:

.. autoclass:: photons_themes.collections.TileColors
    :members:
"""
from photons_themes.theme import ThemeColor

class ZoneColors:
    """
    Representation of colors on a zone
    """
    def __init__(self):
        self._colors = []

    def add_hsbk(self, hsbk):
        """
        Add a ThemeColor instance

        The idea is you use this function to add each zone in order.
        """
        self._colors.append(hsbk)

    def apply_to_range(self, color, next_color, length):
        """
        Recursively apply two colours to our strip such that we blend between
        the two colours.
        """
        if length == 1:
            self.add_hsbk(color)

        elif length == 2:
            second_color = ThemeColor.average([next_color.limit_distance_to(color), color])

            self.add_hsbk(color)
            self.add_hsbk(second_color)

        else:
            average = ThemeColor.average([next_color, color])
            self.apply_to_range(color, average, length // 2)
            self.apply_to_range(average, next_color, length - length // 2)

    def apply_theme(self, theme, zone_count):
        """Apply a theme across zone_count zones"""
        i = 0
        location = 0
        zones_per_color = max(1, int(zone_count / (max(len(theme) - 1, 1))))

        while location < zone_count:
            length = min(location + zones_per_color, zone_count) - location
            self.apply_to_range(theme[i], theme.get_next_bounds_checked(i), length)
            i = min(len(theme) - 1, i + 1)
            location += zones_per_color

    @property
    def colors(self):
        """
        Return a list of ``((start_index, end_index), hsbk)`` for our colors.

        This function will make sure that contiguous colors are returned with
        an appropriate ``start_index``, ``end_index`` range.
        """
        start_index = 0
        end_index = -1
        current = None
        result = []

        for hsbk in self._colors:
            if current is not None and current != hsbk:
                result.append(((start_index, end_index), current))
                start_index = end_index + 1

            end_index += 1
            current = hsbk

        result.append(((start_index, end_index), current))
        return result

class TileColors:
    """
    A very simple wrapper around multiple tiles
    """
    def __init__(self):
        self.tiles = []

    def add_tile(self, hsbks):
        """Add a list of 64 ThemeColor objects to represent the next tile"""
        self.tiles.append(hsbks)
