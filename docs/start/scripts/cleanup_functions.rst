.. _cleanup_functions:

Cleanup Functions
=================

The ``photons_app`` object on the :ref:`collector <collector_root>` has an
array of functions called ``cleaners``.

Add an async function to this array to include it when Photons shuts down.

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
        __import__("photons_core").run("lan:run_the_thing {@:1:}")

This is useful if there are many items to setup as it avoids the complexity
of nested context managers or ``try..finally`` code blocks.
