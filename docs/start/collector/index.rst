.. _collector_root:

The Collector
=============

Photons creates a ``collector`` object when instantiated. The ``collector``
is responsible for reading configuration and loading all available Photons
module functionality.

The ``collector`` has several useful attributes:

configuration
    This is a dictionary-like object that contains all the
    :ref:`configuration <collector_configuration>` objects created by Photons.

``run_coro_as_main(coro)``
    Runs a co-routine as the main Photons task. Handles initial setup and
    final cleanup when the co-routine ends or the script is stopped.

    See :ref:`library_setup`.

photons_app
    The ``photons_app`` object contains several useful attributes:

    ``using_graceful_future()``
        A context manager that yields a graceful future.
        :ref:`long_running_server` provides more information.

    extra
        The JSON string provided after the ``--`` on the command line.
        For example, the command ``lifx lan:transform -- '{"power": "off"}'``
        results in ``photons_app.extra`` containing the string
        ``'{"power": "off"}'``.

    extra_as_json
        A Python dictionary created from ``json.loads(self.extra)``. Using the
        example above, ``photons_app.extra_as_json`` is the Python
        dictionary ``{"power": "off"}``.

    final_future
        A future that is cancelled when the application needs to shutdown.

    cleaners
        An array of async functions called when Photons shuts down.

``resolve_target(name)``
    This returns the target with name ``name``.
    See :ref:`configuration_targets` for information on how to create
    custom targets that are resolved with this function.

``reference_object(reference)``
    This accepts a :ref:`reference <cli_references>` or an array of serial
    numbers e.g. ``["d073d5000001", "d073d5000002"]`` and it'll return a
    special reference object that discovers the specified devices.

    See the page on using :ref:`special reference objects <special_reference_objects>`
    for more information on using these objects.

.. _collector_configuration:

The configuration object
------------------------

Photons reads :ref:`configuration <configuration_root>` from
files and creates a `merged dictionary <https://delfick-project.readthedocs.io/en/latest/api/option_merge/index.html>`_
of the combined configuration from all specified files.

The configuration object includes several registered converters used to
transform values on the object to make them more useful.

By default, the following attributers are available:

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

You can add your own objects by creating a hook that will be loaded when Photons
started, and then adding your configuration to the collector.

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


    @addon_hook()
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
        __import__("photons_core").run_cli("turn_off {@:1:}")

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

    @addon_hook()
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
