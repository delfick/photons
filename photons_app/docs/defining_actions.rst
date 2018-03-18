.. _photons_app_defining_actions:

Defining Photons Actions
========================

.. automodule:: photons_app.actions

The default photons cli interface takes in commands of the following format:

.. code-block:: sh

    $ lifx <target>:<action> <reference> <artifact> -- '<extra>'

For example:

.. code-block:: sh

    $ lifx lan:set_attr d073d5000000 color -- '{"hue": 210, "saturation": 0.4, "brightness": 0.3, "kelvin": 3500}'

In this example we are invoking the ``set_attr`` action using the ``lan`` target
(which would defined in configuration) and running it against the device
``d073d5000000`` and setting the ``color`` attribute with the options set after
the ``--``.

It is equivalent to saying:

.. code-block:: sh
    
    $ lifx --target lan --task set_attr --reference d073d5000000 --artifact color -- '<options>'
