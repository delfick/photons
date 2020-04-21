.. _scripts_root:

Writing Scripts
===============

A Photons script is much like any Python script, but you need to instantiate
Photons. There are two methods of doing this. One is to use the
:ref:`library_setup <library_setup>` function, and the other is to register an
:ref:`action <photons_action>` like the ones shown in the section on
:ref:`CLI commands <common_cli_commands>`.

Starting Photons will load the necessary code, register functionality that is
spread across the different "modules" that makes up Photons; and reading in
configuration.

.. toctree::
    :hidden:

    library_setup
    photons_action
    logging
    long_running_server
    cleanup_functions
