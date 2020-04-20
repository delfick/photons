.. toctree::
    :hidden:

    installation.rst
    philosophy.rst
    commandline/index.rst
    scripts/index.rst
    collector/index.rst
    configuration/index.rst
    interacting/index.rst
    useful_helpers/index.rst
    products/index.rst
    animations/index.rst
    changelog.rst

Photons
=======

Photons is an async Python3.6+ framework for interacting with LIFX devices.

Photons gives you:

* High level creation of LIFX :ref:`packets <packets>`
* Transparent device :ref:`discovery <sender_discovery>`
* Convenient API for :ref:`sending <sender_interface>` packets to multiple
  devices in parallel and streams responses back.
* A :ref:`gatherer <gatherer_interface>` for sending the least number of
  messages to get information from devices.
* A :ref:`product registry <products>` for determining the capabilities of the
  devices on your network.
* Efficient :ref:`tile animations <animations_root>` that can even run on
  a Raspberry Pi
* A rich set of functionality you an access from the
  :ref:`command line <commandline_root>`
* The ability to :ref:`configure <configuration_root>` Photons.
* A :ref:`daemon <device_finder>` you can run for continuous discovery and
  information gathering on your network.
* Useful :ref:`functionality <useful_helpers_root>` for common tasks while
  creating scripts.

Installation
------------

As long as you have a version of Python 3.6 or newer installed you can do
something like::

    $ python3 -m venv .photons-core
    $ source .photons-core/bin/activate
    $ pip install lifx-photons-core

    # And then you can use Photons
    $ lifx lan:transform -- '{"power": "on", "color": "red", "brightness": 0.5}'

Source code
-----------

The code for photons can be found at https://github.com/delfick/photons-core
which also has an ``examples`` folder of scripts.
