.. _photons_action:

Registering a Photons task
==========================

All the tasks available to the Photons ``lifx`` program are registered onto the
``photons_app.tasks.task_register`` object and are responsible for specifying how
we transform instructions from the commandline into objects for use in the task.

For example, the ``power_toggle`` action is defined as:

.. code-block:: python

    from photons_app.tasks import task_register as task

    from photons_control.transform import PowerToggle


    @task
    class power_toggle(task.Task):
        """
        Toggle the power of devices.

        ``target:power_toggle match:group_label=kitchen -- '{"duration": 2}'``

        It takes in a ``duration`` field that is the seconds of the duration. This defaults
        to 1 second.
        """

        target = task.requires_target()
        reference = task.provides_reference(special=True)

        async def execute_task(self, **kwargs):
            extra = self.photons_app.extra_as_json
            msg = PowerToggle(**extra)
            await self.target.send(msg, self.reference)

The tasks seen in the ``lifx`` program are registered when each Photons module
is activated. A standalone script that has it's own tasks can be written using
the ``photons_core.run`` function:

.. code-block:: python

    from photons_app.tasks import task_register as task

    from photons_messages import DeviceMessages


    @task
    class display_label(task.Task):
        """Display the label for specific devices"""

        target = task.requires_target()
        reference = task.provides_reference(special=True)

        async def execute_task(self, **kwargs):
            async for pkt in target.send(DeviceMessages.GetLabel(), reference):
                print(f"{pkt.serial}: {pkt.label}")


    if __name__ == "__main__":
        __import__("photons_core").run('lan:display_label {@:1:}')

The action has the same command-line options available as the ``lifx`` utility,
including the :ref:`references <cli_references>`::

    $ python my_script.py match:group_name=kitchen --silent

The fields on the class uses the data normalisation functionality provided in
`delfick_project.norms <https://delfick-project.readthedocs.io/en/latest/api/norms/index.html>`_.

When the ``lifx`` program creates the task it does the following:

.. code-block:: python

    artifact = collector.photons_app.artifact
    reference = collector.photons_app.reference
    target_name, task_name = collector.photons_app.task_specifier()

    task_register.fill_task(
        collector,
        task_name,
        path="CLI|",
        target=target_name,
        reference=reference,
        artifact=artifact,
    ).run_loop()

So for example if the command was::

    > lifx lan:attr d073d5000001 Color

    # OR
    > lifx --task lan:attr --reference d073d5000001 --artifact Color

Then the ``attr`` task is created with::

    target: "lan"
    artifact: "Color":
    reference: "d073d5000001"

And will have available in the ``meta`` object the
:ref:`Collector <collector_root>` available.

See :ref:`photons_task_class` for more information on how the ``Task``
class works.

photons_core.run
----------------

The ``run`` function takes either a formatted string of environment variables
and ``sys.argv`` values or a list of manually specified arguments.

For example, this:

.. code-block:: python

    __import__("photons_core").run("{TRANSPORT_TARGET|lan:env}:{@:1} {@:2:}")

Is the same as this:

.. code-block:: python

    import sys
    import os

    target = os.environ.get("TRANSPORT_TARGET", "lan")
    __import__("photons_core").run([f"{transport}:{sys.argv[1]}"] + sys.argv[2:])

An environment variable is mandatory if a default is not provided:

.. code-block:: python

    __import__("photons_core").run("{TRANSPORT_TARGET:env}:{@:1} {@:2:}")

By default this will start the core modules, which is likely all that'll ever
be needed. Run can be given ``default_activate=[]`` to make Photons not load any
modules. If there are other Photons modules in the environment, they can be
loaded with ``default_activate=["other_module"]``. Not specifying a
``default_activate`` is equivalent to ``default_activate=["core"]``. Finally
if it's desirable to load all Photons modules found in the environment, then
the special ``__all__`` module can be used.

.. _legacy_actions:

Legacy Function based Actions
-----------------------------

The original way that Photons defined tasks was via functions rather than
classes. This can still be done using either:

.. code-block:: python

    from photons_app.tasks import task_register as task

    @task.from_function(needs_target=True, special_reference=True)
    async def power_toggle(collector, target, reference, artifact, **kwargs):
        ...

Or, for backwards compatible, with the original import:

.. code-block:: python

    from photons_app.actions import an_action

    @an_action(needs_target=True, special_reference=True)
    async def power_toggle(collector, target, reference, artifact, **kwargs):
        ...

.. automethod:: photons_app.tasks.task_register.from_function
