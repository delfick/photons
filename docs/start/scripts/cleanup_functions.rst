.. _cleanup_functions:

Cleanup Functions
=================

The ``photons_app`` object on the collector has an array on it called ``cleaners``.

You can add async functions to this array and they will be run as part of
shutdown.

For example:

.. code-block:: python

    from photons_app.actions import an_action


    @an_action(needs_target=True)
    async def run_the_thing(collector, target, **kwargs):
        thing = start_my_thing()

        async def shutdown_the_thing():
            await thing.shutdown()

        collector.photons_app.cleaners.append(shut_down_the_thing)

        await thing.run(target)


    if __name__ == "__main__":
        __import__("photons_core").run_cli("lan:run_the_thing {@:1:}")

This is useful if you have many items to setup and you don't want to have a
bunch of nested context managers or try..finally blocks.
