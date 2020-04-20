.. _packets:

LIFX Binary Protocol
====================

To interact with LIFX devices you create packets and send those. A packet is
a string of bytes that contains header and payload information. In Photons you
create these using the objects listed below. For example
:ref:`DeviceMessages.SetPower` can be made by saying:

.. code-block:: python

    from photons_messages import DeviceMessages


    # An instruction that says to turn the device on
    get_power = DeviceMessages.SetPower(level=65535)

The only information in the header that you need to care about are:

target
    If you set this then that packet will only be sent to that particular device.

    .. code-block:: python

        # Send to d073d5000001 regardless of the reference you use
        # when you send the message
        DeviceMessages.SetPower(level=0, target="d073d5000001")

ack_required
    A boolean that tells the device to send back an acknowledgment and for
    Photons to then expect and wait for one:

    .. code-block:: python

        # Note that ack_required is True by default
        DeviceMessages.GetPower(level=0, ack_required=False)

res_required
    A boolean that tells the device to send back a response and for Photons to
    then expect and wait for one:

    .. code-block:: python

        # Note that res_required is True by default
        DeviceMessages.SetPower(level=0, res_required=False)

The rest of the keyword arguments to the packet are related to the payload of
the packet. Many messages have defaults and transformations for these fields.

.. note:: You can find a definition of the packets in this github
    `repository <https://github.com/LIFX/public-protocol>`_ and explanations
    on the LAN `documentation <https://lan.developer.lifx.com/>`_.

Once you have one of these packet objects you can access fields like it's a
dictionary or like it's an object:

.. code-block:: python

    msg = DeviceMessages.SetPower(level=65535)
    assert msg.level == 65535
    assert msg["level"] == "65535"

And you can change values the same way:

.. code-block:: python

    msg = DeviceMessages.SetPower(level=65535)
    msg["level"] = 0
    msg.level = 0

Some fields have transformations. For example ``duration`` on a
:ref:`LightSetPower <LightMessages.SetLightPower>`
is measured in milliseconds on the device, but I find it easier to specify it
in seconds instead. And so Photons will take the value you provide and times it
by ``1000`` to make it milliseconds. The value on the object is actually stored
using the value that ends up in the binary packet and when you access that value,
the opposite transformation is done to turn it back into seconds.

.. code-block:: python

    msg = LightMessagse.SetLightPower(level=0, duration=20)
    assert msg.duration == 20
    assert msg.actual("duration") == 20000

.. show_packets::
