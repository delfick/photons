.. _common_cli_commands:

Common commands from the cli
============================

You can find a full list of built in commands by saying ``lifx help`` but
the most commons ones are as follows.

.. note:: The <reference> in all these commands is explained in
    :ref:`the cli references section <cli_references>`

find_devices and find_ips
    Find the devices on your network::

        # Just get the serials
        $ lifx lan:find_devices

        # Get the IP addresses of the devices too
        $ lifx lan:find_ips

transform
    This command lets you change the power, colour of your device with a duration
    and optionally with a waveform.

    For example::

        # Turn off all the devices on the network
        $ lifx lan:transform -- '{"power": "off"}'

        # turn on a specific device
        $ lifx lan:transform d073d5001337 -- '{"power": "on"}'

        # Start a waveform on a group after first starting them on red
        $ lifx lan:transform match:group_name=kitchen -- '{"color": "red", "brightness": 1, "power": "on"}'
        $ lifx lan:transform match:group_name=kitchen -- '{"color": "blue", "brightness": 0.5, "effect": "SINE", "cycles": 3, "period": 1}'

get_attr and set_attr
    This command looks like ``lifx lan:get_attr <reference> <message> -- '{options}'``
    and will construct a message to send and print all the replies.

    So for ``get_attr`` if you specify ``color`` as the message, we will send
    a ``GetColor`` to the device. Or if you say ``device_chain`` we will send
    a ``GetDeviceChain`` message to the device.

    The ``set_attr`` command does the same but prefixes the message name with
    ``Set`` instead of ``Get``. So a ``lifx lan:set_attr <reference> waveform_optional``
    will send a ``SetWaveformOptional`` to the device.

    Not all commands have defaults for their fields and so for these you must
    specify what values to use. For example::

        $ lifx lan:set_attr match:label=den power -- '{"level": 0}'

attr
    This is the same as ``get_attr`` and ``set_attr`` but without the prefixing
    of the message name.

get_effects
    Return the currently running firmware effects on your devices. This only
    applies to the Tile, Candle, Strip and Beam devices as we don't have a
    message that tells us if a Waveform is running on the device.

multizone_effect and tile_effect
    Start a firmware effect on your devices.

    So for strip and Beams you can say::

        $ lifx lan:multizone_effect _  move
        $ lifx lan:multizone_effect _ off

    And for the Tile and candle::

        $ lifx lan:tile_effect _ morph
        $ lifx lan:tile_effect _ flame
        $ lifx lan:tile_effect _ off

unpack
    LIFX binary messages are just a string of bytes. You can represent these
    as a hex value. For example a GetLabel in hex may look like:

    .. code-block:: text

        2400001403b6cf3bd073d522932200000000000000000301000000000000000017000000

    You can get the values from this message by saying::

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

pack
    If you have a dictionary of values you can then pack them into a hex value
    that represents the message to send to the device. For example to get back
    our bytes from above::

        $ lifx pack -- '{"frame_address": {"ack_required": true, "res_required": true, "reserved2": "000000000000", "reserved3": "00", "sequence": 1, "target": "d073d52293220000"}, "frame_header": {"addressable": true, "protocol": 1024, "reserved1": "00", "size": 36, "source": 1003468291, "tagged": false}, "protocol_header": {"pkt_type": 23, "reserved4": "0000000000000000", "reserved5": "0000"}}'
        2400001403b6cf3bd073d522932200000000000000000301000000000000000017000000

    You can be a little less verbose, for example constructing a SetLabel can
    look like::

        $ lifx pack -- '{"protocol": 1024, "pkt_type": 24, "source": 1, "sequence": 1, "target": "d073d5229322", "label": "basement"}'
        4400001401000000d073d522932200000000000000000301000000000000000018000000626173656d656e74000000000000000000000000000000000000000000000000

tile_effect
    Start an effect on your Tile or Colour Candle::

        $ lifx lan:tile_effect _ morph

    You may specify other devices in the reference and it'll only apply to
    devices that support tile firmware effects.

    You have ``morph``, ``flame`` and ``off``

multizone_effect
    Start an effect on your Strip or Beam::

        $ lifx lan:multizone_effect _ move

    You may specify other devices in the reference and it'll only apply to
    devices that support multizone firmware effects.

    You have ``move`` and ``off``.

apply_theme
    Set a theme on your devices. By default this behaves like the ``exciting``
    theme in the LIFX mobile apps::

        # Apply the theme to all devices
        $ lifx lan:apply_theme

        # apply a theme only using red and blue
        $ lifx lan:apply_theme -- '{"colors": ["red", "blue"]}'

        # apply a theme only using red and blue and a smaller brightness
        $ lifx lan:apply_theme -- '{"colors": ["red", "blue"], "overrides": {"brightness": 0.1}}'

Tile animations
    See :ref:`Tile animation commands <tile_animation_commands>`
