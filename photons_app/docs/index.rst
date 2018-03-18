.. _photons_app:

photons_app
===========

photons_app is the central Photons module. This module is responsible for
setting up the module system and providing core functionality for Photons apps.

Defining actions
    Photons provides a basic system for defining cli actions.

    Please see :ref:`photons_app_defining_actions` for more information.

The collector
    Photons uses the `option_merge <https://option_merge.readthedocs.io>`_
    library for configuration. This library comes with the collector class,
    which photons extends.

    This class is responsible for collecting configuration from multiple sources
    and merging them into ``collector.configuration``.

    We define ``converters`` on the configuration that allows us to access
    normalized options from the raw configuration.

    Collector is also responsible for finding and initializing our photons
    modules.

    Please see :ref:`photons_app_collector` for more information.

Core Error classes
    Photons provides some error classes that are good to be aware of and extend.

    See :ref:`photons_app_errors`.

The executor
    We use `Delfick App <https://delfick-app.readthedocs.io>`_ to create the
    mainline functionality.

    If you are creating a Photons App, you extend this class to hook into the
    initialization of the program and to modify the interaction with the
    commandline.

    :ref:`photons_app_executor` has more information.

Helpers
    There are a bunch of useful helper functionality that photons_app provides
    for your programs.

    See :ref:`photons_app_helpers` for information about those.

Registers
    Photons App provides some registration objects in the configuration that can
    be used to register extra functionality for use in your program.

    :ref:`photons_app_registers` has information about how to use these.

Special References
    We also provide objects that can be used to find devices to send messages to.

    :ref:`photons_app_special` has information about these objects.

.. toctree::
    :hidden:

    defining_actions
    collector
    errors
    executor
    helpers
    registers
    special
