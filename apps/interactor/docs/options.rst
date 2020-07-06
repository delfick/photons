.. _interactor_options:

Options for the Interactor
==========================

By default ``lifx lan:interactor`` will load options from a ``lifx.yml`` in the
current directory. This can be changed with the ``LIFX_CONFIG`` environment
variable.

The file used for configuration may contain
:ref:`Photons specific configuration <configuration_root>` along with the
following options which are all optional:

.. code-block:: yaml

    interactor:
        # The host the server is started on
        # If you want to expose the server externally and you aren't running
        # this through docker, 0.0.0.0 is what you want.
        # The server has no authentication, so it's not recommended to do that
        # without it being behind a VPN
        host: 127.0.0.1

        # The port used by the server
        port: 6100

        database:
          # Scenes use a sqlite3 database and one will be created when the server
          # starts up if one does not already exist
          # By default it will create interactor.db in the same directory as the
          # main configuration file. If a configuration file doesn't exist, then
          # this is made in the current working directory.
          uri: "{config_root}/interactor.db"
