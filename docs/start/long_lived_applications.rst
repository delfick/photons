Long lived Applications
=======================

In photons you have the ``collector.configuration["photons_app"]`` object that
represents the application. On this object you have ``final_future`` which
represents the end of the program.

So, when your application is stopped it gets cancelled before cleanup is performed
or if your application raises an error, that error is given to the final future.

This means if you wait on the final future, your application can be told when
the program should be stopped.

The problem with waiting on ``final_future`` however is that many resources
rely on this future to know when they should shut down, and so once this future
completes any existing processes in your application may fail because the
resources they are using may be shutting down.

Since version ``0.25.0`` there is a more graceful way of responding to the end
of the program.

.. code-block:: python

    from photons_app.errors import ApplicationStopped, UserQuit

    import asyncio

    with photons_app.using_graceful_future() as final_future:
        try:
            start_my_server()
            await final_future
        except ApplicationStopped:
            # Application got a SIGTERM
        except UserQuit:
            # The user did a ctrl-c
        except asyncio.CancelledError:
            # Something did photons_app.final_future.cancel()
        finally:
            # This is run before final_future is cancelled
            # Unless something already cancelled it!

Here we use a context manager to get a "graceful" future to wait on. This future
will complete and let your program naturally quit before stopping the real
``final_future`` and let resources be cleaned up.

.. note:: this method assumes that your program will quit when this future is
    done, otherwise your program will not ever finish.
