.. _app_tile_arranger:

Tile arranger
=============

Photons animations require the tiles know where they are in relation to each
other to make multiple tile sets appear as one collection of tiles in an
animation.

This app provides a web interface that can be used to set this information
on the tiles.

To install and use this app, the following commands may be run::

    $ pip install lifx-photons-arranger
    $ lifx lan:arrange

The documentation on :ref:`targets <configuration_targets>` can be read to
understand if it's desirable to use a different target than the default ``lan``
target.

How it works
------------

When the web UI is opened in the browser, the server will discover the tiles on
the network, change them all to a unique pattern, and display each panel as it's
own square on a grid. Each pattern will also have a white line on the bottom of
the panel to help determine it's orientation. When all tabs to the web
UI are closed, or the server is shutdown, the panels will return to how they
looked before the arranging began.

There are two ways to interact with the panels:

Clicking a panel
    This can be used to help work out which panel in the web UI corresponds to
    which panel in physical space with an animation.

Dragging a panel
    This will change the tile's idea of where that panel is. Once a panel has
    been dragged, the server will cause the panel to glow and change that
    information.

    If the server is unable to give that information to the tile, the square in
    the UI will return to where it was was dragged.

Once the tiles are given their correct positions, photons can be used to run
:ref:`animations <animations_root>` on them as if they are one set.

Changelog
---------

0.5.6 - 28 November 2020
    * Fixed some memory leaks in photons

0.5.5 - 22 November 2020
    * Update dependencies for python3.9 compatibility

0.5.4 - 23 August 2020
    * Upgrade photons-core to fix discovery bug

0.5.3 - 12 August 2020
    * Fixed bug where the program can enter a state of using all your CPU

0.5.2 - 9 August 2020
    * 0.5.1 had development assets in it, so I deleted it

0.5.1 - 9 August 2020
    * Using new photons code, including fixing memory leaks

0.5 - 11 July 2020
    * Initial import from https://photons-interactor.readthedocs.io/
