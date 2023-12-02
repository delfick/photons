.. toctree::
    :hidden:

    philosophy.rst
    Installation <installation/index.rst>
    commandline/index.rst
    scripts/index.rst
    collector/index.rst
    configuration/index.rst
    interacting/index.rst
    useful_helpers/index.rst
    products/index.rst
    animations/index.rst
    apps/index.rst
    glossary.rst
    changelog.rst

Photons
=======

Photons is an asynchronous Python3.11+ framework for interacting with LIFX
devices.

Photons provides:

* High level creation of LIFX :ref:`packets <packets>`
* Transparent device :ref:`discovery <sender_discovery>`
* A convenient API for :ref:`sending <sender_interface>` packets to multiple
  devices in parallel and streams responses back.
* A :ref:`gatherer <gatherer_interface>` for sending the least number of
  messages to get information from devices.
* A :ref:`product registry <products>` for determining the capabilities of the
  devices on your network.
* Efficient :ref:`tile animations <animations_root>` that can run on
  low powered devices like a Raspberry Pi
* A rich set of functionality that can be accessed from the
  :ref:`command line <commandline_root>`
* A :ref:`daemon <device_finder>` you can run for continuous discovery and
  information gathering on your network.
* Useful :ref:`functionality <useful_helpers_root>` for common tasks while
  creating scripts.
* Flexible :ref:`configuration <configuration_root>` capabilities.

.. include:: installation/installation.inc

Source code
-----------

The code for photons is found at https://github.com/delfick/photons
and includes an ``examples`` folder of scripts.
