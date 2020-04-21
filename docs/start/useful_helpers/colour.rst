.. _colour_helpers:

Working with Colour
===================

It's useful to be able to transform colour specifiers into ``hue``,
``saturation``, ``brightness`` and ``kelvin`` values. These are used by LIFX
devices to change how they look.

Photons supports all the colour formats used by the LIFX
`HTTP API <https://api.developer.lifx.com/docs/colors>`_ as explained in the
:class:`ColourParser <photons_control.colour.ColourParser>` below.

.. autoclass:: photons_control.colour.ColourParser

.. autoclass:: photons_control.colour.Effects

.. autofunction:: photons_control.colour.make_hsbk

.. autofunction:: photons_control.colour.make_hsbks
