.. _script_mechanism:

The Script Mechanism
====================

Once you have your target object, you interact with your lights by creating a
"script" with the messages you want to send to your devices and running that
against the serials of your devices:

.. code-block:: python

    from photons_messages import DeviceMessages

    script = target.script(DeviceMessages.GetPower())

    async for pkt, addr, original in script.run_with(["d073d5000000", "d073d5000001"]):
        if pkt | DeviceMessages.StatePower:
            print(pkt.serial, pkt.level)

What this has done is taken the ``GetPower`` messages and made a copy for our
two serials and added the necessary ``source`` and ``sequence_id`` properties;
and then sent those messages to our devices and got back ``StatePower`` messages.

Photons knows that the returned ``pkt`` objects are for our messages because
they have the same ``target``, ``source`` and ``sequence_id`` of the messages
that were sent.

The return of ``run_with`` is a list of ``[(pkt, addr, original), ...)]`` where
``pkt`` is the Packet object representing the packet the device sent back; ``addr``
is a tuple of the ip address and port of the device; and ``original`` is the
original message that was sent.

This mechanism is responsible for timeouts and retries, which are configured by
options to ``run_with``.

For example, the lan target ``run_with`` takes in:

.. automethod:: photons_transport.targets.item.Item.run_with
    :noindex:

Sending multiple packets
------------------------

You can provide a list of messages to ``target.script`` and it will send all of
them for all of the serials specified and collect all the responses.

If you want to make sure they happen in order, then use a
``photons_control.script.Pipeline``. For example:

.. code-block:: python

    from photons_messages import DeviceMessages, LightMessages
    from photons_control.script import Pipeline

    color_no_brightness = LightMessages.SetColor(hue=210, saturation=0.5, brightness=0, kelvin=3500, res_required=False)
    power_on = DeviceMessages.SetPower(level=65535, res_required=False)
    color_with_brightness = LightMessages.SetColor(hue=210, saturation=0.5, brightness=0.8, kelvin=3500, res_required=False)

    pipeline = Pipeline(color_no_brightness, power_on, color_with_brightness)
    script = target.script(pipeline)
    await script.run_with_all([serial1, serials2, serials3])

.. note:: You most likely don't want res_required for Set messages as the device
 will return the state before the message is applied. Note that ack_required
 defaults to True, so photons will still know to retry if we don't get an ack

Inflight limit
--------------

When you call run_with, photons will default to ensuring there's only 30 messages
being sent at any one time. This means for that run_with, the 31st message will
be sent once the first message to get replies does so.

You can change the limit by specifying the limit option. For example, to limit
to only 3 messages being sent at any one time, you could say:

.. code-block:: python

    await sender(msg, reference, limit=3)

You may also specify no limit by passing in limit as None:

.. code-block:: python

    await sender(msg, reference, limit=None)

Or you may share a limit between multiple run_with calls by sharing an
asyncio.Semaphore object. This makes sense if you're doing multiple run_withs
at the same time:

.. code-block:: python

    from photons_app import helpers as hp

    import asyncio

    async def send(limit):
        msg = ...
        await sender(msg, reference, limit=limit)

    limit = asyncio.Semaphore(20)

    ts = [
          hp.async_as_background(send(limit))
        , hp.async_as_background(send(limit))
        ]

    await asyncio.wait(ts)
