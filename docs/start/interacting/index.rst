.. _interacting_root:

Interacting with LIFX devices
=============================

To interact with a LIFX device, you send it packets and potentially receive
replies that you can look at. To do this you need a ``target`` object, some
:ref:`packets <packets>`, or message :ref:`objects <special_message_objects>`
to send; and a ``reference`` that says what devices on your network to send to.

Photons comes with one ``target`` type, which is the ``LanTarget``. This knows
how to send packets using UDP over the LAN. You can see how to get access to
one of these in the :ref:`scripts section <scripts_root>`.

Once you have a ``target``, you create a ``sender`` object, which is essentially
a session. This does discovery for you and holds onto the results of that so
you can send packets multiple times in your program and only have to do
discovery once. If your script only sends one message, then you can send it
directly from the target and it'll create and cleanup a sender for you.

For example, to tell devices to turn off you can say:

.. code-block:: python

    from photons_messages import DeviceMessages


    async def my_action(target, reference):
        async with target.session() as sender:
            await sender(DeviceMessages.SetPower(level=0), reference)

        # Or if you don't want to create a sender
        await target.send(DeviceMessages.SetPower(level=0), reference)

A message can be a single :ref:`packet <packets>`, a list of those, or a
:ref:`special message object <special_message_objects>` that knows how to send
multiple messages.

And a reference can be a single serial (i.e. the string ``"d073d5001337"``, a
list of those serials or a :ref:`special reference <special_reference_objects>`.

You can read more details about :ref:`sender <sender_interface>` and also the
higher level :ref:`Gatherer <gatherer_interface>`.

.. toctree::
    :hidden:
    
    sender_interface
    gatherer_interface
    packets
    special_message_objects
    special_reference_objects
    device_finder
