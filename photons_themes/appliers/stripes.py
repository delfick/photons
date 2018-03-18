"""
These appliers generate colors for each point using a function

.. autoclass:: photons_themes.appliers.stripes.TileApplierVerticalStripe

.. autoclass:: photons_themes.appliers.stripes.TileApplierHorizontalStripe

.. autoclass:: photons_themes.appliers.stripes.TileApplierDownDiagnoalStripe

.. autoclass:: photons_themes.appliers.stripes.TileApplierUpDiagnoalStripe

.. autoclass:: photons_themes.appliers.stripes.TileApplierSquareStripe
"""
from photons_themes.appliers.base import TileApplierPattern

import math

class TileApplierVerticalStripe(TileApplierPattern):
    """
    Used to apply a vertical stripe to the tiles in a chain
    """
    def color_func_generator(self, theme, canvas):
        colors = self.make_colors(theme)

        def get_color(i, j):
            item = i % len(colors)
            return colors[item]
        return get_color

class TileApplierHorizontalStripe(TileApplierPattern):
    """
    Used to apply a horizontal stripe to the tiles in a chain
    """
    def color_func_generator(self, theme, canvas):
        colors = self.make_colors(theme)

        def get_color(i, j):
            item = j % len(colors)
            return colors[item]
        return get_color

class TileApplierDownDiagnoalStripe(TileApplierPattern):
    """
    Makes diagonal stripes that go from the top left to the bottom right
    """
    def color_func_generator(self, theme, canvas):
        colors = self.make_colors(theme)

        def get_color(i, j):
            return colors[(i + j) % len(colors)]
        return get_color

class TileApplierUpDiagnoalStripe(TileApplierPattern):
    """
    Makes diagonal stripes that go from the bottom left to the top right
    """
    def color_func_generator(self, theme, canvas):
        colors = self.make_colors(theme)

        def get_color(i, j):
            return colors[(i - j) % len(colors)]
        return get_color

class TileApplierSquareStripe(TileApplierPattern):
    """
    Makes progressively bigger squares from the center point on the canvas
    """
    def color_func_generator(self, theme, canvas):
        colors = self.make_colors(theme, multiplier=1)
        center = canvas.center

        def get_color(i, j):
            distance = max(abs(center[0] - i), abs(center[1] - j))
            return colors[distance % len(colors)]
        return get_color
