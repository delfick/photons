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
        # this in a container, set this to 0.0.0.0.
        # The server has no authentication, so it's not recommended to do that
        # without it being behind a firewall or only accessible via VPN.
        host: 127.0.0.1

        # The port used by the server
        port: 6100

        # options for zeroconf setup
        zeroconf:
          # If true, Interactor will enable Zeroconf but only if the host is not
          # set to 127.0.0.1 or localhost. Default is false.
          # enabled: true

          # Interactor can work out the IP of this computer automatically,
          # or you can manually specify one. It must be assigned to an interface
          # on the local machine.
          # ip_address: 192.168.0.1

          # The name of this Photons Interactor instance. Defaults to the hostname,
          # but it can be customised. Should be unique on the network to avoid duplicates.
          # name: <hostname>

        database:
          # Scenes use a sqlite3 database and one will be created when the server
          # starts up if one does not already exist
          # By default it will create interactor.db in the same directory as the
          # main configuration file. If a configuration file doesn't exist, then
          # this is made in the current working directory.
          uri: "{config_root}/interactor.db"

        daemon_options:
            limit: 30 # Limit of 30 messages inflight at any one time
            search_interval: 1800 # do a discovery every 30 minutes
            time_between_queries:
              LIGHT_STATE: 600 # label, power, hsbk every 10 minutes
              VERSION: null # The type of product can be cached forever
              FIRMWARE: 86400 # Cache the firmware version for a day
              GROUP: 780 # Cache group information for 13 minutes
              LOCATION: 9600 # Cache location information for 16 minutes
