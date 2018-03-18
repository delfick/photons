"""
There's only so much you can do with a single light. The LightApplier just
chooses a random color from our theme.
"""

class LightApplier:
    """
    Get us a random color from our theme::

        applier = LightApplier()
        color = applier.apply_theme(theme)

    .. automethod:: apply_theme
    """
    def apply_theme(self, theme):
        """Just return a random color from our theme"""
        theme = theme.shuffled()
        theme.ensure_color()
        return theme.random()
