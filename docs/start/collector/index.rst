.. _collector_root:

The Collector
=============

When you start photons you are given a ``collector`` object. This is the entry
point to photons and is responsible for reading configuration and creating
everything you need to get you going.

It has a few things on it you'll find useful:

configuration
    This is a dictionary like object that contains all the configuration and
    objects created by photons. More about this is explained
    :ref:`below <collector_configuration>`

``run_coro_as_main(coro)``
    Used to run a coroutine as the main photons task. This function will
    handle setting everything up for you and cleanly shutting things down
    when the program finishes or is stopped. See :ref:`library_setup`.

photons_app
    This object has many things on it, but the few you'll find most useful is:

    ``using_graceful_future()``
        A context manager that yields a graceful future. See
        :ref:`long_running_server` for more information.

    extra
        The string that appears after a ``--``. So say you run
        ``lifx lan:transform -- '{"power": "off"}'`` then ``photons_app.extra``
        will be the string ``'{"power": "off"}'``

    extra_as_json
        A dictionary that is created by ``json.loads(self.extra)``. So in the
        example above, ``photons_app.extra_as_json`` will be a python
        dictionary ``{"power": "off"}``.

    final_future
        A future that is cancelled when the application needs to shutdown.

    cleaners
        An array you can add async functions to, that will be called when
        Photons is shut down.

``resolve_target(name)``
    This will return the target with name ``name``.
    See :ref:`configuration_targets` for information on how to create your
    own targets that you can resolve with this function.

``reference_object(reference)``
    This takes in the given :ref:`reference <cli_references>` and returns a
    Special reference object that can be used to discover devices. You may
    also supply it an array of serial numbers
    (i.e. ``["d073d5000001", "d073d5000002"]``) and it'll return an object
    that will try and find those devices. Or you can give it an existing
    Special reference object and it'll just give that back to you.

    See the page on using :ref:`Special Reference <special_reference_objects>`
    for more information on using these objects.

.. _collector_configuration:

The configuration object
------------------------

Photons has the ability to read :ref:`configuration <configuration_root>` from
files and the result of that is a
`merged dictionary <https://delfick-project.readthedocs.io/en/latest/api/option_merge/index.html>`_
That takes all the different files that were loaded and presents them as if
you specified all the options in one file.

This object also has some registered "converters" that are used to transform
values on the object into useful objects.

By default you have available:

``configuration["photons_app"]``
    This is where ``collector.photons_app`` comes from.

``configuration["target_register"]``
    This is the "target register" and holds all the targets in your configuration.
    To use it you say ``configuration["target_register"].resolve("nameoftarget")``
    or you can use the shortcut on the collector,
    ``collector.resolve_target("nameoftarget")``. In your configuration you can
    reference different targets with ``{targets.nameoftarget}``.

``configuration["protocol_register"]``
    This is the register for all the protocol messages. You only need this if
    you're making a target object programmatically, but you can say:

    .. code-block::

        from photons_transport.targets import LanTarget
        from photons_messages import protocol_register


        final_future = "<an asyncio.Future that stops sessions from the target when canceled>"

        my_target = LanTarget.create(
            {"final_future": final_future, "protocol_register": protocol_register},
            {"default_broadcast": "192.168.0.255"},
        )

``configuration["reference_resolver_register"]``
    This object knows how to create a
    :ref:`Special reference <special_reference_objects>` object from a reference,
    ``configuration["reference_resolver_register"].reference_object("d03d75000001")``
    or you can use the shortcut on the collector as mentioned above,
    ``collector.reference_object("d073d5000001")``

You can add your own objects when you use the :ref:`addon_hook <photons_action>`
for example:

.. code-block:: python

    from photons_app.formatter import MergedOptionStringFormatter
    from photons_app.actions import an_action

    from photons_transport.targets.base import Target
    from photons_messages import DeviceMessages

    from delfick_project.norms import dictobj, sb
    from delfick_project.addons import addon_hook


    class Options(dictobj.Spec):
        target = dictobj.Field(format_into=sb.typed(Target), default="{targets.lan}")
        message_timeout = dictobj.Field(sb.integer_spec, default=30)


    @addon_hook(extras=[("lifx.photons", "transport"), ("lifx.photons", "control")])
    def __lifx__(collector, *args, **kwargs):
        collector.register_converters(
            {
                "example_script_options": Options.FieldSpec(
                    formatter=MergedOptionStringFormatter
                )
            }
        )


    @an_action(special_reference=True)
    async def turn_off(collector, reference, **kwargs):
        options = collector.configuration["example_script_options"]
        async with options.target.session() as sender:
            await sender(
                DeviceMessages.SetPower(level=0),
                reference,
                message_timeout=options.message_timeout,
            )


    if __name__ == "__main__":
        __import__("photons_core").run_script("turn_off {@:1:}")

Here, our Options has two attributes: target and message_timeout. ``target`` is
a Target object that defaults to the lan target, and message_timeout is an
integer with a default value of 30.

Then in the ``__lifx__`` hook we say that ``example_script_options`` in your
configuration gets normalised into one of these objects.

So you could say in configuration:

.. code-block:: yaml

    ---

    example_script_options:
      target: "{targets.mytarget}"
      kmessage_timeout: 10

    targets:
      mytarget:
        type: lan
        options:
          default_broadcast: 192.168.0.255

And it'll use you ``mytarget`` target to turn off your lights using a message
timeout of ``10`` seconds.

See
`spec helpers <https://delfick-project.readthedocs.io/en/latest/api/norms/api/spec_base.html>`_
and `the dictobj <https://delfick-project.readthedocs.io/en/latest/api/norms/api/dictobj.html#module-delfick_project.norms.field_spec>`_

You can also make your options mandatory by saying:

.. code-block:: python

    @addon_hook(extras=[("lifx.photons", "transport"), ("lifx.photons", "control")])
    def __lifx__(collector, *args, **kwargs):
        collector.register_converters(
            {
                "example_script_options": sb.required(
                    Options.FieldSpec(formatter=MergedOptionStringFormatter)
                )
            }
        )

You can then run your script by saying something like ``python turn_off.py`` to
turn off all your lights or ``python turn_off.py match:label=den`` to turn off
your light with the label of ``den``.
