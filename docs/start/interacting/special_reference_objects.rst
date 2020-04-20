.. _special_reference_objects:

Special Reference Objects
=========================

When you refer to one or more devices, you supply a ``reference`` to the
:ref:`sender <sender_interface>`. This can be a single serial like
``"d073d5006677"``, a list of these serials; or an object that knows how to
search for devices based on some condition.

.. note:: The serial is the MAC address of the device and can be found printed
    on the side of the device. It is a 12 character hex number that starts with
    ``d073d5``. So ``d073d5xxxxxx``, like ``d073d50a3bcd``.

You can also target devices by setting the serial directly on the packets:

.. code-block:: python

    from photons_messages import DeviceMessages, LightMessages


    async def my_action(target):
        # Get color for d073d5000001
        get_color = LightMessages.GetColor(target="d073d5000001")

        # Get power messages for for d073d5000002 and d073d5000003
        get_power1 = DeviceMessages.GetPower(target="d073d5000002")
        get_power2 = DeviceMessages.GetPower(target="d073d5000003")

        async with target.session() as sender:
            async with pkt in sender([get_color, get_power1, get_power2]):
                if pkt | LightMessages.LightState:
                    assert pkt.serial == "d073d5000001"

                elif pkt | DeviceMessages.StatePower:
                    assert pkt.serial in ("d073d5000002", "d073d5000003")

Otherwise you can use one of the following objects to address your devices in
either the :ref:`sender <sender_interface>` or in manually
:ref:`discovering <sender_discovery>` serials.

photons_app.special.FoundSerials
    This doesn't take in any arguments and just performs a normal discovery
    to find all the devices on the network.

    .. note:: Broadcasting on a network can be unreliable and doesn't
        necessarily return all the devices that are actually on the network.

photons_app.special.HardCodedSerials
    This takes in a single serial ``"d073d5000001"`` or a list of serials. It
    will keep searching for the serials you ask for until either the timeout
    occurs or it finds all the devices.

photons_app.special.ResolveReferencesFromFile
    This takes in the path to a file that has one serial per line. It will
    then create a ``HardCodedSerials`` reference and use that to discover
    those devices.

photons_control.device_finder.DeviceFinder
    This allows you to find devices based on their attributes. You can find
    more information about this on the page about the
    :ref:`DeviceFinder <device_finder>`

Making your own finder
----------------------

A ``SpecialReference`` is an object that has the following three methods on it:

.. code-block:: python

    from photons_app.errors import DevicesNotFound 

    import binascii


    class MyReference:
        """
        See below for the easy way of creating one of these
        """
        async def find(sender, *, timeout, **kwargs):
            # serials is a list of serials
            serials = [serial1, serial2, ...]

            # found is a dictionary of target bytes to transport information.
            # The easiest way to get this is
            # ```
            #    targets = [binascii.unhexlify(serial)[:6] for serial in serials]
            #    found = {target: sender.found[target] for serial in targets}
            # ```

            return found, serials

        def reset(selt):
            # Clear any cached data

        def raise_on_missing(self, found):
            # If the found dictionary doesn't contain all the serials we
            # expect, then raise a DevicesNotFound
            raise DevicesNotFound(missing=[missing_serial1, ...])

The easiest way to create one of these objects is to inherit from
``photons_app.special.SpecialReference`` and implement the ``find_serials``
method:

.. code-block:: python

    from photons_app.errors import DevicesNotFound

    from photons_transport import RetryOptions

    import binascii


    class UpTo(SpecialReference):
        """
        A SpecialReference object that finds the first ``upto`` devices
        """

        def __init__(self, upto=5):
            super().__init__()
            self.upto = upto

        async def find_serials(self, sender, *, timeout, broadcast=True):
            found = getattr(sender, "found", {})
            serials = []

            # Just keep retrying every 0.5 seconds until it's been 2 seconds,
            # And then retry every second after that.
            retrier = RetryOptions(timeouts=[[0.5, 2], [1, 2]])

            async for time_left, _ in retrier.iterator(end_after=timeout):
                if len(serials) >= self.upto:
                    break

                _, ss = await sender.find_devices(
                    timeout=time_left, broadcast=broadcast, raise_on_none=False
                )

                for s in ss:
                    if s not in serials:
                        if len(serials) >= self.upto:
                            break

                        serials.append(s)

                        target = binascii.unhexlify(s)[:6]
                        found[target] = sender.found[target]

            # Only need to return the found dictionary
            # I create a serials array anyway to avoid unhexlifying serials
            # Every time sender.find_devices returns.
            return found

        # If we knew specific serials, we could do
        # ```
        #    def missing(self, found):
        #       # Say we didn't find d073d5000001 despite wanting it
        #       return ["d03d5000001"]
        # ```

Then you would say:

.. code-block:: python

    from photons_messages import DeviceMessages


    async def my_action(target):
        # Turn off up to the first 6 devices I find
        async with target.session() as sender:
            await sender(DeviceMessages(level=0), UpTo(6))
