.. _products_root:

The Product Registry
====================

Different LIFX devices have a range of capabilities. For example, our LIFX+
range have the ability to output Infrared light, and the Tile has a 2d matrix
of zones.

You can query devices for their product id to work out what kind of device
it is and use that to then determine what you can do with the device. This is
done with the :ref:`GetVersion <DeviceMessages.GetVersion>` message, which gives
you a ``vendor`` and ``product``. The ``vendor`` is always ``1`` to specify
the device is a ``LIFX`` device. There may be additional ``vendor`` values
in the future.

Photons provides a registry of the products that allow you to match the
``vendor`` and ``product`` to an object that tells you what capabilities are
available.

You can get this object by doing something like:

.. code-block::

    from photons_messages import DeviceMessages
    from photons_products import Products


    async def my_script(sender, reference):
        async for pkt in sender(DeviceMessages.GetVersion(), reference):
            if pkt | DeviceMessages.StateVersion:
                cap = Products[pkt.vendor, pkt.product].cap
                have = "has" if cap.has_ir else "doesn't have"
                print(f"device {pkt.serial} {have} infrared ability")

Some capabilities are dependent on the firmware version, which you can get
with the :ref:`GetHostFirmware <DeviceMessages.GetHostFirmware>` message.
If you have a :ref:`StateVersion <DeviceMessages.StateVersion>` and
:ref:`StateHostFirmware <DeviceMessages.StateHostFirmware>` message then you
can do something like:

.. code-block:: python

    from photons_app.actions import an_action

    from photons_messages import DeviceMessages
    from photons_products import Products

    from collections import defaultdict


    @an_action(special_reference=True, needs_target=True)
    async def has_multizone(collector, target, reference, **kwargs):
        by_device = defaultdict(dict)

        async with target.session() as sender:
            async for pkt in sender(
                [DeviceMessages.GetVersion(), DeviceMessages.GetHostFirmware()], reference
            ):
                if pkt | DeviceMessages.StateVersion:
                    by_device[pkt.serial]["version"] = pkt
                elif pkt | DeviceMessages.StateHostFirmware:
                    by_device[pkt.serial]["firmware"] = pkt

            for serial, pkts in by_device.items():
                version = pkts["version"]
                firmware = pkts["firmware"]

                # Calling cap with the major and minor parts of the firmware version
                # will return a new capability object that then knows what
                # firmware is on the device.
                cap = Products[version.vendor, version.product].cap(
                    firmware.version_major, firmware.version_minor
                )

                if cap.has_extended_multizone:
                    print(f"device {serial} has extended multizone capability")
                elif cap.has_multizone:
                    print(f"device {serial} has multizone, but not extended multizone")
                else:
                    print(f"device {serial} doesn't have any multizone capability")


    if __name__ == "__main__":
        __import__("photons_core").run("lan:has_multizone {@:1:}")

The problem with this script is you have to wait for all the devices to return
values before you get any results. If you want to print the information as
devices return information, you can use the :ref:`gatherer <gatherer_interface>`:

.. code-block:: python

    from photons_app.actions import an_action


    @an_action(special_reference=True, needs_target=True)
    async def has_multizone(collector, target, reference, **kwargs):
        async with target.session() as sender:
            plans = sender.make_plans("capability")

            async for serial, complete, info in sender.gatherer.gather_per_serial(
                plans, reference
            ):
                if complete:
                    cap = info["capability"]["cap"]

                    if cap.has_extended_multizone:
                        print(f"device {serial} has extended multizone capability")
                    elif cap.has_multizone:
                        print(f"device {serial} has multizone, but not extended multizone")
                    else:
                        print(f"device {serial} doesn't have any multizone capability")


    if __name__ == "__main__":
        __import__("photons_core").run("lan:has_multizone {@:1:}")

You can see the :ref:`available capabilities <available_caps>` and the
:ref:`products  <products>` that photons knows about.

.. toctree::
    :hidden:

    available_caps
    products
