.. toctree::
    :hidden:

    installation.rst
    philosophy.rst
    commandline/index.rst
    scripts/index.rst
    configuration/index.rst
    interacting/index.rst
    collector/index.rst
    products/index.rst
    animations/index.rst
    changelog.rst

Photons
=======

Photons is an async Python3.6+ framework for interacting with LIFX devices.

It currently supports a rich CLI interface as well as the ability to write
complicated scripts.

The programmatic interface supports a large range of features:

* High level creation of LIFX packets
* Easy ability to send messages to multiple devices in parallel
* A streaming API for sending and receiving messages
* Device discovery
* High level interface for creating messages that set HSBK values on devices.
* A rich "Planner" interface for sending the least number of messages to get
  information from devices.
* A product registry for determining information about the different LIFX
  devices
* Efficient tile animations that even run on Raspberry Pis

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
