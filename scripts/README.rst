Handy Scripts
=============

To run these scripts first run ``./setup_venv``

Then just run the scripts.

Unless you're on windows, in which case ``./setup_venv`` won't work. On windows
make you're own virtualenv and ``pip install photons-core`` in it, or
``pip install -e .`` frm the ``photons-core`` directory and then run the scripts
with ``python``. i.e. ``python find``.

References
----------

In all the commands below, ``<reference>`` can be empty or an ``_`` to signify
running the command against all the devices on the network.

Or it can be a comma separated list of serials like ``d073d5000001,d073d5000002``

Or it can be a ``match:<options>`` where ``<options>`` is a url query string
specifying filters to match against.

For example, ``match:group_name=one&cap=multizone`` will match against all
the multizone capable lights in the ``one`` group.

Or ``match:cap=multizone&cap=ir`` will match against all the multizone and
infrared capable lights.

You may also specify a file that has newline separated serials in it by saying
``file:/path/to/filename``.

Common Command Examples
-----------------------

Finding devices::

  ./find

Finding devices with a filter:
  You can use filters to find your devices with the ``./find_with_filter``
  command.

  For example to find strips and A19s::

    ./find_with_filter -- '{"product_identifier": ["lifx_z", "lifx_a19"]}'

  Or all the lights that are turned off"::

    ./find_with_filter -- '{"power": "off"}'

Finding devices and other information about them::

  ./info <reference>

A never ending loop of getting information about devices on your network::

  ./repeater <reference>

Asking for information:
  You can ask a bulb for information using ``./lan_control get_attr <reference> <message>``

  For example to send a ``GetColor`` to a bulb and print out the response you
  would run::

    ./lan_control get_attr d073d500001 color

  Or to do a ``GetHostFirmware``::

    ./lan_control get_attr d073d580085 host_firmware

Sending set messages:
  You can change a bulb with a ``Set`` message by using ``./lan_control set_attr <reference> <message> -- '{<options}'``

  For example, to send a ``SetColor``::

    ./lan_control set_attr d073d580085 color -- '{"hue": 240, "saturation": 0.4, "brightness": 0.8, "kelvin": 2500}'

  Or a ``SetLabel``::

    ./lan_control set_attr d073d580085 label -- '{"label": "Ceiling"}'`

Transform:
  This command can apply a state to multiple devices using options similar to
  the http API.

  For example, to make all the lights on the network blue and 50% brightness::

    ./transform -- '{"color": "blue", "brightness": 0.5}'`

  Or to make them pulse blue::

    ./transform -- '{"color": "blue", "brightness": 0.5, "effect": "pulse"}'`

  You can also address individual serials by saying::

    ./transform d073d5000001,d073d5000002 -- '{"color": "green", "power": "on"}'

  Or address against a filter::

    ./transform match:cap=color -- '{"color": "green"}'

Applying a theme
  To apply a theme to all devices on your network::

    ./apply_theme -- '{"colors": [{"brightness": 0.3, "hue": 0, "kelvin": 3500, "saturation": 1}, {"brightness": 0.3, "hue": 40, "kelvin": 3500, "saturation": 1}, {"brightness": 0.3, "hue": 60, "kelvin": 3500, "saturation": 1}, {"brightness": 0.3, "hue": 127, "kelvin": 3500, "saturation": 1}, {"brightness": 0.3, "hue": 239, "kelvin": 3500, "saturation": 1}, {"brightness": 0.3, "hue": 271, "kelvin": 3500, "saturation": 1}, {"brightness": 0.3, "hue": 294, "kelvin": 3500, "saturation": 1}]}'

  To apply a theme to specific devices::

    ./apply_theme d073d500001,d073d500002 -- '{"colors": [{"brightness": 0.3, "hue": 0, "kelvin": 3500, "saturation": 1}]}'

  You must specify colors in a json string after a ``--`` and optionally
  provide a duration in seconds.

  You can also supply the ``theme`` option to change how the theme is applied.
  By default it is ``SPLOTCH``

Strip Control
-------------

Getting information about the zones in the strip::

  ./lan_control get_zones d073d500001

Setting the zones on a strip:
  Note that you can only set one contiguous section of the strip at a time.

  For example, to make zones from 0 to 10 red::

    ./lan_control set_zones d073d514e733 -- '{"start_index": 0, "end_index": 10, "hue": 0, "saturation": 1, "brightness": 1}'

  You also can set ``kelvin`` and ``duration``.

  Also, if you want to apply multiple sections and then change them all at once,
  you can set ``type`` to ``NO_APPLY`` and then set it to ``APPLY`` for the last
  message (which is the default value).

Tile Control
------------

Getting device chain::

  ./lan_control get_device_chain <reference>

Getting state from device chain::

  ./lan_control get_chain_state <reference> -- '{"tile_index": 0, "length": 2, "x": 0, "y": 0, "width": 8, "size": 64}'

Setting state on a tile::

  ./lan_control set_chain_state <reference> -- '{"colors": [[[0, 1, 0.3, 1500], [5, 1, 0.3, 1500], [10, 1, 0.3, 1500], [15, 1, 0.3, 1500], [20, 1, 0.3, 1500], [25, 1, 0.3, 1500], [30, 1, 0.3, 1500], [35, 1, 0.3, 1500]], [[40, 1, 0.3, 1500], [45, 1, 0.3, 1500], [50, 1, 0.3, 1500], [55, 1, 0.3, 1500], [60, 1, 0.3, 1500], [65, 1, 0.3, 1500], [70, 1, 0.3, 1500], [75, 1, 0.3, 1500]], [[80, 1, 0.3, 1500], [85, 1, 0.3, 1500], [90, 1, 0.3, 1500], [95, 1, 0.3, 1500], [100, 1, 0.3, 1500], [105, 1, 0.3, 1500], [110, 1, 0.3, 1500], [115, 1, 0.3, 1500]], [[120, 1, 0.3, 1500], [125, 1, 0.3, 1500], [130, 1, 0.3, 1500], [135, 1, 0.3, 1500], [140, 1, 0.3, 1500], [145, 1, 0.3, 1500], [150, 1, 0.3, 1500], [155, 1, 0.3, 1500]], [[160, 1, 0.3, 1500], [165, 1, 0.3, 1500], [170, 1, 0.3, 1500], [175, 1, 0.3, 1500], [180, 1, 0.3, 1500], [185, 1, 0.3, 1500], [190, 1, 0.3, 1500], [195, 1, 0.3, 1500]], [[200, 1, 0.3, 1500], [205, 1, 0.3, 1500], [210, 1, 0.3, 1500], [215, 1, 0.3, 1500], [220, 1, 0.3, 1500], [225, 1, 0.3, 1500], [230, 1, 0.3, 1500], [235, 1, 0.3, 1500]], [[240, 1, 0.3, 1500], [245, 1, 0.3, 1500], [250, 1, 0.3, 1500], [255, 1, 0.3, 1500], [260, 1, 0.3, 1500], [265, 1, 0.3, 1500], [270, 1, 0.3, 1500], [275, 1, 0.3, 1500]], [[280, 1, 0.3, 1500], [285, 1, 0.3, 1500], [290, 1, 0.3, 1500], [295, 1, 0.3, 1500], [300, 1, 0.3, 1500], [305, 1, 0.3, 1500], [310, 1, 0.3, 1500], [315, 1, 0.3, 1500]]], "tile_index": 0, "length": 2, "x": 0, "y": 0, "width": 8}'

You can run animations with the tile with the ``tile_time``, ``tile_marquee``
and ``tile_pacman`` actions. For example::

  ./lan_control tile_time <reference> -- '{options}'

  ./lan_control tile_marquee <reference> -- '{"text": "hello there"}'

  ./lan_control tile_pacman <reference>

More information can be found at https://delfick.github.io/photons-core/tile_animations.html
