"""
This module contains code for representing the colors for devices on a plane
that covers one or more devices.

Tasks
-----

See :ref:`tasks`.

.. photons_module_tasks::

Themes
------

.. automodule:: photons_canvas.theme

Canvas
------

.. automodule:: photons_canvas.canvas

Animations
----------

.. automodule:: photons_canvas.animations
"""

from photons_canvas.points import helpers as point_helpers, rearrange
from photons_canvas.points.canvas import Canvas
from photons_canvas.theme import ApplyTheme
from photons_canvas import font

__all__ = [
    "Canvas",
    "point_helpers",
    "rearrange",
    "ApplyTheme",
    "Points",
    "font",
]
