.. _device_finder:

The Device Finder
=================

It can be really helpful to target devices based on certain attributes without
having to first ask the device all the necessary questions. To make this task
easier, photons provides a ``DeviceFinder``
:ref:`special reference <special_reference_objects>`:

.. code-block:: python

    from photons_control.device_finder import DeviceFinder
    from photons_messages import DeviceMessages


    async def my_action(target):
        async with target.session() as sender:
            reference = DeviceFinder.from_kwargs(label="kitchen")
            msg = DeviceFinder.SetPower(level=0)

            # Turn off the device with the label kitchen
            await sender(msg, reference)

To create a special reference, you use the same methods as the ``Filter`` class
mentioned below.  Or you can create a ``DeviceFinder`` by instantiating it
with an instance of that ``Filter`` class.

Once you have a ``DeviceFinder`` object you then use it like any other
``reference`` object in photons:

Valid Filters
-------------

You can create a ``Filter`` using a number of different formats:

.. code-block:: python

    from photons_control.device_finder import Filter


    fltr = Filter.from_json_str('{"refresh_info": true, "firmware_version": "1.22"}')

    # or
    fltr = Filter.from_options({"refresh_info": True, "firmware_version": "1.22"})

    # or
    fltr = Filter.from_kwargs(refresh_info=True, firmware_version="1.22")

    # or
    fltr = Filter.from_key_value_str("refresh_info=true firmware_version=1.22")

    # or
    fltr = Filter.from_url_str("refresh_info=true&firmware_version=1.22")

The filter takes in:

refresh_info:
    Refresh the information on the device

refresh_discovery:
    Refresh discovery information

serial
    The serial of the device

label
    The label set on the device

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
    The product id of the device as an integer. You can see the hex product id
    of each device type in the ``photons_products`` module.

cap
    A list of strings of capabilities this device has.

    Capabilities include:

    * ``ir`` and ``not_ir``
    * ``color`` and ``not_color``
    * ``chain`` and ``not_chain``
    * ``matrix`` and ``not_matrix``
    * ``multizone`` and ``not_multizone``
    * ``variable_color_temp`` and ``not_variable_color_temp``

When a property in the filter is an array, it will match any device that matches
against any of the items in the array.

And a filter with multiple properties will only match devices that match against
all those properties.

Label properties ``label``, ``location_name``, ``group_name`` are matched with
globs. So if you have device1 with label of ``hallway_1`` and device2 with a label
of ``hallway_2`` you can choose both of them by using
``Filter.from_kwargs(label="hallway_*")``

Sharing gathered data
---------------------

If you want to share data retrieved from the devices between multiple
``DeviceFinder`` objects then you can create a ``Finder`` object and pass that
in when you create the ``DeviceFinder``:

.. code-block:: python

    from photons_control.device_finder import DeviceFinder, Finder
    from photons_messages import DeviceMessages


    async def my_action(target):
        async with target.session() as sender:
            finder = Finder(sender)

            # Turn off the lights with label kitchen
            reference = DeviceFinder.from_kwargs(label="kitchen", finder=finder)
            await sender(DeviceMessages.SetPower(level=0), reference)

            # Turn on the lights with label attic
            # Note that without passing in finder, it would ask the devices for
            # their label again
            reference = DeviceFinder.from_options({"label": "attic"}, finder=finder)
            await sender(DeviceMessages.SetPower(level=65535), reference)

Streaming serials and info from the finder
------------------------------------------

It's possible to stream devices from the ``DeviceFinder``. The advantage here
is the ``SpecialReference`` waits for all devices to respond before returning
what it found, but we can use the finder to instead stream devices as they
answer enough questions:

.. code-block:: python

    from photons_control.device_finder import DeviceFinder, Finder


    async def my_action(target):
        async with target.session() as sender:
            # The finder is optional, but does mean subsequent calls to
            # serials or info will not have to ask the devices for information
            # that it already asked for
            finder = Finder(sender)

            reference = DeviceFinder.from_kwargs(cap=["matrix"], group_name=["attic"], finder=finder)

            async for device in reference.serials(sender):
                print(device.serial)

            async for device in reference.info(sender):
                # This returns the same device objects as .serials
                # But asks all the questions to the device so that
                # ``device.info`` is fully populated
                print(device.serial, device.info)

.. note:: the ``info`` property is a dictionary of values on the device where
    the available properties are those you can control on the ``Filter`` class.

Daemon
------

You can start a daemon that you can use to query the network continuously.

.. code-block:: python

    from photons_control.device_finder import DeviceFinderDaemon, Filter


    # These points of information have their own default refresh numbers
    # But you can override them like this.
    time_between_queries = {"LIGHT_STATE": 10, "FIRMWARE": 300, "GROUP": 60, "LOCATION": 60}

    async with target.session() as sender:
        daemon = DeviceFinderDaemon(
            sender,
            photons_app.final_future,
            search_interval=20,
            time_between_queries=time_between_queries,
        )

        # Optionally start searching for information straight away
        daemon.start()

        try:
            # Create an instance of the Filter
            fltr = Filter.from_kwargs(label="den")

            # This returns the devices with whatever information they currently have
            async for device in daemon.serials(fltr):
                print(device.serial)

            # This returns devices after first getting all the information
            async for device in daemon.info(fltr):
                print(device.serial)
                print(device.info)
        finally:
            await daemon.finish()

The daemon takes in the following arguments:

limit - default 30
    This is the limit of inflight messages sent by the daemon. You can pass in
    an ``asyncio.Semaphore`` or a number and a Semaphore will be made for you.

finder - optional
    The finder object that does all the hard work. If one is not supplied then
    one is made for you

forget_after - default 30
    The number of seconds since a device is last discovered before we forget
    it ever existed

final_future - defaults to the final_future on the sender
    A future that when cancelled will shut down the daemon.

search_interval - default 20
    The number of seconds between each discovery

time_between_queries - optional
    A dictionary of refresh times for the different points of information the
    device finder looks for.

    By default it is::

        {"LIGHT_STATE": 10, "VERSION": None, "FIRMWARE": 300, "GROUP": 60, "LOCATION": 60}

    The ``None`` value for ``VERSION`` means the version information is never
    asked for again. The numbers in the rest of them is the minimum number of
    seconds since getting a result before it asks for an updated value.

The daemon will then sit there and keep discovering devices and asking those
devices questions to update their state. It tries it's best to send the least
amount of packets on the network as possible.
