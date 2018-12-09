.. _script_mechanism:

The Script Mechanism
====================

Once you have your target object, you interact with your lights by creating a
"script" with the messages you want to send to your devices and running that
against the serials of your devices:

.. code-block:: python

    from photons_messages import DeviceMessages

    script = target.script(DeviceMessages.GetPower())

    async for pkt, addr, sent_to in script.run_with(["d073d5000000", "d073d5000001"]):
        if pkt | DeviceMessages.StatePower:
            print(pkt.serial, pkt.level)

What this has done is taken the ``GetPower`` messages and made a copy for our
two serials and added the necessary ``source`` and ``sequence_id`` properties;
and then sent those messages to our devices and got back ``StatePower`` messages.

Photons knows that the returned ``pkt`` objects are for our messages because
they have the same ``target``, ``source`` and ``sequence_id`` of the messages
that were sent.

The return of ``run_with`` is a list of ``[(pkt, addr, sent_to), ...)]`` where
``pkt`` is the Packet object representing the packet the device sent back; ``addr``
is a tuple of the ip address and port of the device; and ``sent_to`` is the
address that was sent to (i.e. the broadcast address if the message was broadcast,
or the ip of the device if it was unicast).

This mechanism is responsible for timeouts and retries, which are configured by
options to ``run_with``.

For example, the lan target ``run_with`` takes in:

.. automethod:: photons_transport.target.item.TransportItem.run_with
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

The AFR
-------

This mechanism has the idea of the ``afr`` object (args for run) which is where
we essentially store a context for the run. For our lan target it's main function
is storing the ip addresses of our serials.

When you do a ``run_with`` without specifying the ``afr``, it will essentially do:

.. code-block:: python

    try:
        afr = await target.args_for_run()
        await script.run_with_all([serial], afr)
    finally:
        await target.close_args_for_run(afr)

You can create an ``afr`` and pass it in yourself by running ``args_for_run`` and
``close_args_for_run`` yourself, or you can use the ``session()`` context manager
on the target.

.. code-block:: python
    
    async with target.session() as afr:
        script.run_with([serial1, serial2], afr)
        script2.run_with([serial2], afr)

This will mean that multiple ``run_with`` don't have to search for the devices
on every run.

run_with vs run_with_all
------------------------

The ``run_with`` function on a lan target is an async iterator and so you call
it like so:

.. code-block:: python
    
    async for pkt, addr, sent_to in script.run_with(references):
        ...

Note that this will raise any errors after giving back any results we got from
the call.

If you don't care about the replies or you want all the replies in one go, then
you can use ``run_with_all`` which is equivalent to the following:

.. code-block:: python

    async def run_with_all(*args, **kwargs):
        """Do a run_with but don't complete till all messages have completed"""
        results = []
        try:
            async for info in script.run_with(*args, **kwargs):
                results.append(info)
        except RunErrors as error:
            raise BadRunWithResults(results=results, _errors=error.errors)
        except Exception as error:
            raise BadRunWithResults(results=results, _errors=[error])
        else:
            return results
