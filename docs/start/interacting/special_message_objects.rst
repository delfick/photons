.. _special_message_objects:

Special Message objects
=======================

Using the :ref:`sender <sender_interface>` we can send individual
:ref:`packets <packets>` but sometimes we want to have more control over the
order and timing of packets that is otherwise difficult and tedious to do.

For this purpose, you can provide the ``sender`` an object that makes it easy
to make these kind of decisions.

For example, an object that toggles the power of lights:

.. code-block:: python

    from photons_messages import DeviceMessages, LightMessages
    from photons_control.script import FromGenerator


    async def toggle(reference, sender, **kwargs):
        get_power = DeviceMessages.GetPower()

        async for pkt in sender(get_power, reference, **kwargs):
            if pkt | DeviceMessages.StatePower:
                if pkt.level == 0:
                    yield LightMessages.SetLightPower(
                        level=65535, res_required=False, target=pkt.serial
                    )

                else:
                    yield LightMessages.SetLightPower(
                        level=0, res_required=False, target=pkt.serial
                    )


    async def my_action(target, reference):
        async with target.session() as sender:
            ToggleLights = FromGenerator(toggle)
            await sender(ToggleLights, reference)

Here we're using the
:class:`FromGenerator <photons_control.script.FromGenerator>` helper to turn an
async generator into a message object. What this means is that every message
that is yielded from will be sent to devices. See :ref:`below <FromGenerator>`
for more details about how this mechanism works.

There exists a few message objects you can use straight away. For example, if
I wanted to repeatedly send certain messages forever I could do something like:

.. code-block:: python

    from photons_messages import DeviceMessages
    from photons_control.script import Repeater


    async def my_action(target, reference):
        get_power = DeviceMessages.GetPower()
        get_group = DeviceMessages.GetGroup()

        def errors(e):
            print(e)

        msg = Repeater([get_power, get_group], min_loop_time=5)

        async for pkt in target.send(msg, reference, error_catcher=errors, message_timeout=3):
            if pkt | DeviceMessages.StatePower:
                power_state = "off" if pkt.level == 0 else "on"
                print(f"{pkt.serial} is {power_state}")

            elif pkt | DeviceMessages.StateGroup:
                print(f"{pkt.serial} is in the {pkt.label} group")

Here our ``msg`` object will keep asking the devices for ``power`` and ``group``
until the program is stopped. The ``Repeater`` takes in a couple options, and
here we're using the ``min_loop_time`` time to say if we get replies before
it's been 5 seconds, then wait the remaining time before sending the messages
again.

You can even combine special messages. So say I want to keep toggling my
lights forever, I can use our ``ToggleLights`` msg above with the ``Repeater``:

.. code-block:: python

    from photons_control.script import Repeater, FromGenerator


    async def toggle(reference, sender, **kwargs):
        ....

    async def my_action(target, reference):
        def errors(e):
            print(e)

        ToggleLights = FromGenerator(toggle)
        msg = Repeater(ToggleLights, min_loop_time=5)
        await target.send(msg, reference, error_catcher=errors, message_timeout=3)

You can even do this without making your own toggle function!

.. code-block:: python

    from photons_control.transform import PowerToggle
    from photons_control.script import Repeater


    async def my_action(target, reference):
        def errors(e):
            print(e)

        msg = Repeater(PowerToggle(), min_loop_time=5)
        await target.send(msg, reference, error_catcher=errors, message_timeout=3)

Existing message objects
------------------------

.. autofunction:: photons_control.script.Repeater

.. autofunction:: photons_control.script.Pipeline

.. autofunction:: photons_control.transform.PowerToggle

.. autofunction:: photons_control.transform.PowerToggleGroup

.. autofunction:: photons_control.multizone.SetZones

.. autofunction:: photons_control.multizone.SetZonesEffect

.. autofunction:: photons_control.tile.SetTileEffect

.. autoclass:: photons_control.transform.Transformer

.. autoclass:: photons_canvas.theme.ApplyTheme

.. _FromGenerator:

Making your own message objects
-------------------------------

To make your own message objects you use the
:class:`FromGenerater <photons_control.script.FromGenerator>` helper mentioned
below, or the related helper ``photons_control.script.FromGeneratorPerSerial``.

``FromGeneratorPerSerial`` works exactly like
:class:`FromGenerater <photons_control.script.FromGenerator>` except that the
``reference`` passed in will be each individual serial and the messages you
yield will automatically be told to send to that serial.

.. autoclass:: photons_control.script.FromGenerator
