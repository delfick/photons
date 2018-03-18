.. _finding_serials:

Finding Serials
===============

The ``run_with`` and ``run_with_all`` functions mentioned in :ref:`script_mechanism`
take in serials to send the messages to, but sometimes we don't know what serials
we want to work with and instead want to address devices based on label or group
or some other property.

To help with this, photons provides the ``DeviceFinder``.

Below is a short introduction to what it can do:

.. code-block:: python

    from photons_device_messages import DeviceMessages
    from photons_device_finder import DeviceFinder

    async def my_process(lan_target):
        device_finder = DeviceFinder(lan_target)

        # Optionally start the device_finder daemon functionality
        # Not doing this is equivalent to setting force_refresh to True everytime
        # we use the device_finder
        # By saying start then filters will use what information it already has,
        # and that information will be updated in the background
        await device_finder.start()

        # Determine the power for all the devices in the ``house`` group
        reference = device_finder.find(group_name="house")
        msg = DeviceMessages.GetPower()
        async for pkt, _, _ in lan_target.script(msg).run_with(reference):
            print(pkt.target, pkt.power)

        # Set the power for all the devices with the label kitchen
        reference = device_finder.find(label="kitchen")
        msg = DeviceMessages.SetPower(level=65535)
        await lan_target.script(msg).run_with_all(reference)

You can also use the device_finder to determine a list of serials given some
conditions, or even a dictionary of information for those devices.

Detailed information can be found at :ref:`photons_device_finder`.

Information about the mechanism that supports this can be found at
:ref:`photons_app_special`
