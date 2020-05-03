.. _common_cli_commands:

Common tasks with the CLI
============================

A full list of available tasks is returned by running ``lifx help``.

.. note:: The ``<reference>`` used in these common tasks is explained in
    :ref:`the CLI reference <cli_references>`. It determines which devices
    will be affected by the task used.

``find_devices`` and ``find_ips``
        List the serial numbers of all discovered devices on the local network::

        $ lifx lan:find_devices

    List the serial numbers and associated IP address of all discovered devices

        $ lifx lan:find_ips

``transform``
    This task changes the power and colour of the target devices over an
    optionally specified duration. It can also perform waveform-based
    transformations similar to the `Breathe <https://api.developer.lifx.com/docs/breathe-effect>`_
    and `Pulse <hthttps://api.developer.lifx.com/docs/pulse-effect>`_ effects
    available via the `LIFX HTTP API <https://api.developer.lifx.com/>`_.

    For example, turn off all the devices on the network ::

        $ lifx lan:transform -- '{"power": "off"}'

    Turn on a specific device::

        $ lifx lan:transform d073d5001337 -- '{"power": "on"}'

    Power on a group of devices and set to the color to red and brightness to
    100% followed by a waveform to cycle between red and blue three times over
    three seconds at 50% brightness::

        $ lifx lan:transform match:group_name=kitchen -- '{"color": "red", "brightness": 1, "power": "on"}'
        $ lifx lan:transform match:group_name=kitchen -- '{"color": "blue", "brightness": 0.5, "effect": "SINE", "cycles": 3, "period": 1}'

``attr``
    This task gets or sets attributes on a device using a specific packet type.
    The packet type is specified in the ``<artifact>`` field of the ``lifx``
    utility syntax, i.e. ``lifx lan:attr <reference> <artifact> -- <options>``.

    For example, get the color attribute value from all devices::

        $ lifx lan:attr _ GetColor

    Not all packet types include defaults for the available fields. For those
    types, a value must be explicity provided in the ``<options>`` field in
    valid JSON syntax::

        $ lifx lan:attr match:label=den SetPower -- '{"level": 0}'

    A full list of packet types and values is found on the :ref:`packets <packets>`
    page.

``unpack``
    LIFX binary messages are a string of bytes represented as a hexadecimal
    value. For example a :ref:`DeviceMessages.GetLabel` in hex look likes:

    .. code-block:: text

        2400001403b6cf3bd073d522932200000000000000000301000000000000000017000000

    Use the ``unpack`` task to retrieve the values from a LIFX binary message::

        $ lifx unpack -- 2400001403b6cf3bd073d522932200000000000000000301000000000000000017000000 | jq
        {
          "frame_address": {
            "ack_required": true,
            "res_required": true,
            "reserved2": "000000000000",
            "reserved3": "00",
            "sequence": 1,
            "target": "d073d52293220000"
          },
          "frame_header": {
            "addressable": true,
            "protocol": 1024,
            "reserved1": "00",
            "size": 36,
            "source": 1003468291,
            "tagged": false
          },
          "protocol_header": {
            "pkt_type": 23,
            "reserved4": "0000000000000000",
            "reserved5": "0000"
          }
        }

    .. note:: **Tip**: Pipe the output of the ``lifx unpack`` task through the
        ``jq`` utility to convert the JSON into human-readable format.

``pack``
    This task translates a dictionary of values into a LIFX binary message in
    hexadecimal format.

    Using the same example as above, the ``pack`` command outputs the hexadecimal
    representation of the provided JSON::

        $ lifx pack -- '{"frame_address": {"ack_required": true, "res_required": true, "reserved2": "000000000000", "reserved3": "00", "sequence": 1, "target": "d073d52293220000"}, "frame_header": {"addressable": true, "protocol": 1024, "reserved1": "00", "size": 36, "source": 1003468291, "tagged": false}, "protocol_header": {"pkt_type": 23, "reserved4": "0000000000000000", "reserved5": "0000"}}'
        2400001403b6cf3bd073d522932200000000000000000301000000000000000017000000

    It is not necessary to provide values for all fields. The ``pack`` command only requires mandatory fields to be
    specified. For example, constructing a :ref:`DeviceMessages.SetLabel` message::

        $ lifx pack -- '{"protocol": 1024, "pkt_type": 24, "source": 1, "sequence": 1, "target": "d073d5229322", "label": "basement"}'
        4400001401000000d073d522932200000000000000000301000000000000000018000000626173656d656e74000000000000000000000000000000000000000000000000

``get_effects``
    Returns the currently running firmware effects on the specified devices.
    This only applies to devices with firmware effects, i.e. the Tile, Candle,
    Strip and Beam. Currently active waveforms are not considered an effect.

``tile_effect``
    Starts a firmware effect on a Tile or Candle Colour device::

        $ lifx lan:tile_effect _ morph

    In the case of a range of device types being returned by the provided
    reference, only those with matrix firmware effects will be affected.

    The available effects are ``morph``, ``flame`` and ``off``.

``multizone_effect``
    Starts a firmware effect on a Z Strip or Beam device::

        $ lifx lan:multizone_effect _ move

    In the case of a range of device types being returned by the provided
    reference, only those with multizone firmware effects will be affected.

    The available effects are ``move`` and ``off``.

``apply_theme``
    Set a theme on your devices. By default, this applies a seven colour theme
    at 30% brightness onto the device.

    Apply the default theme to all devices::

        $ lifx lan:apply_theme

    Apply a theme using only red and blue::

        $ lifx lan:apply_theme -- '{"colors": ["red", "blue"]}'

    Apply a theme using only red and blue at 100% brightness::

        $ lifx lan:apply_theme -- '{"colors": ["red", "blue"], "overrides": {"brightness": 1}}'

Tile animations
    See :ref:`Tile animation commands <tile_animation_commands>`
