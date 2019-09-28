.. _config_file:

Config file
===========

Photons allows you to customize it via configuration file.

* ``~/.photons_apprc.yml``
* ``lifx.yml`` in the current directory, or the file specified by the ``LIFX_CONFIG``
  environment variable

You may also load more configuration files by specifying the following in either
of the two default files mentioned above:

.. code-block:: yaml

   photons_app:
      extra_files:
        - "{config_root}/secrets.yml"
        - /absolute/path/to/somewhere.yml

Note that in this case, ``{config_root}`` will be the folder the ``lifx.yml`` is
in. These files will be added after the file we say extra_files in.

All options will then be merged together before being interpreted by photons.

Currently there are three main things you can configure:

* :ref:`animation_options <tile_animation_noisy>`
* :ref:`discovery_options <discovery_options>`
* :ref:`target options <target_options>`
