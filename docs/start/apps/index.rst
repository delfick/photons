.. _apps:

Photons Applications
====================

Photons comes with some applications built on top of the core code.

:ref:`Tile arranger <app_tile_arranger>`
    Photons animations require the tiles know where they are in relation to each
    other to make multiple tile sets appear as one collection of tiles in an
    animation.

    This app provides a web interface that can be used to set this information
    on the tiles::

        $ pip install lifx-photons-arranger
        $ lifx lan:arrange

:ref:`Interactor <app_interactor>`
    This application provides a web server that will sit on your network aware
    of your devices and information about them. It will then accept HTTP requests
    to interact with those devices with almost no latency::

        $ pip install lifx-photons-interactor
        $ lifx lan:interactor

.. toctree::
    :hidden:

    arranger/index.rst
    interactor/index.rst
