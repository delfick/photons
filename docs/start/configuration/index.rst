.. _configuration_root:

Photons Configuration files
===========================

Photons is configured using one or more configuration files.

Photons looks for a ``lifx.yml`` file in the same directory as the script being
run. The ``LIFX_CONFIG`` environment variable is used to override this location
with the specific path to a configuration file.

Photons will combine the ``lifx.yml`` or ``LIFX_CONFIG`` configuration with the
contents of ``~/.photons_apprc.yml``.

Additional configuration files can be included using the following syntax in
one of the automatically detected configuration files:

.. code-block:: yaml

    ---

    photons_app:
      extra_files:
        after:
          - filename: "{config_root}/secrets.yml"
            optional: true
        before:
          - filename: "/path/to/file/you/want/loaded/before/this/one.yml

All configuration files are automatically merged to create a single
Python dictionary using `Option Merge <https://delfick-project.readthedocs.io/en/latest/api/option_merge/index.html>`_.

The following options can be configured.

Logs colours
------------

Change the color scheme used by the console log by setting the ``term_colors``
variable. This is best configured as a per-user setting in ``~/.photons_apprc.yml``

.. code-block:: yaml

    ---

    term_colors: light

.. note:: log theme is set when the configuration is loaded after Photons starts.

.. _configuration_targets:

Targets
-------

Photons has a single target type of ``lan`` named ``lan`` by default.
The default target uses a default broadcast address of ``255.255.255.255``
for device discovery.

To make discovery more efficient, the ``lan`` target can be configured with a
more specific broadcast address.

.. code-block:: yaml

    ---

    targets:
      lan:
        type: lan
        options:
          default_broadcast: 192.168.1.255

          # These options are all optional, below are the defaults
          gaps:
            # Some messages, like that used for discovery has an "unbound" number of results
            # We stop waiting for results this gap plus 0.05 seconds before giving up waiting
            # for more results
            # In practise, with the default value, discovery will take a minimum 0.45 seconds to complete
            gap_between_results: 0.4

            # If we need both an acknowledgement and a result from a device, we wait this many seconds
            # after getting an acknowledgement before retrying a message if we haven't got a reply yet
            gap_between_ack_and_res: 0.2

            # This is the backoff times for retrying messages.
            # So with this setting, we retry at 0.2, 0.3, 0.4, 0.5, 0.7, 0.9, 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, etc
            timeouts: [(0.2, 0.2), (0.1, 0.5), (0.2, 1), (1, 5)]

A custom target can also be defined:

.. code-block:: yaml

    ---

    targets:
      home_network:
        type: lan
        options:
          default_broadcast: 192.168.1.255

If a custom target is configured, it can be used instead of the ``lan`` target
the ``lifx`` utility on the command line, e.g. instead of
``lifx lan:transform -- '{"power": "off"}'`` it becomes
``lifx home_network:transform -- '{"power": "off"}'``

Hard-coded discovery
--------------------

See :ref:`discovery_options`

.. _noisy_networks_config:

Adjusting animations for busy networks
--------------------------------------

Tile animations send 320 HSBK values every 0.075 seconds to each tile set. To
compensate for networks with heavy existing traffic, configure Photons to used
a different packet strategy to reduce the overall number of packets sent and
received:

.. code-block:: yaml

   ---

   animation_options:
      noisy_network_limit: 2

This configuration is overridden at runtime by similarly named environment
variables:

``NOISY_NETWORK_LIMIT``
   Sets the maximum number of unacknowledged animations frames in-flight at
   any point.

In noisy network mode, Photons will limit the number of frames in-flight to the
value set. In this example, if two frames have been sent, Photons will not send
another frame until it receives an acknowledgement.

Full configuration example
--------------------------

An example configuration with all available options looks like this:

.. code-block:: yaml

    ---

    photons_app:
      extra_files:
        after:
          # load a "secrets.yml" that sits next to this file
          # before this file is read
          # If there is a secrets.yml to be found
          - filename: "{config_root}/secrets.yml"
            optional: true

    animation_options:
      noisy_network: true
      inflight_limit: 2

    targets:
      home_network:
        type: lan
        options:
          default_broadcast: 192.168.0.255

      work_network:
        type: lan
        options:
          discovery_options:
            hardcoded_discovery:
              d073d5000002: 10.0.0.2
              d073d5000003: 10.0.0.3

.. toctree::
    :hidden:

    discovery_options
