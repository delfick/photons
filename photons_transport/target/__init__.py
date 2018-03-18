"""
A transport is essentially functionality for getting messages as objects and sending
them to devices as binary (or as http) (or as nats messages, etc)

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

.. automodule:: photons_transport.target.target
    :members:

The bridge
----------

.. automodule:: photons_transport.target.bridge

The item
--------

.. automodule:: photons_transport.target.item
    :members:

The waiter
----------

.. automodule:: photons_transport.target.waiter
    :members:

The writer
----------

.. automodule:: photons_transport.target.writer
    :members:
"""
from photons_transport.target.target import TransportTarget
from photons_transport.target.bridge import TransportBridge
from photons_transport.target.item import TransportItem

# Aaaand, make vim be quiet
TransportItem = TransportItem
TransportTarget = TransportTarget
TransportBridge = TransportBridge

