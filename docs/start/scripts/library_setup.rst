.. _library_setup:

Using the library_setup function
================================

If you want to integrate Photons with your existing script and/or have control
over the command line arguments, then you can use the ``library_setup`` function
to start Photons.

For example:

.. code-block:: python

    from photons_app.executor import library_setup

    from photons_messages import DeviceMessages

    import asyncio


    async def get_label(collector):
        lan_target = collector.resolve_target("lan")
        reference = collector.reference_object("_")

        async for pkt in lan_target.send(DeviceMessages.GetLabel(), reference):
            print(f"{pkt.serial}: {pkt.label}")


    if __name__ == "__main__":
        loop = asyncio.new_event_loop()
        collector = library_setup()
        try:
            loop.run_until_complete(get_label(collector))
        finally:
            loop.run_until_complete(collector.stop_photons_app())
            loop.close()

If you are only doing Photons work in your script, then you can get the
collector to create the asyncio event loop and do cleanup for you.

.. code-block:: python

    from photons_app.executor import library_setup

    from photons_messages import DeviceMessages


    async def get_label(collector):
        lan_target = collector.resolve_target("lan")
        reference = collector.reference_object("_")

        async for pkt in lan_target.send(DeviceMessages.GetLabel(), reference):
            print(f"{pkt.serial}: {pkt.label}")


    if __name__ == "__main__":
        collector = library_setup()
        collector.run_coro_as_main(get_label(collector))

An example of using ``argparse`` to specify options on the command line may
look like:

.. code-block:: python

    from photons_app.executor import library_setup

    from photons_messages import DeviceMessages

    import argparse


    async def get_label(collector):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--target", choices=[collector.configuration["target_register"].targets.keys()]
        )
        parser.add_argument("--reference", default="_")
        args = parser.parse_args()

        lan_target = collector.resolve_target(args.target)
        reference = collector.reference_object(args.reference)

        async for pkt in lan_target.send(DeviceMessages.GetLabel(), reference):
            print(f"{pkt.serial}: {pkt.label}")


    if __name__ == "__main__":
        collector = library_setup()
        collector.run_coro_as_main(get_label(collector))
