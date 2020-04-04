.. installation:

Installation
============

As long as you have a version of Python 3.6 or newer installed you can do
something like::

    $ python3 -m venv .photons-core
    $ source .photons-core/bin/activate
    $ pip install lifx-photons-core
    
    # And then you can use Photons
    $ lifx lan:transform -- '{"power": "on", "color": "red", "brightness": 0.5}'
