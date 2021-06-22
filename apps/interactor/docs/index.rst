.. _app_interactor:

Local daemon with HTTP API
==========================

A downside of using photons from the commandline is the time it takes to start
up photons and discover devices. One way to get around this is to make a script
or server that has a long life and knows where the devices are.

Instead of someone building their own, Photons comes with a server that can be
used for this purpose.

To install and use::

    $ pip install lifx-photons-interactor
    $ lifx lan:interactor

The documentation on :ref:`targets <configuration_targets>` can be read to
understand if it's desirable to use a different target than the default ``lan``
target.

There is also a :ref:`Docker image <interactor_docker>` that can be used to
start the server.

And also you can load using :ref:`Home Assistant <interactor_homeassistant>` to
run Photons interactor.

The server currently supports:

* Getting help information about commands it supports
* Applying a theme
* Getting serials and information from the network
* Starting, stopping and querying firmware effects on devices
* Toggling power
* Querying devices for information
* Setting attributes on devices
* Capturing, changing and applying scenes on devices
* Transforming the devices in a similar way to the
  `LIFX HTTP API <https://api.developer.lifx.com/docs/set-state>`_.
* Controlling tile animations

Each command comes with the ability to target specific devices.

This server was originally a
`separate application <https://photons-interactor.readthedocs.io/en/latest/>`_
and was placed alongside the rest of the Photons codebase as part of the
``0.30.0`` release.

Running commands is done with the following PUT command::

    
    curl -XPUT http://127.0.0.1:6100/v1/lifx/command \
      -HContent-Type:application/json \
      -d '{"command": "transform", "args": {"transform": {"power": "on"}}}'

This
`handy script <https://github.com/delfick/photons/blob/main/apps/interactor/command>`_
can make it easier to make these requests::
    
    $ ./command query '{"pkt_type": "GetColor"}'
    {
        "results": {
            "d073d5001337": {
                "payload": {
                    "brightness": 1.0,
                    "hue": 0.0,
                    "kelvin": 3500,
                    "label": "",
                    "power": 65535,
                    "saturation": 0.0
                },
                "pkt_name": "LightState",
                "pkt_type": 107
            }
        }
    }

Available commands
------------------

To get information about what specific commands are available, run::

    curl -XPUT http://127.0.0.1:6100/v1/lifx/command \
      -HContent-Type:application/json \
      -d '{"command": "help"}'

And help for specific commands::

    curl -XPUT http://127.0.0.1:6100/v1/lifx/command \
      -HContent-Type:application/json \
      -d '{"command": "help", "args": {"command": "transform"}}'

Running on a raspberry Pi
-------------------------

Note that whilst you can run the interactor on an rPi and most commands will be
super quick, some commands will not be. The way Photons creates messages is
noticeably slow on an rPi for multizone and matrix devices as those messages
are quite large. This may improve in the future, but for now applying a theme
or scene to such devices may take a few seconds instead of instant. This problem
does not exist on a more powerful computer.

.. toctree::
    :hidden:

    options.rst
    docker.rst
    homeassistant.rst
    changelog.rst
