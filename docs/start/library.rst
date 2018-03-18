.. _lifx_photons_library:

Using Photons as a library
==========================

We can use photons more like a library and less like a walled garden by creating
the collector with ``photons_app.executor.library_setup``.

So our script from the :ref:`lifx_photons_script` would look like:

.. code-block:: python

    from photons_app.executor import library_setup
    
    from photons_device_messages import DeviceMessages

    import random

    # Create the collector with default options
    # This will load all the modules under the lifx.photons entry_point namespace
    # You can load only particular entry_points by
    # setting find_all_photons_modules to False
    # and core_modules to a list like ["sockets", "color"]
    collector = library_setup()

    # We can get a uvloop from the photons_app object
    loop = collector.configuration["photons_app"].uvloop

    # Or we can do something like
    # import asyncio
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)

    # Then we get our lan target
    target = collector.configuration["target_register"].resolve("lan")

    async def doit():
        if random.randrange(0, 10) < 5:
            # Determine the reference somehow, should be a string of the serial (i.e. d073d5000001)
            # Or you can import ``photons_app.special.FoundSerials``
            # and then provide FoundSerials() instead of [reference, reference, ...]
            # Which will search for all the serials it can find and send our messages to them all
            await target.script(DeviceMessages.SetPower(level=0)).run_with_all([reference])

    loop.run_until_complete(doit())

.. autofunction:: photons_app.executor.library_setup
