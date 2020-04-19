.. _colour_helpers:

Working with Colour
===================

It's useful to be able to transform colour specifiers into ``hue``,
``saturation``, ``brightness`` and ``kelvin`` values. These are used by LIFX
devices to change how they look.

Photons supports all the colour specifies used by the LIFX
`HTTP API <https://api.developer.lifx.com/docs/colors>`_

You can turn these specifiers into hsbk values or even a packet that will tell
the device to change to those values.

.. autoclass:: photons_control.colour.ColourParser

.. autoclass:: photons_control.colour.Effects

.. autofunction:: photons_control.colour.make_hsbk

.. autofunction:: photons_control.colour.make_hsbks
