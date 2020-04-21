.. _cli_references:

References from the command line
================================

References in photons can be a single ``serial``, a list of ``serials`` or a
``special`` reference which defines how to find these ``serials``

A ``serial`` is a hex number that looks like ``d073d5xxxxxx`` and is the MAC
address of the device. For example it might be ``d073d5123456``. Whilst it
shouldn't be necessary to take down your lights, you can find these serials
printed on the side.

When we discover devices we get an IP address associated with each serial and
we use that to know where to send messages to.

So, for example::

    # Get the current color of the device with serial d073d5001337
    $ lifx lan:get_attr d073d5001337 color

    # Set the power of these two devices
    $ lifx lan:set_attr d073d5000001,d073d500adb8 power -- '{"level": 65535}'

You can also specify a number of ``special`` references like the following::

    # apply a theme to all devices on the network
    $ lifx lan:apply_theme _

    # apply a theme to just strips and beams
    $ lifx lan:apply_theme match:cap=multizone

    # transform a device with the label kitchen
    $ lifx lan:transform match:label=kitchen -- '{"color": "blue"}'

You can also put serials into a file with one line per serial and say::

    $ cat my_serials.txt
    d073d5008988
    d073d500ad23

    $ lifx lan:apply_theme file:my_serials.txt

The match reference
-------------------

The match reference has the following options:

serial
    The serial of the device

label
    The label set on the device, which is the name you see for this light in
    the LIFX app.

power
    Either "on" or "off" depending on whether the device is on or not.

group_id
    The uuid of the group set on this device

group_name
    The name of this group. Note that if you have several devices that have
    the same group, then this will be set to the label of the group
    with the newest updated_at option.

location_id
    The uuid of the location set on this device

location_name
    The name of this location. Note that if you have several devices that have
    the same location_id, then this will be set to the label of the location
    with the newest updated_at option.

hue, saturation, brightness, kelvin
    The hsbk values of the device. You can specify a range by saying something
    like ``10-30``, which would match any device with a hsbk value between 10
    and 30 (inclusive).

firmware_version
    The version of the HostFirmware as a string of "{major}.{minor}".

product_id
    The product id of the device as an integer. For example LIFX Tiles have the
    product id of 55.

product_identifier
    The identifier of the type of device. You can find these strings in the
    :ref:`products <products>` page.

cap
    A list of strings of capabilities this device has.

    * ``ir`` and ``not_ir``
    * ``color`` and ``not_color``
    * ``chain`` and ``not_chain``
    * ``matrix`` and ``not_matrix``
    * ``multizone`` and ``not_multizone``
    * ``variable_color_temp`` and ``not_variable_color_temp``

You can specify multiple specifiers like::

    "match:cap=matrix&saturation=1"

If you are setting a label and it has special characters in it, you need to
url encode the value. For example say I have a device with the label of
"Kitchen bench", then I'd have to address it by saying::

    "match:label=Kitchen%20bench"

You can specify multiple values with an ``&`` and multiple of the same specifier
For example if I want to do something with my tiles and my strips::

    "match:cap=chain&cap=multizone"

So if you ``&`` different specifiers they are a logical ``AND`` and an ``&`` with
multiple of the same specifier is a logical ``OR`` within that specifier.
