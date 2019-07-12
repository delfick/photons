__doc__ = """
This module is responsible for determining how to get bytes to and from devices.

It contains targets which know how to communicate with devices in a particular
way. You use these targets to create one or more sessions, which each have one
or more connections to your devices that it uses to send a receive messages.

Target
------

.. automodule:: photons_transport.targets
    :members:

Session
-------

.. automodule:: photons_transport.session

Transports
----------

.. automodule:: photons_transport.transports

Retry options
-------------

This module also provides a ``RetryOptions`` and ``RetryIterator`` for working
with retry logic.

.. autoclass:: photons_transport.RetryOptions

.. autoclass:: photons_transport.RetryIterator
"""

from photons_transport.retry_options import RetryOptions, RetryIterator
from photons_app.errors import RunErrors
from photons_app import helpers as hp

from contextlib import contextmanager
import asyncio

RetryOptions = RetryOptions
RetryIterator = RetryIterator

@contextmanager
def catch_errors(error_catcher=None):
    do_raise = error_catcher is None
    error_catcher = [] if do_raise else error_catcher

    try:
        yield error_catcher
    except asyncio.CancelledError:
        raise
    except Exception as error:
        hp.add_error(error_catcher, error)

    if not do_raise:
        return

    error_catcher = list(set(error_catcher))

    if len(error_catcher) == 1:
        raise error_catcher[0]

    if error_catcher:
        raise RunErrors(_errors=error_catcher)

__all__ = ["RetryOptions", "RetryIterator", "catch_errors"]
