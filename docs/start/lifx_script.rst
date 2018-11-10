.. _lifx_photons_lifx_script:

LIFX script
===========

When you have ``pip install lifx-photons-core`` you will have a ``lifx`` script
in your PATH which can be used to access photons functionality.

For example:

finding devices on the lan
    ``lifx lan:find_devices``

finding devices with a filter
    ``lifx lan:find_with_filter -- '{"label": "kitchen"}'``

Unpacking a binary payload
    ``lifx unpack -- 24000014d87d0a89d073d514e73300000000000000000301000000000000000020000000``

Setting some attribute on a light
    ``lifx lan:set_attr d073d514e733 power -- '{"level": 0}'``

Getting some attribute from a light
    ``lifx lan:get_attr d073d514e733 power``

Doing a http api like transform on a light
    ``lifx lan:transform d073d514e733 -- '{"power": "on", "color": "blue"}'``

Applying a theme of colours to all the lights on your network
    ``lifx lan:apply_theme -- '{"colors": [{"brightness": 0.3, "hue": 0, "kelvin": 3500, "saturation": 1}, ...]}'``

Applying an animation to your tile
    ``lifx lan:tile_pacman match:cap=chain``

    See :ref:`tile_animations` for more information.

If you execute ``lifx`` with no arguments it will display all the available tasks.

See :ref:`tasks` for more information.
