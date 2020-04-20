.. _gatherer_interface:

The Gatherer Interface
======================

A common task is to gather information from devices. This can often require
combining multiple points of information. For example to determine if the device
supports extended multizone messages you need both the product id and hardware
version of the device.

To get and combine this information in a way that streams that information
back to you using the :ref:`sender <sender_interface>` API is a little tricky.

To solve this problem, Photons supplies the ``gatherer`` that lets you ask for
``plans`` of information to be resolved.

For example:

.. code-block:: python

    from photons_control.planner import Skip


    async def my_action(target, reference):
        async with target.session() as sender:
            plans = sender.make_plans("capability", "firmware_effects")

            async for serial, name, info in sender.gatherer.gather(plans, reference):
                if name == "capability":
                    print(f"{serial} is a {info['cap'].product.name}")

                elif name == "firmware_effects":
                    if info is Skip:
                        print(f"{serial} doesn't support firmware effects")
                    else:
                        print(f"{serial} is running the effect: {info['type']}")

In this example each device will get one
:ref:`GetVersion <DeviceMessages.GetVersion>`,
:ref:`GetHostFirmware <DeviceMessages.GetHostFirmware>` and for those that
support firmware effects, either a
:ref:`GetMultizoneEffect <MultizoneMessages.GetMultizoneEffect>` or
:ref:`GetTileEffect <TileMessages.GetTileEffect>` and all the information from
those is presented to you in a useful way. Note that both the ``"capability"``
and ``"firmware_effects"`` plans require version information, but the gatherer
makes it so we only ask the device for this information once.

By using :ref:`gather <gatherer.gather>` we will get each plan result as they
come in. The gatherer also gives you
:ref:`gather_per_serial <gatherer.gather_per_serial>` and
:ref:`gather_all <gatherer.gather_all>`.

All the ``gather`` methods take in ``plans``, ``reference`` and ``**kwargs``
where ``kwargs`` are the same keyword arguments you would give the
:ref:`sender <sender_interface>`.

.. _gather_methods:

The gather methods
------------------

There are three methods on the ``sender.gatherer`` that you would use:

.. py:class:: photons_control.planner.gatherer.Gatherer

    .. _gatherer.gather:

    .. automethod:: gather

    .. _gatherer.gather_per_serial:

    .. automethod:: gather_per_serial

    .. _gatherer.gather_all:

    .. automethod:: gather_all

Using Plans
-----------

There are a number of plans that comes with Photons by default. You can either
use these by their name when you use ``make_plans`` function or you
can use your own label with something like ``make_plans(thing=MyThingPlan())``
and then the result from that plan will have the label ``thing``.

For example:

.. code-block:: python

    plans = sender.make_plans("capability", "state", other=MyOtherPlan())

Is the same as saying:

.. code-block:: python

    from photons_control.planner.plans import CapabilityPlan, StatePlan


    plans = sender.make_plans(capability=CapabilityPlan(), state=StatePlan, other=MyOtherPlan())

The first form is convenient, but the second form gives you more control on
what label the plan is given and lets you override the ``refresh`` value of the
plan which says how long it'll take for the data it cares about to refresh and
be asked for again.

Photons comes with some default plans for you to use:

.. show_plans::

Making your own Plans
---------------------

To make your own Plan, you need to inherit from the
:class:`photons_control.planner.Plan` class and fill out some methods.

The simplest plan you can make is:

.. code-block:: python

    from photons_control.planner import Plan, a_plan
    from photons_messages import DeviceMessages


    @a_plan("responds")
    class RespondsPlan(Plan):
        """
        Return whether this device responds to messages
        """

        messages = [DeviceMessages.EchoRequest(echoing=b"can_i_has_response")]

        class Instance(Plan.Instance):
            def process(self, pkt):
                if pkt | DeviceMessages.EchoResponse:
                    if pkt.echoing == b"can_i_has_response":
                        return True

            async def info(self):
                return True

Here we say the plan should send out a single EchoRequest for this device. We
then have an ``Instance`` class that inherits from ``Plan.Instance`` and one of
these is made for every device the Plan is operating on. There are two main
methods on this: ``process`` and ``info``.

The ``process`` method takes in every packet that has been received from the
device, even if this plan didn't send that packet.

You can store whatever information you want on ``self`` and when you have
received enough information you return ``True`` from this method. Once that is
done, the ``info`` method is called to return something useful from this plan.

In our example above, the ``info`` from the plan is a boolean ``True`` if the
device responded to our echo request. If we never get that response back then
this plan will never resolve and not given back in the output from the gather
methods.

You can also depend on other plans:

.. code-block:: python

    from photons_control.planner.plans import CapabilityPlan
    from photons_control.planner import Plan, a_plan, Skip
    from photons_messages import DeviceMessages
    from photons_products import Family


    @a_plan("labels_from_lcm1")
    class LabelsFromLCM1(Plan):
        @property
        def dependant_info(kls):
            return {"c": CapabilityPlan()}

        class Instance(Plan.Instance):
            @property
            def is_lcm1(self):
                return self.deps["c"]["cap"].product.family is Family.LCM1

            @property
            def messages(self):
                if self.is_lcm1:
                    return [DeviceMessages.GetLabel()]
                return Skip

            def process(self, pkt):
                if pkt | DeviceMessages.StateLabel:
                    self.label = pkt.label
                    return True

            async def info(self):
                return self.label

This plan will return the label for any ``LCM1`` devices it finds. If the
device is not an ``LCM1`` then the ``info`` for this plan will be a ``Skip``
object.

The gatherer will make sure all dependencies for the plan are resolved before
this plan is used. If that dependency has any dependencies, then those are
resolve first, and so on.

.. note:: the ``a_plan`` decorator is optional and is only registering this
    plan with a label you can use as a positional argument in the ``make_plans``
    function.

You can look at the
`source code <https://github.com/delfick/photons-core/blob/master/photons_control/planner/plans.py>`_
for examples of plans.

There's quite a few features on the ``Plan`` object:

.. autoclass:: photons_control.planner.Plan(refresh=10, **kwargs)
