.. _lifx_photons_library:

Using Photons as a library
==========================

We can use photons more like a library and less like a walled garden by creating
the collector with ``photons_app.executor.library_setup``.

So our script from the :ref:`lifx_photons_script` would look like:

.. code-block:: python

    from photons_app.executor import library_setup
    
    from photons_messages import DeviceMessages

    from delfick_project.logging import setup_logging
    import random

    async def doit(collector):
        target = collector.configuration["target_register"].resolve("lan")

        if random.randrange(0, 10) < 5:
            # Determine the reference somehow, should be a string of the serial (i.e. d073d5000001)
            # Or you can import ``photons_app.special.FoundSerials``
            # and then provide FoundSerials() instead of [reference, reference, ...]
            # Which will search for all the serials it can find and send our messages to them all
            await target.script(DeviceMessages.SetPower(level=0)).run_with_all([reference])

    if __name__ == "__main__":
        # Setup logging handlers
        setup_logging(level=logging.ERROR)

        # Create the collector with default options
        # This will load all the modules under the lifx.photons entry_point namespace
        # You can load only particular entry_points by
        # setting find_all_photons_modules to False
        # and core_modules to a list like ["transport", "color"]
        collector = library_setup()

        # Run our doit function and handle stopping correctly
        collector.run_coro_as_main(doit(collector))

.. autofunction:: photons_app.executor.library_setup
