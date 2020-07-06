.. _orientation_helpers:

Working with Tile orientation
=============================

The LIFX tile contains an accelerometer that is used to determine what direction
is down. This information can then be used by Photons to rotate the 64 hsbk
values we give to a tile such that it looks like the Tile is rotated upright.

So for example, if the Tile is rotated to the left, then when we send the hsbk
values to the device, we first rotate them to the right.

Photons contains code to make this easy.

.. automodule:: photons_canvas.orientation
    :members:
    :undoc-members:

It is recommended you use the :ref:`"parts" plan <plan_parts>` to access this
functionality.
