"""
The appliers here are for randomly distributing the theme to the device.

.. autoclass:: photons_themes.appliers.splotch.StripApplierSplotch

.. autoclass:: photons_themes.appliers.splotch.TileApplierSplotch
"""
from photons_themes.collections import ZoneColors, TileColors
from photons_themes.canvas import Canvas, color_weighting
from photons_themes.appliers.base import TileApplier
from photons_themes.theme import ThemeColor

class StripApplierSplotch:
    """
    Apply a theme to a multizone device::

        applier = StripApplier(num_zones)
        for (start_index, end_index), color in applier.apply_theme(theme):
            ...

    .. automethod:: apply_theme
    """
    def __init__(self, number_zones):
        self.number_zones = number_zones

    def apply_theme(self, theme):
        """
        Divide and conquer the zones on the strip with our colours such that we
        blend from one colour to the next along the length of the strip.

        To make the application different each time, we first create a shuffled
        version of the theme which we then use.
        """
        colors = ZoneColors()
        theme = theme.shuffled()
        theme.ensure_color()
        colors.apply_theme(theme, self.number_zones)
        return colors.colors

class TileApplierSplotch(TileApplier):
    """
    Used to apply a random distribution of colors on a 2d device (i.e. the Tile)::

        coords_and_sizes = [((t.user_x, t.user_y), (t.width, t.height)) for t in chain]

        applier = TileApplier.from_user_coords(coords_and_sizes)

        for i, colors in enumerate(applier.apply_theme(theme)):
            # Apply colors to tile index i

    coords_and_sizes
        A list of ``((left_x, top_y), (width, height))`` representing the top
        left corner of each tile in the chain.

        Note that if you have ``((user_x, user_y), (width, height))`` values from
        asking a tile for it's device chain, then use the ``from_user_coords``
        classmethod to create a TileApplier from that data.

    just_points
        Part of the algorithm generates random points on the canvas followed by
        filling in the gaps between those points. By setting this option to True
        we won't fill in the gaps

    post_blur
        By setting this to false we won't blur the points after the gaps are
        filled in.

    .. automethod:: from_user_coords

    .. automethod:: apply_theme
    """
    def __init__(self, coords_and_sizes, just_points=False, post_blur=True):
        super(TileApplierSplotch, self).__init__(coords_and_sizes)

        self.post_blur = post_blur
        self.just_points = just_points

    def apply_theme(self, theme, return_canvas=False, canvas=None):
        """
        If a canvas is not supplied then we create a new canvas with random points
        around where each tile is. We then shuffle those points and blur them
        a little.

        We then fill in the gaps between the points.

        Then we blur the filled in points and create the 64 hsbk values for each
        tile.

        We return the list of ``[<64 hsbks>, <64 hsbks>, ...]``.

        If ``return_canvas`` is True then we return a tuple of ``(tiles, canvas)``
        """
        if canvas is None:
            canvas = Canvas()
            theme = theme.shuffled()
            theme.ensure_color()

            for (left_x, top_y), (w, h) in self.coords_and_sizes:
                canvas.add_points_for_tile(left_x, top_y, w, h, theme)
            canvas.shuffle_points()
            canvas.blur_by_distance()

        colors = TileColors()
        tile_canvas = Canvas()

        for (left_x, top_y), (tile_width, tile_height) in self.coords_and_sizes:
            if self.just_points:
                colors.add_tile(canvas.points_for_tile(left_x, top_y, tile_width, tile_height))
            else:
                tile_canvas.fill_in_points(canvas, left_x, top_y, tile_width, tile_height)

        if not self.just_points:
            if self.post_blur:
                tile_canvas.blur()

            self.add_tiles_from_canvas(colors, tile_canvas)

        if return_canvas:
            return colors.tiles, canvas

        return colors.tiles

