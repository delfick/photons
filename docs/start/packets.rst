.. _packets:

Packets
=======

LIFX devices speak a binary protocol of packets and photons provides the ability
to pack and unpack these packets via ``photons_protocol``.

The information that is used to understand the different messages is kept in the
``protocol_register`` object, which is an instance of
``photons_app.registers.ProtocolRegister``.

If you use the module system of photons then one of these will be available and
filled out via ``collector.configuration["protocol_register"]``.

Otherwise, just import the default one from ``photons_messages.protocol_register``

Or you can create a new one yourself.

.. code-block:: python

    from photons_messages import DiscoveryMessages, ColourMessages, LIFXPacket

    collector.configuration["protocol_register"].add(1024, LIFXPacket)
    collector.configuration["protocol_register"].message_register(1024).add(ColourMessages)
    collector.configuration["protocol_register"].message_register(1024).add(DiscoveryMessages)

.. note:: If you manually create a target and pass in a protocol register,
 you must register a Messages class that implements message 45 (the acknowledgement
 packet) for the target to be able to tell the difference between acks and replies.

 ``photons_messages.CoreMessages`` is an example of a class that
 defines the Acknowledgement message.

And then you can use the protocol_register to unpack messages you receive from
the bulb.

.. code-block:: python
    
    from photons_protocol.messages import Messages

    data = "580000541cf7e30cd073d514e73300004c4946585632000128cc694f8bdee2146b000000aa2affffcc4cac0d0000000073747269700000000000000000000000000000000000000000000000000000000000000000000000"
    pkt = Messages.unpack(data, protocol_register)
    assert pkt | ColourMessages.LightState
    assert pkt.as_dict() == {
          "frame_address":
          { "ack_required": false
          , "res_required": false
          , "reserved2": "4c4946585632"
          , "reserved3": "00"
          , "sequence": 1
          , "target": "d073d514e7330000"
          }
        , "frame_header":
          { "addressable": true
          , "protocol": 1024
          , "reserved1": "01"
          , "size": 88
          , "source": 216266524
          , "tagged": false
          }
        , "payload":
          { "brightness": 0.29999237048905164
          , "hue": 59.997253376058595
          , "kelvin": 3500
          , "label": "strip"
          , "power": 0
          , "saturation": 1.0
          , "state_reserved1": 0
          , "state_reserved2": 0
          }
        , "protocol_header":
          { "pkt_type": 107
          , "reserved4": 1505009915409321000
          , "reserved5": "0000"
          }
        }

You can then access these groups off the packet or the individual parts directly:

.. code-block:: python

    assert pkt.frame_address == {
          "ack_required": false
        , "res_required": false
        , "reserved2": "4c4946585632"
        , "reserved3": "00"
        , "sequence": 1
        , "target": "d073d514e7330000"
        }

    assert pkt.kelvin == 3500

Note that the definition of the ``LightState`` message in ``photons_colour``
includes transformations for some values in the payload.

.. code-block:: python

    assert pkt.hue == 59.997253376058595
    assert pkt.actual("hue") == 10922

Here accessing the variable returns the transformed value, whereas the ``actual``
function returns us the actual value in the packet.

Another example of a packet with transformed values is ``DeviceMessages.SetLightPower``.
In this packet, the duration is transformed into seconds whereas the packet
defines it in milliseconds:

.. code-block:: python

    from photons_messages import DeviceMessages

    pkt = DeviceMessages.SetLightPower(level=0, duration=10)

    assert pkt.actual("duration") == 10000

Note that when creating a packet from user input it's better to use the ``normalise``
functionality on the class:

.. code-block:: python

    pkt = DeviceMessages.SetLightPower.empty_normalise(**kwargs)

    # Or

    from input_algorithms.meta import Meta
    pkt = DeviceMessages.SetLightPower.normalise(Meta.empty(), kwargs)

Doing this will mean that the values are checked at the instantiation of the
packet and extra options are ignored.
