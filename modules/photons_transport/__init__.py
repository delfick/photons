"""
This module is responsible for determining how to get bytes to and from devices.

It contains targets which know how to communicate with devices in a particular
way. You use these targets to create one or more sessions, which each have one
or more connections to your devices that it uses to send a receive messages.
"""

from photons_transport.retry_options import RetryTicker, Gaps
from photons_app.errors import RunErrors, PhotonsAppError
from photons_transport.errors import StopPacketStream
from photons_app import helpers as hp

from contextlib import contextmanager
import logging
import asyncio

log = logging.getLogger("photons_transport")


@contextmanager
def catch_errors(error_catcher=None):
    do_raise = error_catcher is None
    error_catcher = [] if do_raise else error_catcher

    try:
        yield error_catcher
    except asyncio.CancelledError:
        raise
    except StopPacketStream:
        pass
    except Exception as error:
        if not isinstance(error, PhotonsAppError):
            log.exception(error)
        hp.add_error(error_catcher, error)

    if not do_raise:
        return

    error_catcher = list(set(error_catcher))

    if len(error_catcher) == 1:
        raise error_catcher[0]

    if error_catcher:
        raise RunErrors(_errors=error_catcher)


__all__ = ["RetryTicker", "Gaps", "catch_errors"]
