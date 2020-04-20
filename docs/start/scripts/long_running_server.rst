.. _long_running_server:

Making a long running server
============================

As long as you are using a :ref:`photons action <photons_action>` or using the
``collector.run_coro_as_main`` function, then you have available to you a
``graceful_final_future`` that lets you tell Photons that you want to stop
your script before it shuts everything down.

In normal shutdown logic the main task is cancelled before everything is shut
down but this can mean that resources used by your long running process may be
closed before you have a chance to gracefully shut down.

So as long as your task will shutdown by itself if the graceful future is
resolved, then you can say this:

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
