.. _commandline_root:

Photons from the command line
=============================

Photons provides the ``lifx`` command-line utility which can be used
to perform several tasks. If multiple tasks are required, consider
creating a :ref:`script <scripts_root>` instead.

To access these tasks, ensure the ``lifx`` command is in your ``PATH`` by
:ref:`activating the virtual environment <activation>` into which Photons is
installed.

A simple example of running a task with the ``lifx`` utility::

    $ lifx lan:transform match:label=kitchen -- '{"power": "off"}'

This command uses the ``lan`` target with the ``transform`` task to find a
device with the :term:`label` ``kitchen`` and powers it off.

The ``lifx`` utility uses the following command-line structure::

    $ lifx <target>:<task> <reference> <artifact> -- <options>

Some tasks don't need all of these items, like ``unpack`` doesn't require a
:term:`reference` to be specified for example.

Photons includes a single ``lan`` target, which is configured to discover
and communicate with devices on the local network using the default broadcast
address of 255.255.255.255. It's possible to change the default broadcast
address used by the ``lan`` target or create new targets by providing a
custom :ref:`configuration <configuration_root>`.

To list all available tasks, run ``lifx help``. To get details about a specific
task, run ``lifx help <task>``, e.g. ``lifx help transform``.

.. note:: The ``options`` field must be valid JSON syntax which can be
   cumbersome to provide directly on the command line. For ease of use, the
   ``lifx`` utility accepts a `file://` path instead::

        $ lifx lan:transform -- file:///path/to/my/options.json

    If the file is in the current directory::

        $ lifx lan:transform -- file://options.json

Running CLI commands on Windows
-------------------------------

Running the ``lifx`` utility from the Windows Command Prompt requires the
JSON syntax to be escaped correctly, which can be challenging::

    C:\Users\me> lifx lan:transform -- "{\"power\": \"on\"}"

An alternative method which doesn't require escaping JSON is to write
a simple Python script instead:

.. code-block:: python

    __import__("photons_core").run_cli('lan:transform -- {"power": "on"}')

which can be run directly from the command prompt::

    C:\Users\me> python power_on.py

.. toctree::
    :hidden:

    references
    common_commands
