.. _photons_action:

Registering a Photons action
============================

All the Photons CLI commands you can run from the ``lifx`` program are an action
that has been registered in one of the Photons modules. An action is a
function that takes in objects that represent the arguments you gave
on the command line.

So for example, the ``power_toggle`` action looks like:

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

There's a few things to take in here:

* :ref:`an_action <an_action>` takes in a few arguments

  * ``needs_reference=True`` would mean that we complain if the ``<reference>``
    argument is not specified
  * ``special_reference=True`` will mean the ``reference`` variable given to
    you is a :ref:`Special Reference <cli_references>`
  * ``needs_target=True`` says that a ``<target>`` must be specified.

* The :ref:`collector <collector_root>` is the entry point to everything that
  has been registered by the Photons modules.
* The ``target`` is the object you use to :ref:`send messages <interacting_root>`
  with.
* The ``artifact``, while not used in the above example, is that last argument
  given to the command line.
* You can access the json string after the ``--`` on the command line by
  looking at ``collector.photons_app.extra_as_json``.
* All the arguments to the action are provided as keyword arguments, so they
  must be given those names, but you can also not specify them and let the
  ``**kwargs`` consume those you don't use.

To make your own script that uses one of these actions, you create a file that
registers an action and then tells Photons to run that action.

.. code-block:: python

    from photons_app.actions import an_action

    from photons_messages import DeviceMessages


    @an_action(needs_target=True, special_reference=True)
    async def display_label(collector, target, reference, **kwargs):
        async for pkt in target.send(DeviceMessages.GetLabel(), reference):
            print(f"{pkt.serial}: {pkt.label}")


    if __name__ == "__main__":
        __import__("photons_core").run_cli('lan:display_label {@:1:}')

When we run it like a script we will run our ``display_label`` action using the
``lan`` target with any other arguments specified on the command line::

    # The same as running ``lifx lan:display_label --silent``
    # If display_label was defined in a photons module, rather than it's own file
    $ python my_script.py --silent


run_cli
-------

The ``run_cli`` function can either take in a string that lets you format in
environment variables and ``sys.argv`` values or you can pass in a list of
arguments yourself.

For example you can say:

.. code-block:: python

    __import__("photons_core").run_cli("{TRANSPORT_TARGET|lan:env}:{@:1} {@:2:}")

Which is the same as saying:

.. code-block:: python

    import sys
    import os

    target = os.environ.get("TRANSPORT_TARGET", "lan")
    __import__("photons_core").run_cli([f"{transport}:{sys.argv[1]}"] + sys.argv[2:])

You can also specify that an environment variable is required by not specifying
a default. For example:

.. code-block:: python

    __import__("photons_core").run_cli("{TRANSPORT_TARGET:env}:{@:1} {@:2:}")

.. _an_action:

The an_action decorator
-----------------------

.. autoclass:: photons_app.actions.an_action
