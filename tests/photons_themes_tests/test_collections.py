# coding: spec

from photons_themes.collections import ZoneColors, TileColors
from photons_themes.theme import ThemeColor, Theme

from unittest import mock

describe "ZoneColors":
    it "has colors":
        colors = ZoneColors()
        assert colors._colors == []

    it "can add a color":
        colors = ZoneColors()
        colors.add_hsbk(ThemeColor(0, 1, 1, 3500))
        colors.add_hsbk(ThemeColor(100, 1, 1, 3500))
        assert colors._colors == [
            ThemeColor(0, 1, 1, 3500),
            ThemeColor(100, 1, 1, 3500),
        ]

    describe "returning colors":
        it "returns with appropriate start_index, end_index":
            colors = ZoneColors()
            colors.add_hsbk(ThemeColor(0, 1, 1, 3500))
            colors.add_hsbk(ThemeColor(100, 1, 1, 3500))
            colors.add_hsbk(ThemeColor(200, 1, 1, 3500))

            assert colors.colors == [
                ((0, 0), ThemeColor(0, 1, 1, 3500)),
                ((1, 1), ThemeColor(100, 1, 1, 3500)),
                ((2, 2), ThemeColor(200, 1, 1, 3500)),
            ]

        it "groups the same colors together":
            colors = ZoneColors()
            colors.add_hsbk(ThemeColor(0, 1, 1, 3500))
            colors.add_hsbk(ThemeColor(0, 1, 1, 3500))
            colors.add_hsbk(ThemeColor(0, 1, 1, 3500))
            colors.add_hsbk(ThemeColor(100, 1, 1, 3500))
            colors.add_hsbk(ThemeColor(200, 1, 1, 3500))
            colors.add_hsbk(ThemeColor(200, 1, 1, 3500))
            colors.add_hsbk(ThemeColor(100, 1, 1, 3500))

            assert colors.colors == [
                ((0, 2), ThemeColor(0, 1, 1, 3500)),
                ((3, 3), ThemeColor(100, 1, 1, 3500)),
                ((4, 5), ThemeColor(200, 1, 1, 3500)),
                ((6, 6), ThemeColor(100, 1, 1, 3500)),
            ]

    describe "applying a range":
        it "adds one color if length is 1":
            color = ThemeColor(0, 1, 1, 3500)
            color2 = ThemeColor(100, 1, 1, 3500)
            colors = ZoneColors()
            colors.apply_to_range(color, color2, 1)
            assert colors._colors == [color]

        it "adds two colors if length is 2 where second color is averaged":
            color = ThemeColor(0, 1, 1, 3500)
            color2 = ThemeColor(100, 1, 1, 3500)
            second_color = ThemeColor.average([color2.limit_distance_to(color), color])

            colors = ZoneColors()
            colors.apply_to_range(color, color2, 2)
            assert colors._colors == [color, second_color]

        it "applies a gradient for length greater than two":
            color = ThemeColor(0, 1, 1, 3500)
            color2 = ThemeColor(100, 1, 1, 3500)

            colors = ZoneColors()
            colors.apply_to_range(color, color2, 8)
            hues = [float("{:.3f}".format(c.hue)) for c in colors._colors]
            assert hues == [0.0, 12.5, 25.0, 37.5, 50.0, 62.5, 75.0, 87.5]

    describe "applying a theme":
        it "applies a gradient of the colors in the theme":
            theme = Theme()
            theme.add_hsbk(10, 1, 1, 3500)
            theme.add_hsbk(100, 1, 1, 3500)
            theme.add_hsbk(40, 1, 1, 3500)
            theme.add_hsbk(300, 1, 1, 3500)

            colors = ZoneColors()
            colors.apply_theme(theme, 32)
            hues = [float("{:.3f}".format(c.hue)) for c in colors._colors]
            # fmt: off
            expected = [
                10.0, 21.25, 32.5, 43.75, 49.375, 55.0, 66.25, 77.5, 88.75, 94.375, 100.0,
                92.5, 85.0, 77.5, 73.75, 70.0, 62.5, 55.0, 47.5, 43.75, 40.0,
                27.5, 15.0, 2.5, 356.25, 350.0, 337.5, 325.0, 312.5, 306.25, 300.0, 300.0
            ]
            # fmt: on
            assert hues == expected

describe "TileColors":
    it "has tiles":
        colors = TileColors()
        assert colors.tiles == []

    it "can add a tile":
        colors = TileColors()
        hsbks = mock.Mock(name="hsbks")
        hsbks2 = mock.Mock(name="hsbks2")

        colors.add_tile(hsbks)
        colors.add_tile(hsbks2)

        assert colors.tiles == [hsbks, hsbks2]
