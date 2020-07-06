.. _cli_references:

References from the command line
================================

:term:`References<reference>` in Photons are specified either as a single
``serial``, a list of ``serials`` or a ``special`` reference which defines how
to find devices dynamically on the network.

A ``serial`` is a 12-digit hexadecimal number in the format ``d073d5xxxxxx``,
e.g. ``d073d5123456`` and is also the :term:`MAC address` of the device. The
serial number is printed on the base of each bulb.

When Photons discovers devices, it associates an IP address with each serial and
uses that to target packets for each device.

For example, get the current color of the device with serial ``d073d5001337``::

    $ lifx lan:get_attr d073d5001337 color

Set the power of these two devices::

    $ lifx lan:set_attr d073d5000001,d073d500adb8 power -- '{"level": 65535}'

Photons provides some special references including ``_`` which is a shortcut
for all discovered devices on the network and the
:ref:`match reference <match-reference>`.

Toggle the power on all devices on the network::

    $ lifx lan:power_toggle _

Set all multizone devices (Z and Beam) to green::

    $ lifx lan:transform match:cap=multizone -- '{"color": "green"}'

Transform a device with the label ``kitchen`` to blue over 2 seconds::

    $ lifx lan:transform match:label=kitchen -- '{"color": "blue", "duration": 2}'

Photons also accepts a list of serials contained within a file as the
reference::

    $ cat my_serials.txt
    d073d5008988
    d073d500ad23

    $ lifx lan:apply_theme file:my_serials.txt

.. _match-reference:

The match reference
-------------------

The ``match`` :term:`reference` has the following options:

.. glossary::

   serial
      The serial of the device

   label
      The label of a device is its name as defined in the smart phone app.

   power
      Either "on" or "off" depending on whether the device is on or not.

   group_id
      The UUID of the group set on this device.

   group_name
      The name of a group. If there are several devices that have the same
      group_id, this will be set to the label of the group with the newest
      ``updated_at`` option.

   location_id
      The UUID of the location set on this device.

   location_name
      The name of a location. If there are several devices that have the same
      location_id, this will be set to the label of the location with the
      newest ``updated_at`` option.

   hue
   saturation
   brightness
   kelvin
      The HSBK values of the device. You can specify a range by providing the
      minimum and maximum values seperated by a hypen, e.g. ``10-30``, which
      would match any device with an HSBK value between 10 and 30 (inclusive).

   firmware_version
      The version of the HostFirmware as a string of "{major}.{minor}".

   product_id
      The product ID of the device as an integer. For example LIFX Tiles have the
      product ID of 55.

   product_identifier
      The identifier of the type of device. A list of available identifer strings
      is available on the :ref:`products <products>` page.

   cap
      A list of capability strings, i.e.

         * ``ir`` and ``not_ir``
         * ``color`` and ``not_color``
         * ``chain`` and ``not_chain``
         * ``matrix`` and ``not_matrix``
         * ``multizone`` and ``not_multizone``
         * ``variable_color_temp`` and ``not_variable_color_temp``

      Use the ``&`` operator to combine multiple options or multiple values of
      the same option::

         # Find matrix devices with a saturation value of 1
         "match:cap=matrix&saturation=1"

         # Find devices that have either the chain and multizone capabilities
         "match:cap=chain&cap=multizone"

      .. note:: combining different options uses a logical ``AND`` while
         combining multiple values of the same option uses a logical ``OR``.

      To match on a label with specicial characters, provide the URL encoded
      value of the label. For example, to find a device with the label "Kitchen
      bench" use the following match string::

         "match:label=Kitchen%20bench"
