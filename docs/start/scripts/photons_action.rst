.. _photons_action:

Registering a Photons action
============================

All the tasks available to the Photons ``lifx`` program are actions that
are registered in one of the Photons modules. An action is a
function that takes in objects that represent the arguments provided
on the command line.

For example, the ``power_toggle`` action is defined as:

.. code-block:: python

    from photons_app.actions import an_action

    from photons_control.transform import PowerToggle


    @an_action(needs_target=True, special_reference=True)
    async def power_toggle(collector, target, reference, artifact, **kwargs):
        """
        Toggle the power of devices.

        ``target:power_toggle match:group_label=kitchen -- '{"duration": 2}'``

        It takes in a ``duration`` field that is the seconds of the duration.
        This defaults to 1 second.
        """
        extra = collector.photons_app.extra_as_json
        msg = PowerToggle(**extra)
        await target.send(msg, reference)

This definition is detailed as follows:

* :ref:`an_action <an_action>` takes in a few arguments

  * ``needs_reference=True`` means Photons throws an error if the ``<reference>``
    argument is not specified
  * ``special_reference=True`` means the ``reference`` variable provided must
    be is a :ref:`Special Reference <cli_references>`
  * ``needs_target=True`` means a ``<target>`` must be specified.

* The :ref:`collector <collector_root>` is the entry point to all functionality
  registered by the Photons modules.
* The ``target`` is the object that :ref:`sends messages <interacting_root>`.
  The ``artifact`` (which is not used above) is the last argument
  given on the command line.
* The JSON options string provided on the command line is available
  as the ``collector.photons_app.extra_as_json`` attribute.
* All arguments to an action must be provided as keyword arguments. If
  you do not specify a keyword, the unused arguments will be consumed by
  the ``**kwargs`` argument.

Create a script that registers and runs an action:

.. code-block:: python

    from photons_app.actions import an_action

    from photons_messages import DeviceMessages


    @an_action(needs_target=True, special_reference=True)
    async def display_label(collector, target, reference, **kwargs):
        async for pkt in target.send(DeviceMessages.GetLabel(), reference):
            print(f"{pkt.serial}: {pkt.label}")

    if __name__ == "__main__":
        __import__("photons_core").run_cli('lan:display_label {@:1:}')

The action has the same command-line options available as the ``lifx`` utility,
including the :ref:`references <cli_references>`::

    $ python my_script.py match:group_name=kitchen --silent


run_cli
-------

The ``run_cli`` function takes either a formatted string of environment
variables and ``sys.argv`` values or a list of manually specified arguments.

For example, this:

.. code-block:: python

    __import__("photons_core").run_cli("{TRANSPORT_TARGET|lan:env}:{@:1} {@:2:}")

Is the same as this:

.. code-block:: python

    import sys
    import os

    target = os.environ.get("TRANSPORT_TARGET", "lan")
    __import__("photons_core").run_cli([f"{transport}:{sys.argv[1]}"] + sys.argv[2:])

An environment variable is mandatory if a default is not provided:

.. code-block:: python

    __import__("photons_core").run_cli("{TRANSPORT_TARGET:env}:{@:1} {@:2:}")

.. _an_action:

The ``an_action`` decorator
---------------------------

.. autoclass:: photons_app.actions.an_action
