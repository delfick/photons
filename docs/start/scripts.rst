.. _lifx_photons_script:

Making a Photons Script
=======================

Let's say you want to turn your bulb off if a random number between 0 and 10 is
less than 5.

So, we create a virtualenv (see :ref:`lifx_photons_venvstarter`) and then create
a script that uses that virtualenv.

First we create ``setup_venv`` with the following:

.. code-block:: python

    #!/usr/bin/env python3

    from venvstarter import ignite
    ignite(__file__, "lifx"
        , deps = ["lifx-photons-core==0.21.0"]
        , min_python_version = 3.6
        )

And create our virtualenv by running it::

    $ ./setup_venv

Now that we have a virtualenv, we can use it to run some code, so let's start
our ``my_script`` file.

.. code-block:: python

    #!/usr/bin/env python -cos=__import__("os");sys=__import__("sys");python=os.path.join(os.path.dirname(sys.argv[1]),".lifx/bin/python");os.execv(python,sys.argv)

    from photons_app.actions import an_action

    from delfick_project.addons import addon_hook

    import logging

    log = logging.getLogger("my_script")

    @addon_hook(extras=[
          ("lifx.photons", "transport")
        , ("lifx.photons", "messages")
        ])
    def __lifx__(collector, *args, **kwargs):
        pass

    @addon_hook(post_register=True)
    def __post__(collector, *args, **kwargs):
        # Optionally do something with the collector once all our
        # dependencies are resolved
        pass

    @an_action(target="lan", special_reference=True, needs_target=True)
    async def do_turn_off(collector, target, reference, artifact, **kwargs):
        print("Do the turn off here")

    if __name__ == "__main__":
        from photons_app.executor import main
        import sys
        main(["lan:do_turn_off"] + sys.argv[1:])

I'll complete the ``do_turn_off`` action below for completeness sake, but first
let's go over the different parts of this file and what they are for and what
they do.

``#!/usr/bin/env python -cos=__import__("os");sys=__import__("sys");python=os.path.join(os.path.dirname(sys.argv[1]),".lifx/bin/python");os.execv(python,sys.argv)``
    This shebang means that when you say ``./my_script`` you are actually saying
    ``./.lifx/bin/python ./my_script`` so that you are running the script
    with the python in the virtualenv you created when you ran ``./setup_venv``

``addon_hook``
    This function registers this module and is used to specify what other
    modules should be loaded.

    When modules are created, they have a ``setup.py`` that defines the name of
    these ``entry_points``. and these are the names you must use here so that
    these modules are initialized properly at the start of the app.

    When modules are loaded, there are two passes over the modules. The first
    pass is used for registering special hooks in the configuration and for
    defining what dependency modules are required.

    You can also use the decorator with ``post_register=True`` and this function
    will be called once all the dependencies are resolved and initialized.
    In this second pass we can inspect the configuration and do any setup we
    need to do.

``an_action``
    This decorator registers a function to be an action.

    ``an_action`` takes some arguments that define common behaviour for the action.

    In this case we say that the user must specify a reference and a target to
    use, with the lan target being set by default.

    We also ask that the reference be treated as a special reference. This means
    empty or ``_`` is all devices on the network, a comma seperated list of serials
    will address just those serials, and ``type:options`` syntax for matching
    against lights. If the ``photons_device_finder`` module is enabled then you
    can say something like ``match:power=off&cap=multizone`` to find all powered
    off strips for example.

``from photons_app.executor import main``
    This is the photons mainline. Calling it with an array is equivalent to
    running the ``lifx`` application with the specified arguments on the
    command line.

    In this case we are saying run photons with the ``lan`` target an execute
    the ``do_turn_off`` target.

So now, running our app should spit out something like::

    $ ./my_script
    15:11:04 INFO    delfick_project.option_merge.collector Adding configuration from /Users/stephenmoore/.photons_apprc.yml
    15:11:04 INFO    delfick_project.addons Found lifx.photons.__main__ addon
    15:11:04 INFO    delfick_project.addons Found lifx.photons.transport addon
    15:11:04 INFO    delfick_project.addons Found lifx.photons.protocol addon
    15:11:04 INFO    delfick_project.addons Found lifx.photons.transport addon
    15:11:04 INFO    delfick_project.addons Found lifx.photons.messages addon
    15:11:04 INFO    delfick_project.addons Found lifx.photons.script addon
    15:11:04 INFO    delfick_project.option_merge.collector Converting protocol_register
    15:11:04 INFO    delfick_project.option_merge.collector Converting target_register
    15:11:04 INFO    delfick_project.option_merge.collector Converting photons_app
    15:11:04 INFO    delfick_project.option_merge.collector Converting targets
    Do the turn off here

To summarize, we have

* Loaded the correct modules and only those modules we want
* Ensured that we have a lan target
* Defined the ``do_turn_off`` task
* Started the photons mainline and told it to execute the ``do_turn_off`` task.
  with the ``lan`` target

And that's how we create a script using photons!

For completeness, this particular script would be implemented like:

.. code-block:: python

    from photons_messages import DeviceMessages

    import random

    @an_action(target="lan", special_reference=True, needs_target=True)
    async def do_turn_off(collector, target, reference, artifact, **kwargs):
        if random.randrange(0, 10) < 5:
            await target.script(DeviceMessages.SetPower(level=0)).run_with_all([reference])

and usage would be like::

    $ ./my_script d073d580085

    # Or if we want to apply the SetPower to all devices on the network
    $ ./my_script
