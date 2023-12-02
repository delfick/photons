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

.. _release-arranger-0-7-0:

0.7.0 - 2 December 2023
    * Photons is now python3.11+

.. _release-arranger-0-6-1:

0.6.1 - 9 January 2022
    * Upgrade Photons
    * lint and update the Javascript

.. _release-arranger-0-6-0:

0.6.0 - 6 November 2021
    * Now python3.7+ and supports python3.10

.. _release-arranger-0-5-14:

0.5.14 - 15 August 2021
    * Update JS dependencies

.. _release-arranger-0-5-13:

0.5.13 - 28 March 2021
    * Upgrade Photons and implement more graceful shutdown

.. _release-arranger-0-5-12:

0.5.12 - 15 March 2021
    * Seems my fix to avoid a release without JS didn't work properly

.. _release-arranger-0-5-11:

0.5.11 - 15 March 2021
    * Updating photons

.. _release-arranger-0-5-10:

0.5.10 - 9 February 2021
    * Same as 0.5.9 but with JavaScript included!

.. _release-arranger-0-5-9:

0.5.9 - 3 January 2021
    * Adding LICENSE file to the package on pypi

.. _release-arranger-0-5-8:

0.5.8 - 12 December 2020
    * update photons

.. _release-arranger-0-5-7:

0.5.7 - 5 December 2020
    * Update photons
    * Upgraded all the JavaScript dependencies

.. _release-arranger-0-5-6:

0.5.6 - 28 November 2020
    * Fixed some memory leaks in photons

.. _release-arranger-0-5-5:

0.5.5 - 22 November 2020
    * Update dependencies for python3.9 compatibility

.. _release-arranger-0-5-4:

0.5.4 - 23 August 2020
    * Upgrade photons-core to fix discovery bug

.. _release-arranger-0-5-3:

0.5.3 - 12 August 2020
    * Fixed bug where the program can enter a state of using all your CPU

.. _release-arranger-0-5-2:

0.5.2 - 9 August 2020
    * 0.5.1 had development assets in it, so I deleted it

.. _release-arranger-0-5-1:

0.5.1 - 9 August 2020
    * Using new photons code, including fixing memory leaks

.. _release-arranger-0-5:

0.5 - 11 July 2020
    * Initial import from https://photons-interactor.readthedocs.io/
