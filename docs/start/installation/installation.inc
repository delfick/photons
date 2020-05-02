Installation
------------

Photons is best installed in a Python virtual environment. The following
commands create a virtual environment named ``.photons-core`` in the current
user's home directory and installs the latest version of Photons::

    $ python3 -m venv ~/.photons-core
    $ source ~/.photons-core/bin/activate
    $ pip install lifx-photons-core

.. note:: the virtual environment can be located anywhere on the file system by
   changing the ``~/.photons-core`` path to the desired location.

After installation, the Photons command-line tool ``lifx`` is available in the
virtual environment::

    $ lifx lan:transform -- '{"power": "on", "color": "red", "brightness": 0.5}'
