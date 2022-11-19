.. _interactor_homeassistant:

Home Assistant Addon
====================

`Home Assistant <https://www.home-assistant.io/>`_ is an open source platform for
managing all the smart devices in your home.

This provides the ability to load arbitrary applications alongside your home
assistant instance via addons.

You can use this by adding https://github.com/delfick/photons-homeassistant as
a repository in Home Assistant and enabling ``Photons Interactor``.

Once it is running you can use the Home Assistant ``rest_command`` to make Photons
Interactor do things to your devices:

.. code-block:: yaml

  rest_command:
    lights_red:
      url: 'http://127.0.0.1:6100/v1/lifx/command'
      method: "put"
      payload: |
        {
          "command": "transform",
          "args": {
            "transform": {
              "color": "red saturation:0.5 brightness:0.5"
            }
          }
        }

Will use the interactor to change all of your lights to red.

A custom lifx.yml configuration may also be provided by placing a ``lifx.yml``
file in a ``photons`` folder in the home assistant ``config`` share.

See https://www.home-assistant.io/docs/configuration/
