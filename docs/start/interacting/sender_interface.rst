.. _sender_interface:

The Sender Interface
====================

Once you have a ``sender`` object that you create from a ``target``, you can
start sending messages:

.. code-block:: python

    from photons_messages import DeviceMessages


    async def my_action(target, reference):
        async with target.session() as sender:
            await sender(DeviceMessages.SetPower(level=0), reference)

        # Or if you don't want to create a sender
        await target.send(DeviceMessages.SetPower(level=0), reference)

Both ``sender`` and ``target.send`` take in the same options, a ``message`` to
send, a ``reference`` to send that message to, and a number of keyword
arguments.

The ``message`` can be a :ref:`packet <packets>`, a list of them, or a
:ref:`special message object <special_message_objects>`. If you don't specify
a reference, we'll default to ``None``. This works if you set ``broadcast=True``
or if the message you are sending already has a serial set on it.

The following are the keyword arguments available to you:

broadcast (default False)
    Whether we are broadcasting these packets or just uni-casting directly
    to each device. If this is set to a string, then that will be used as an
    IP address to broadcast to (e.g. ``"192.168.0.255"``).

find_timeout (default 20) - (seconds)
    Timeout for finding devices that have not already been discovered.

connect_timeout (default 10) - (seconds)
    Timeout for connecting to devices. Note that with the default LAN target,
    there is no connection required because UDP is connectionless, so it's
    unlikely this option will have an affect for you.

message_timeout (default 10) - (seconds)
    A per message timeout for receiving replies for that message. We have this
    instead of a overall timeout because it's possible to throttle the rate
    of sending messages.

error_catcher (default None)
    When you send messages, any errors (usually only Timeout Errors) will raise
    an exception once you have received all reply packets at the point you
    are using the sender:

    .. code-block:: python

        from photons_app.special import FoundSerials

        from photons_messages import DeviceMessages


        async def my_action(target):
            async with target.session() as sender:
                try:
                    async for pkt in sender(DeviceMessages.GetPower(), FoundSerials()):
                        print(pkt)
                except:
                    # This will only happen once all the reply packets above have been
                    # received and is likely just ``photons_app.errors.TimedOut`` or
                    # ``photons_app.errors.RunErrors`` with an ``errors`` attribute
                    # containing the multiple errors that were raised.

    Or if you're awaiting for all the packets:

    .. code-block:: python

        from photons_app.special import FoundSerials

        from photons_messages import DeviceMessages


        async def my_action(target):
            async with target.session() as sender:
                try:
                    pkts = await sender(DeviceMessages.GetPower(), FoundSerials()):
                except:
                    # This will only happen once you have all the reply packets
                    # This will always be a ``photons_app.errors.BadRunWithResults``
                    # and you'll find a list of errors on the ``errors`` attribute
                    # and any pkts that you would have received on
                    # ``error.kwargs["results"]``

    Catching errors this way can be quite annoying, so a better way to handle
    errors is to pass in an ``error_catcher`` for consuming those errors and
    avoiding the need for a ``try..except`` block.

    This ``error_catcher`` can either be a list that errors will be append
    to; or a function ``def error_catcher(e)`` that takes in the exception
    every time one occurs:

    .. code-block:: python

        from photons_app.errors import TimedOut

        from photons_messages import DeviceMessages


        async def my_action(target, reference):
            def errors(e):
                assert isinstance(e, TimedOut)

            async with target.session() as sender:
                await sender(DeviceMessages.SetPower(level=0), reference, error_catcher=errors)


no_retry - (default False)
    If ``True`` then the packets being sent will have no automatic retry.
    This defaults to ``False`` and retry rates are determined by the target
    you are using. When you create a :ref:`packet <packets>` to send you have
    two flags for saying what kind of response you want. If you have
    ``ack_required=True`` then you are saying you expect to receive an
    ``Acknowledgement`` packet. And ``res_required=True`` says you expect
    to receive a response packet. If neither of these are set, then photons
    will never retry that packet, otherwise Photons will retry sending the packet
    until it has the appropriate response given those flags.

require_all_devices - (default False)
    If this is ``True`` then we will not send any packets if we can't find
    all the devices we want to send packets to within the ``find_timeout``.

limit - (default 30)
    This argument is used as an async context manager used to limit inflight
    packets. So for each packet, we do

    .. code-block:: python

        async with limit:
            send_and_wait_for_reply(packet)

    For example, an ``asyncio.Semaphore(30)``

    If you specify this option as an integer, then Photons will create an
    ``asyncio.Semaphore`` using that value for you.

Receiving Packets
-----------------

The LIFX protocol has triplets of messages. A ``Get`` a ``Set`` and a ``State``.
For example :ref:`GetPower <DeviceMessages.GetPower>`,
:ref:`SetPower <DeviceMessages.SetPower>` and
:ref:`StatePower <DeviceMessages.StatePower>`. Some messages only have a ``Get``
and a ``State`` and there's only one message that breaks the rule
(``EchoRequest`` and ``EchoResponse``).

The ``Get`` will ask the information to give you it's current state and the
device will give back a ``State`` response. A ``Set`` will tell the device to
make some change and then the device will send back a ``State`` message.

If you set ``ack_required=True`` (the default) then when the device gets that
packet it will send back an ``Acknowledgement`` packet before the response. And
a response will be sent back if you specify ``res_required=True``
(also the default).

The general rule with ``State`` packets is if the ``Set`` changes the visual
appearance of the device, then you'll likely get back the state before the
change, otherwise you'll likely get the new state.  For this reason it's not
useful to have ``res_required=True`` and it's likely you just want
``ack_required=True``. If you have both set to ``False`` then Photons has no
way of knowing if the packet got to the device and won't attempt to do any
retries.

The ``State`` packet from a ``Get`` packet will always be the current state of
the device.

Some packets like ``GetService`` or
:ref:`SetColorZones <MultizoneMessages.SetColorZones>`
can potentially return multiple packets in reply. Photons knows about these
packets and will determine when the device has returned all the packets for you.
Photons will not return any of the packets until all of them have been received
in case it needs to retry the original packet.

When you send a message you can either wait for all the packets to return to
you and get back a list of responses, or you can asynchronously stream the
replies as they are received:

.. code-block:: python

    from photons_messages import DeviceMessages


    async def my_action(target):
        async with target.session() as sender:
            # Wait for all replies
            pkts = await sender(DeviceMessages.GetPower(), reference)

            # Stream replies
            async for pkt in sender(DeviceMessages.GetPower(), reference):
                print(pkt)

When you get back packets it's a good idea to check the packet is what you
expect before you access anything on it. So say we send a
:ref:`GetPower <DeviceMessages.GetPower>` and a
:ref:`GetLabel <DeviceMessages.GetLabel>` then we can do the following:

.. code-block:: python

    from photons_messages import DeviceMessages


    async def my_action(target):
        async with target.session() as sender:
            get_power = DeviceMessages.GetPower()
            get_label = DeviceMessages.GetLabel()

            async for pkt in sender([get_power, get_label], reference):
                if pkt | DeviceMessages.StatePower:
                    print(f"Device {pkt.serial} has power level of {pkt.level}")
                elif pkt | DeviceMessages.StateLabel:
                    print(f("Device {pkt.serial} has a label of {pkt.label}")

.. note:: If you want power and label, it's better to send a single
    :ref:`GetColor <LightMessages.GetColor>` as that returns a
    :ref:`LightState <LightMessages.LightState>` message that has hsbk, power
    and label on it. You can also use the :ref:`plan_state` plan on the
    :ref:`gatherer <gatherer_interface>`.

When you receive ``pkt`` replies, there is some meta information on them you can
access that tells you the IP address of the device that sent that reply, as
well as the original packet that was sent to get this response:

.. code-block:: python

    from photons_messages import DeviceMessages


    async def my_action(target):
        async with target.session() as sender:
            async for pkt in sender(DeviceMessages.GetPower(), reference):
                if pkt | DeviceMessages.StatePower:
                    # This will be ``("192.168.1.4", 56700)``
                    ip = pkt.Information.remote_addr 

                    # This will be the GetPower we created in the first place
                    original_packet_name = pkt.Information.sender_message.__class__.__name__

                    print(f"{pkt.serial} responded from {ip} after I sent a {original_packet_name}")

.. _sender_discovery:

Discovery
---------

If you don't :ref:`hard code serials <discovery>` then devices need to be
discovered on the network. Photons does this for you, but essentially the way
it works is we broadcast a ``GetService`` onto the network and look at the
``StateService`` messages that come back to us.

You can just tell the ``sender`` to send to some serials for example and it'll
handle discovering them for you. And then the ``sender`` will hold onto that
information so future sending will already know where the lights are:

.. code-block:: python

    # If the sender doesn't already know the ips of these devices, it'll
    # discover them first for you.
    await sender(DeviceMessages.GetPower(), ["d073d5000001", "d073d5000002"])

If you have a :ref:`special reference <special_reference_objects>` then you
can use use this to get back the ``found`` information (this holds onto a map
of serials to transport objects) and a list of ``serials``:

.. code-block:: python

    from photons_app.special import HardCodedSerials

    
    async def my_action(target):
        reference = HardCodedSerials(["d073d5000001", "d073d5000002"])

        async with target.session() as sender:
            found, serials = await reference.find(sender, timeout=5)

            # Ask the reference to raise a ``photons_app.errors.DevicesNotFound ``
            # exception if some of our devices couldn't be found
            reference.raise_on_missing(found)

            assert serials == ["d073d5000001", "d073d5000002"]

This is useful if you use ``FoundSerials`` or the ``DeviceFinder``. For example:

.. code-block:: python

    from photons_control.device_finder import DeviceFinder


    async def my_action(target):
        reference = DeviceFinder.from_options(group_name="kitchen")

        async with target.session() as sender:
            found, serials = await reference.find(sender, timeout=5)
            reference.raise_on_missing(found)

            # serials is all the lights that are in the "kitchen" group
            print(serials)

Note that a special reference will hold onto the information it discovers, so
if you want to do a search again, you need to call ``reset()`` on it:

.. code-block:: python

    from photons_app.special import FoundSerials


    async def my_action(target):
        reference = FoundSerials()

        async with target.session() as sender:
            found, serials = await reference.find(sender, timeout=5)
            reference.raise_on_missing(found)
            # serials is all the lights that are on the network
            print(serials)

            # reset the reference so that it does the search again
            reference.reset()

            # If we didn't reset the following would do nothing and return
            # what it found last time.
            found, serials = await reference.find(sender, timeout=5)
            reference.raise_on_missing(found)
            print(serials)
