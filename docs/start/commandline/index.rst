.. _commandline_root:

Photons from the command line
=============================

You can achieve many tasks from the command line. Usually if you start to need
multiple of these commands you should create a :ref:`script <scripts_root>` but
there are many tasks that can be done with just one command in your terminal.

You can access these scripts using the ``lifx`` command that will be in your
``PATH`` when you're in a Python virtualenv with photons installed.

For example, once you've installed Photons you can say::

    $ lifx lan:transform match:label=kitchen -- '{"power": "off"}'

This command will use our ``lan`` target with the ``transform`` task, find your
light with the label ``kitchen`` and tell it to turn off.

All commands from the ``lifx`` script are formatted like the following::

    $ lifx <target>:<action> <reference> <artifact> -- <options>

Some commands don't need all of these items, like ``unpack`` doesn't require a
target to be specified for example.

It's possible for photons to know about multiple targets but in most cases you'll
only ever use the ``lan`` target, which by default is a target that talks to
your devices over the local network and uses the broadcast address of
``255.255.255.255`` to find your devices. You can change the default broadcast
address or create other targets with different broadcast addresses using the
:ref:`configuration <configuration_root>`

You can find all available commands by saying ``lifx help`` and information
about a specific task by saying something like ``lifx help transform``.

.. note:: You can specify the options after the ``--`` by a filename by saying::

        lifx lan:transform -- file:///path/to/my/options.json

    If your options is in the current directory then you would say::
        
        lifx lan:transform -- file://options.json

Running CLI commands on windows
-------------------------------

Running these commands from the Windows command prompt is a little tricky
because many of them specify options with a json string. Escaping this in the
window command prompt is annoying because you have to say this::
    
    $ lifx lan:transform -- "{\"power\": \"on\"}"

Instead it's useful to write a python script that looks like:

.. code-block:: python

    __import__("photons_core").run_cli('lan:transform -- {"power": "on"}')

and then from the command line::

    $ python power_on.py

.. toctree::
    :hidden:

    references
    common_commands
