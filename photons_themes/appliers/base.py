from photons_themes.coords import user_coords_to_pixel_coords
from photons_themes.collections import TileColors, ZoneColors
from photons_themes.theme import ThemeColor
from photons_themes.canvas import Canvas

class TileApplier:
    """
    Base class for applying a theme to a tile
    """
    def __init__(self, coords_and_sizes):
        self.coords_and_sizes = coords_and_sizes

    @classmethod
    def from_user_coords(kls, coords_and_sizes, **kwargs):
        """
        Create a TileApplier from the ``[((user_x, user_y), (width, height)), ...]``
        returned by a GetDeviceChain message.
        """
        normalized = user_coords_to_pixel_coords(coords_and_sizes)
        return kls(normalized, **kwargs)

    def add_tiles_from_canvas(self, colors, canvas):
        """Add hsbks values to our colors given this canvas and our tile coords"""
        for (left_x, top_y), (tile_width, tile_height) in self.coords_and_sizes:
            colors.add_tile(canvas.points_for_tile(left_x, top_y, tile_width, tile_height))

class TileApplierPattern(TileApplier):
    """
    Used to apply a generated pattern to the tiles in a chain

        coords_and_sizes = [((t.user_x, t.user_y), (t.width, t.height)) for t in chain]

        applier = TileApplierVerticalStripe.from_user_coords(coords_and_sizes)

        for i, colors in enumerate(applier.apply_theme(theme)):
            # Apply colors to tile index i

    coords_and_sizes
        A list of ``((left_x, top_y), (width, height))`` representing the top
        left corner of each tile in the chain.

        Note that if you have ``((user_x, user_y), (width, height))`` values from
        asking a tile for it's device chain, then use the ``from_user_coords``
        classmethod to create a TileApplier from that data.

    .. automethod:: from_user_coords

    .. automethod:: apply_theme
    """

    def color_func_generator(self, theme, canvas):
        """
        Hook for generating a function to give to the canvas for generating colors from (i, j) points.

        This function takes in the theme to apply and a canvas that has the top left and bottom right
        points of each tile in the chain.
        """
        raise NotImplementedError("Please subclass this to create a valid applier")

    def apply_theme(self, theme, canvas=None, return_canvas=False):
        """
        If a canvas is not supplied then we create a new canvas with a color
        func that generates a vertical stripe
        """
        if canvas is None:
            canvas = Canvas()

            # We add points for our tiles so that canvas.width and canvas.height still work
            # They won't have any effect on the tiles themselves because the color_func overrides points
            grey = ThemeColor(0, 0, 0.3, 3500)
            for (left_x, top_y), (tile_width, tile_height) in self.coords_and_sizes:
                canvas[(left_x, top_y)] = grey
                canvas[(left_x + tile_width, top_y - tile_height)] = grey

            canvas.set_color_func(self.color_func_generator(theme, canvas))

        colors = TileColors()
        self.add_tiles_from_canvas(colors, canvas)

        if return_canvas:
            return colors.tiles, canvas

        return colors.tiles

    def make_colors(self, theme, multiplier=3):
        """
        Return a list of ThemeColor objects for this theme

        This will make a strip ``multiplier`` times the length of the theme
        and transition between the colors along that strip

        If there are no colors, we return just white
        """
        strip = ZoneColors()
        theme = theme.shuffled()
        theme.ensure_color()
        strip.apply_theme(theme, len(theme) * multiplier)
        return strip._colors
