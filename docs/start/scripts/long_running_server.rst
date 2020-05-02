.. _long_running_server:

Creating a long-running server
==============================

Using a registered :ref:`Photons action <photons_action>` or calling the
``collector.run_coro_as_main`` function provides a ``graceful_final_future``
that tells Photons to stop the script prior to running any cleanup tasks.

Normal shutdown logic cancels the main task before everything else is shut down
which can result in resources used by a long-running process being closed before
the process can gracefully shut down.

Ensure the task will shut itself down if the graceful future is resolved, then
call the task like so:

.. code-block:: python

    from photons_app.errors import ApplicationCancelled, ApplicationStopped


    with collector.photons_app.using_graceful_future() as final_future:
        try:
            await start_my_server_in_the_background()
            await final_future
        except ApplicationStopped:
            log.info("Application received SIGTERM.")
        except ApplicationCancelled:
            log.info("User ctrl-c'd the program")
