.. _scripts_root:

Writing Scripts
===============

A Photons script is much like any Python script, but you need to instantiate
Photons. There are two methods of doing this. One is to use the
:ref:`library_setup <library_setup>` function, and the other is to register an
:ref:`action <photons_action>` like the ones shown in the section on
:ref:`CLI commands <common_cli_commands>` and then using the Photons mainline
to run them.

Starting photons does a number of things:

* Load the photons modules your script says it depends on (and the modules those
  depend on, and so forth)
* Loading the modules will register things like target types and reference
  resolvers.
* Load in the :ref:`configuration files <configuration_root>`

Photons also has the ability to start your application from an async function
and handle shut down for you, in a way similar to ``asyncio.run`` but with some
Photons specific extras.

.. toctree::
    :hidden:

    photons_action
    library_setup
    logging
    long_running_server
    cleanup_functions
