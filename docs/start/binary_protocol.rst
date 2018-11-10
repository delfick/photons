.. _lifx_binary_protocol:

LIFX Binary protocol
====================

All messages can be found in the ``photons_messages`` module. For example:

.. code-block:: python

    from photons_messages import DeviceMessages

    set_power_message = DeviceMessages.SetPower(level=0)

All messages have the properties on the ``LIFXPacket`` as well as the payload
for that messages.

LIFX Packet
-----------

The packet contains the following three sections as well as the payload which
is specific to each messages:

.. code_for:: photons_messages.frame.FrameHeader

.. code_for:: photons_messages.frame.FrameAddress

.. code_for:: photons_messages.frame.ProtocolHeader

Also if you have a packet object, you can test what type of packet by using the
``|`` operator. For example:

.. code-block:: python

    from photons_messages import DeviceMessages

    set_power = DeviceMessages.SetPower(level=65535)

    assert set_power | DeviceMessages.SetPower

.. lifx_messages::
