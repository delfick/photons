# coding: spec

from photons_themes.appliers.single import LightApplier
from photons_themes.theme import Theme, ThemeColor

from photons_app.test_helpers import TestCase

from unittest import mock

describe TestCase, "LightApplier":
    it "just returns a random color from the theme":
        color = mock.Mock(name="color")

        theme = mock.Mock(name="theme")
        theme.shuffled.return_value = theme
        theme.random.return_value = color

        applier = LightApplier()
        self.assertIs(applier.apply_theme(theme), color)

    it "returns white if there is no colors in the theme":
        theme = Theme()
        applier = LightApplier()
        self.assertEqual(applier.apply_theme(theme), ThemeColor(0, 0, 1, 3500))
