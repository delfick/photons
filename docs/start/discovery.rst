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

In your :ref:`configuration <config_file>` you can specify something like:

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
two serials and ignore all other devices. This is handy if you want to use
the :ref:`photons_device_finder` and have a large number of devices on your
network.

You can also combine serial_filter and hardcoded_discovery.

You can override what is configured with environment variables. For example,
regardless of what you have in configuration, if you say something like::

   $ export HARDCODED_DISCOVERY='{"d073d5111111": "192.168.0.1"}'
   $ lifx lan:get_attr _ color

Will only care about d073d5111111 and assume it's at 192.168.0.1

And/Or you may specify SERIAL_FILTER::

   $ export SERIAL_FILTER=d073d500001,d073d5111111
   $ lifx lan:get_attr _ color

This will do a broadcast discovery, but only care about d073d5000001 and d073d5111111

If you want to turn off discovery options via environment variables you may
specify them as null. For example::

   $ export HARDCODED_DISCOVERY=null
   $ export SERIAL_FILTER=null
   $ lifx lan get_attr _ color

.. _target_options:

Target options
--------------

You may also define your own ``lan`` targets that have their own discovery options
and broadcast address.

For example:

.. code-block:: yaml

   ---

   targets:
      my_target:
        type: lan
        options:
           default_broadcast: 192.168.0.255

Then when you say something like::

   $ lifx my_target:get_attr _ color

It will use 192.168.0.255 as the broadcast address instead of the default
255.255.255.255.

You can also add discovery_options to your target:

.. code-block:: yaml

   ---

   targets:
      my_target:
        type: lan
        options:
          discovery_options:
            hardcoded_discovery:
              d073d5001337: "192.168.0.1"

In this case, ``my_target`` will only ever see d073d5001337 instead of doing
broadcast discovery. Note that environment variables mentioned above will also
override per target options.

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

In this scenario, target_one knows about d073d5000001 and d073d5000002. Whilst
target_two knows about d073d5000001 and d073d5000003.

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
will only see d073d5000001 and d073d5000002, whilst the target_one will only
see d073d5000003 and target_two will see all devices on the network.

Programmatically telling photons where a device is
--------------------------------------------------

You can tell photons where a device is uses ``afr.add_service``, for example:

.. code-block:: python

   from photons_app.executor import library_setup

   from photons_messages import LightMessages, Services

   from delfick_project.logging import setup_logging


   async def doit(collector):
      lan_target = collector.configuration["target_register"].resolve("lan")

      async with lan_target.session() as afr:
         # Use add_service to tell photons where this device is
         # The run_with mechanism will know that it already has this serial when we
         # send messages to it, and so it won't try to do any discovery
         await afr.add_service("d073d533137a", Services.UDP, host="192.168.0.18", port=56700)

         msg = LightMessages.GetColor()
         async for pkt, _, _ in lan_target.script(msg).run_with("d073d533137a"):
               print("{0}: {1}".format(pkt.serial, repr(pkt.payload)))


   if __name__ == "__main__":
      setup_logging()
      collector = library_setup()
      collector.run_coro_as_main(doit(collector))
