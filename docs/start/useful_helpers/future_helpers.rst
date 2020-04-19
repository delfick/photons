.. _future_helpers:

Working with Async code
=======================

Photons provides a number of utilities for working with Python async code. These
are in the ``photons_app.helpers`` module. It is a Photons convention to import
this module with the alias ``hp`` and access functionality from that:

.. code-block:: python

    from photons_app import helpers as hp


    async def my_coroutine():
        pass

    task = hp.async_as_background(my_coroutine())

Making tasks
------------

These functions are for turning coroutines into tasks. In asyncio Python a
coroutine isn't put onto the loop until it's either turned into a task or
awaited on.

.. autofunction:: photons_app.helpers.async_as_normal

.. autofunction:: photons_app.helpers.async_as_background

.. autofunction:: photons_app.helpers.async_with_timeout

Future callbacks
----------------

Futures and tasks in asyncio Python can be given a callback that is executed
when that future or task is completed.

.. autofunction:: photons_app.helpers.reporter

.. autofunction:: photons_app.helpers.silent_reporter

.. autofunction:: photons_app.helpers.transfer_result

We can also tell if a future or task already has a particular function as a
callback.

.. autofunction:: photons_app.helpers.fut_has_callback

Custom Future classes
---------------------

Photons provides some classes that behave like Futures, but have additional
functionality.

.. autoclass:: photons_app.helpers.ResettableFuture

.. autoclass:: photons_app.helpers.ChildOfFuture

Objects for doing async work
----------------------------

.. autoclass:: photons_app.helpers.ATicker

.. autofunction:: photons_app.helpers.tick

.. autoclass:: photons_app.helpers.TaskHolder

.. autoclass:: photons_app.helpers.ResultStreamer

.. autoclass:: photons_app.helpers.ThreadToAsyncQueue
