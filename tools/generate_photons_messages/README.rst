Generating photons_messages
===========================

This folder contains the script and adjustments.yml necessary for generating the
photons_messages module from the public YAML definition of the LIFX LAN protocol.

To run just do::

    $ git submodule update --init
    $ cd public-protocol && git pull && cd ..
    $ pip3 install venvstarter
    $ ./generate

More information about adjustments.yml can be found at
http://github.com/delfick/photons-messages-generator
