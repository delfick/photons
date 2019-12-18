VERSION = "0.24.3"

__shortdesc__ = """Base module for all photons applications"""

__doc__ = """
Photons
=======

Photons is Python3.6+ framework for interacting with LIFX products.

There are three main ways of using Photons:

Using the lifx script
    Once you have pip installed ``lifx-photons-core`` into your python
    environment, you will have a ``lifx`` script on your PATH.

    You can use photons functionality via this script.

    See :ref:`lifx_photons_lifx_script`

As a walled garden
    You can create scripts where you define the fulfillment of some task and
    photons handles the commandline arguments and configuration files for you.

    See :ref:`lifx_photons_script`

As a library
    Alternatively you can handle how the user gets to your code and just use
    the functionality of photons to interact with LIFX devices.

    See :ref:`lifx_photons_library`

.. note:: It is highly recommended you use a
  `virtualenv <http://docs.python-guide.org/en/latest/dev/virtualenvs/>`_ as
  your python environment. See :ref:`lifx_photons_venvstarter` for example use
  of a tool I built for managing virtualenvs.

Installation
------------

You can install photons by ensuring you have python3.6 or above installed and doing::

    $ python3 -m venv photons-venv
    $ source photons-venv/bin/activate
    $ pip install lifx-photons-core

You can also find the code at https://github.com/delfick/photons-core
"""
