.. _discovery:

Device Discovery
================

Photons discovers LIFX devices by broadcasting a GetService message and
interpreting the StateService messages received from the network.

This method is unavailable on networks that have broadcasting disabled and
unreliable on networks with a large amount of devices. To remove the need for
broadcast delivery, hardcoded discovery is used. To improve the reliability of
discovery, serial filters can be configured.

.. _discovery_options:

Discovery options
-----------------

Use the ``hardcoded_discovery`` option to configure specific serial to IP
address mapping:

.. code-block:: yaml

   ---

   discovery_options:
     hardcoded_discovery:
       d073d5000001: "192.168.0.1"
       d073d5000002: "192.168.0.2"

This requires static IP address assignment on the network DHCP server so that
each bulb always gets the same IP address.

If ``hardcoded_discovery`` is configured, Photons will not do any broadcast
discovery and will not find any bulbs not specifically configured.

A serial_filter restricts the devices Photons can discover, but still uses
broadcasting so static IP addresses are not required:

.. code-block:: yaml

   ---

   discovery_options:
     serial_filter:
       - d073d5001337
       - d073d5001338

In this case, broadcast discovery is used, but only to discover the specified
serials. All other devices are ignored.

The ``serial_filter`` and ``hardcoded_discovery`` options can be combined.

The ``HARDCODED_DISCOVERY`` environment variable sets or overrides any
``hardcoded_discovery`` configuration setting. In the following example, Photons
will only discover a single device with the serial of ``d073d5111111`` if it
has the IP address of ``192.168.0.1``::

   $ export HARDCODED_DISCOVERY='{"d073d5111111": "192.168.0.1"}'
   $ lifx lan:get_attr _ color

The ``SERIAL_FILTER`` environment variable sets or overrides any ``serial_filter``
configuration setting::

   $ export SERIAL_FILTER=d073d500001,d073d5111111
   $ lifx lan:get_attr _ color

Photons will do a broadcast discovery, but only for devices with the serial of
``d073d5000001`` and ``d073d5111111``.

Disable any discovery options set in a configuration file with an environment
variable set to null::

   $ export HARDCODED_DISCOVERY=null
   $ export SERIAL_FILTER=null
   $ lifx lan get_attr _ color

.. _target_options:

Target options
--------------

Custom defined ``lan`` targets can have unique discovery options:

.. code-block:: yaml

   ---

   targets:
      my_target:
        type: lan
        options:
          discovery_options:
            hardcoded_discovery:
              d073d5001337: "192.168.0.1"

In this case, ``my_target`` is restricted to a single device with the serial
``d073d5001337`` using the IP address ``192.168.0.1``.

.. note:: the ``HARDCODED_DISCOVERY`` and ``SERIAL_FILTER`` environment
    variables are global and will override target-specific discovery settings.

Global discovery options are combined with target-specific discovery options:

.. code-block:: yaml

   ---

   discovery_options:
     hardcoded_discovery:
       d073d5000001: 192.168.0.1

   targets:
      target_one:
        type: lan
        options:
          discovery_options:
            hardcoded_discovery:
              d073d5000002: 192.168.0.2

      target_two:
        type: lan
        options:
          discovery_options:
            hardcoded_discovery:
              d073d5000003: 192.168.0.3

In this scenario, ``target_one`` contains ``d073d5000001`` and
``d073d5000002`` while ``target_two`` contains ``d073d5000001`` and
``d073d5000003``.

The global serial_filter is also combined with a target-specific filter:

.. code-block:: yaml

   ---

   discovery_options:
     serial_filter:
      - d073d5000001
      - d073d5000002

   targets:
      target_one:
        type: lan
        options:
          discovery_options:
            serial_filter:
             - d073d5000003

      target_two:
        type: lan
        options:
          discovery_options:
            serial_filter: null

In this case, all targets use broadcast discovery but the default ``lan`` target
will only find ``d073d5000001`` and ``d073d5000002``, ``target_one``
will only find ``d073d5000003`` and ``target_two`` will find all devices on the
network.
