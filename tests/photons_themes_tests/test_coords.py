# coding: spec

from photons_themes.coords import user_coords_to_pixel_coords

from photons_app.test_helpers import TestCase

describe TestCase, "user_coords_to_pixel_coords":
    it "translates to top left corner":
        # fmt: off
        coords_and_sizes = [
            ((1, 1), (8, 8)),
            ((2, 2), (10, 9)),
            ((3, 3), (6, 6))
        ]
        # fmt: on

        normalized = user_coords_to_pixel_coords(coords_and_sizes)
        self.assertEqual(
            normalized,
            [
                ((8 - 4, 8 + 4), (8, 8)),
                ((20 - 5, int(18 + 4.5)), (10, 9)),
                ((18 - 3, 18 + 3), (6, 6)),
            ],
        )
