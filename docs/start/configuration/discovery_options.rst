.. _discovery:

Device Discovery
================

LIFX devices are found on the network by broadcasting a GetService message and
interpreting the StateService messages devices on the network send back.

However, on networks with a large amount of devices or where broadcast is
disabled, this method of discovery either doesn't work or is unreliable. For these
environments, photons can be given hard coded discovery information and serial
filters.

.. _discovery_options:

Discovery options
-----------------

In your configuration, you can say:

.. code-block:: yaml

   ---

   discovery_options:
     hardcoded_discovery:
       d073d5000001: "192.168.0.1"
       d073d5000002: "192.168.0.2"

And photons will use those ip addresses for those serials. By specifying
hardcoded_discovery, photons will not attempt to do broadcast discovery and will
only know about the serials you have specified.

You may also specify serial_filter:

.. code-block:: yaml

   ---

   discovery_options:
     serial_filter:
       - d073d5001337
       - d073d5001338

In this case, broadcast discovery will be used, but it will only discover those
two serials and ignore all other devices. This is handy if you want to restrict
what devices Photons ever interacts with.

You can also combine ``serial_filter`` and ``hardcoded_discovery``.

You can override what is configured with environment variables. For example,
regardless of what you have in configuration, if you say something like::

   $ export HARDCODED_DISCOVERY='{"d073d5111111": "192.168.0.1"}'
   $ lifx lan:get_attr _ color

With this, Photons will only care about ``d073d5111111`` and assume it's at
``192.168.0.1``

You may also specify ``SERIAL_FILTER``::

   $ export SERIAL_FILTER=d073d500001,d073d5111111
   $ lifx lan:get_attr _ color

This will do a broadcast discovery, but only care about ``d073d5000001`` and
``d073d5111111``.

If you want to turn off discovery options via environment variables you may
specify them as null. For example::

   $ export HARDCODED_DISCOVERY=null
   $ export SERIAL_FILTER=null
   $ lifx lan get_attr _ color

.. _target_options:

Target options
--------------

You may also define your own ``lan`` targets that have their own discovery
options:

.. code-block:: yaml

   ---

   targets:
      my_target:
        type: lan
        options:
          discovery_options:
            hardcoded_discovery:
              d073d5001337: "192.168.0.1"

In this case, ``my_target`` will only ever see ``d073d5001337`` instead of doing
broadcast discovery.

.. note:: the ``HARDCODED_DISCOVERY`` and ``SERIAL_FILTER`` environment
    variables will override even target specific discovery settings.

You can add to global discovery_options per target, for example:

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

In this scenario, ``target_one`` knows about ``d073d5000001`` and
``d073d5000002``.  Whilst ``target_two`` knows about ``d073d5000001`` and
``d073d5000003``.

You may also override serial_filter, for example:

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

In this case, all targets will do broadcast discovery, but the default lan target
will only see ``d073d5000001`` and ``d073d5000002``, whilst the ``target_one`` 
will only see ``d073d5000003`` and ``target_two`` will see all devices on the
network.
