.. _configuration_root:

Photons Configuration files
===========================

You can alter Photons settings from a configuration file.

By default Photons will look for ``lifx.yml`` in the current directory you
are running your script from.  You can change where this configuration is by
setting the ``LIFX_CONFIG`` environment variable to the location of your
configuration file.

It will also load ``~/.photons_apprc.yml``.

You can load extra files from either of these locations with something like:

.. code-block:: yaml

    ---

    photons_app:
      extra_files:
        after:
          - filename: "{config_root}/secrets.yml"
            optional: true
        before:
          - filename: "/path/to/file/you/want/loaded/before/this/one.yml

All the files that get loaded will be merged together and treated as if they
were one python dictionary using
`Option Merge <https://delfick-project.readthedocs.io/en/latest/api/option_merge/index.html>`_

There are a few things that can be configured by default.

Logs colours
------------

Depending on your terminal, it may be desirable to change the colours used by
the logging. You can do this with the following (best placed in
``~/.photons_apprc.yml``)

.. code-block:: yaml

    ---

    term_colors: light

.. note:: The logs will be the default theme until after configuration has been
    loaded.

.. _configuration_targets:

Targets
-------

Currently Photons only has one target type, which is the ``lan`` type. If one
has not been specified, Photons will create a target called ``lan`` that has
the type of ``lan`` and a default broadcast of ``255.255.255.255`` for
discovery.

You can override that with something like:

.. code-block:: yaml

    ---

    targets:
      lan:
        type: lan
        options:
          default_broadcast: 192.168.1.255

Or create your own:

.. code-block:: yaml

    ---

    targets:
      home_network:
        type: lan
        options:
          default_broadcast: 192.168.1.255

And then instead of ``lifx lan:transform -- '{"power": "off"}'`` you would
say ``lifx home_network:transform -- '{"power": "off"}'``

Hard coding discovery
---------------------

See :ref:`discovery_options`

Tile animations on noisy networks
---------------------------------

Tile animations require sending 320 HSBK values every 0.075 seconds to each
tile set and so on a noisy network this can result in an animation that
struggles to keep up. To help with this we can tell Photons to take a different
strategy when it comes to determining when to send messages.

.. code-block:: yaml

   ---

   animation_options:
      noisy_network: true
      inflight_limit: 2

You can override configuration with the following two environment variables:

NOISY_NETWORK
   If this environment variable is defined, then the noisy network code will be
   used

ANIMATION_INFLIGHT_MESSAGE_LIMIT
   This needs to be the max number of unacknowledged frames that can be inflight
   at any point

So if I turn noisy network code on and set the inflight limit to 2, then  when
it comes to sending the next frame, if we have two frames that haven't been
acknowledged yet, then we won't send anything for this frame.

.. toctree::
    :hidden:

    discovery_options
