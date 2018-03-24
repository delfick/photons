"""
A theme is just a collection of colors and the job of the appliers is to choose
how those colors are displayed on the device.

.. autoclass:: photons_themes.theme.Theme
    :members:

.. autoclass:: photons_themes.theme.ThemeColor
    :members:
"""
import random
import math

class ThemeColor:
    """
    An encapsulation of ``hue``, ``saturation``, ``brightness`` and ``kelvin``.
    """
    def __init__(self, hue, saturation, brightness, kelvin):
        self.hue = hue
        self.saturation = saturation
        self.brightness = brightness
        self.kelvin = int(kelvin)

    def as_dict(self):
        return {"hue": self.hue, "saturation": self.saturation, "brightness": self.brightness, "kelvin": self.kelvin}

    @classmethod
    def average(kls, colors):
        """
        Return the average of all the provided colors

        If there are no colors we return white.
        """
        if not colors:
            return ThemeColor(0, 0, 1, 3500)

        hue_x_total = 0
        hue_y_total = 0
        saturation_total = 0
        brightness_total = 0
        kelvin_total = 0

        for color in colors:
            hue_x_total += math.sin(color.hue * 2.0 * math.pi / 360)
            hue_y_total += math.cos(color.hue * 2.0 * math.pi / 360)
            saturation_total += color.saturation
            brightness_total += color.brightness

            if color.kelvin == 0:
                kelvin_total += 3500
            else:
                kelvin_total += color.kelvin

        hue = (math.atan2(hue_x_total, hue_y_total) / (2.0 * math.pi))
        if (hue < 0.0):
            hue += 1.0
        hue *= 360

        saturation = saturation_total / len(colors)
        brightness = brightness_total / len(colors)
        kelvin = kelvin_total / len(colors)

        return ThemeColor(hue, saturation, brightness, kelvin)

    def __lt__(self, other):
        return (self.hue, self.saturation, self.brightness, self.kelvin) < (other.hue, other.saturation, other.brightness, other.kelvin)

    def __eq__(self, other):
        """A color is equal if it has the same hsbk value"""
        return other.hue == self.hue and other.saturation == self.saturation and other.brightness == self.brightness and other.kelvin == self.kelvin

    def __hash__(self):
        return hash((self.hue, self.saturation, self.brightness, self.kelvin))

    def limit_distance_to(self, other):
        """
        Return a color within 90 hue points of this color

        We take or add 90 depending on whether the other color is more than 180 hue points away
        where that is calculated by moving forward and wrapping around 360

        If the difference between the two colors is less than 90, then we just return the original color
        """
        raw_dist = self.hue - other.hue if self.hue > other.hue else other.hue - self.hue
        dist = 360 - raw_dist if raw_dist > 180 else raw_dist
        if abs(dist) > 90:
            h = self.hue + 90 if (other.hue + dist) % 360 == self.hue else self.hue - 90
            if h < 0:
                h += 360
            return ThemeColor(h, self.saturation, self.brightness, self.kelvin)
        else:
            return self

    def __repr__(self):
        return "<Color {}>".format(str((self.hue, self.saturation, self.brightness, self.kelvin)))

class Theme:
    """A wrapper around a list of ThemeColor objects"""
    def __init__(self):
        self.colors = []

    def add_hsbk(self, hue, saturation, brightness, kelvin):
        """Create a ThemeColor object and add it to our colors"""
        self.colors.append(ThemeColor(hue, saturation, brightness, kelvin))

    def random(self):
        """Return a random color from our array of colors"""
        return random.choice(self.colors)

    def __len__(self):
        """Return the number of colors we have in this theme"""
        return len(self.colors)

    def __iter__(self):
        """Iterate over the colors"""
        return iter(self.colors)

    def __contains__(self, color):
        """Say whether this color is in the theme"""
        return any(c == color for c in self)

    def __getitem__(self, i):
        """Return the color at this index"""
        return self.colors[i]

    def get_next_bounds_checked(self, i):
        """
        Return the next color after this index

        If there is no next color, then return the last color
        """
        return self[i + 1] if i + 1 < len(self) else self[i]

    def shuffled(self):
        """
        Return a new theme with the same colors but in a different order
        """
        new_theme = Theme()
        colors = list(self.colors)
        random.shuffle(colors)
        new_theme.colors = colors
        return new_theme

    def ensure_color(self):
        """Make sure we have atleast one colors"""
        if not self.colors:
            self.add_hsbk(0, 0, 1, 3500)
