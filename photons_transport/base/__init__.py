"""
A transport is essentially functionality for getting messages as objects and sending
them to devices as binary

We have three concepts here:

TransportItem
    Responsible for formatting the raw messages and writing them to the device

TransportBridge
    Also known as args_for_run or afr, this holds the logic for actually doing
    the writing/reading

TransportTarget
    Responsible for holding onto a references to TransportItem and TransportBridge

    May contain classmethods for common tasks.

The target
----------

.. automodule:: photons_transport.base.target
    :members:

The bridge
----------

.. automodule:: photons_transport.base.bridge

The item
--------

.. automodule:: photons_transport.base.item
    :members:

The waiter
----------

.. automodule:: photons_transport.base.waiter
    :members:

The writer
----------

.. automodule:: photons_transport.base.writer
    :members:

Result
------

.. automodule:: photons_transport.base.result
    :members:

Retry options
-------------

.. automodule:: photons_transport.retry_options
    :members:
"""
from photons_transport.base.target import TransportTarget
from photons_transport.base.bridge import TransportBridge
from photons_transport.base.item import TransportItem

# Aaaand, make vim be quiet
TransportItem = TransportItem
TransportTarget = TransportTarget
TransportBridge = TransportBridge
