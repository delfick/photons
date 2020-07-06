Photons Tile Arranger
=====================

This is a web UI for arranging the positions of a number of LIFX Tiles relative
to each other.

It is build on top of `Photons <https://photons.delfick.com>`_ and once
installed can be run with::

    lifx lan:arrange

Doing this will start a server and then open your web browser to show a web UI
for arranging the tiles. The tiles will each be given a different pattern with
a white line at the bottom of the tile.

Clicking on a panel will highlight that panel in the web interface and on the
tile itself.

Moving a tile will change the ``user_x/user_y`` properties on the tile and make
the tile glow.

You can have multiple tabs open to the server and each tab will be in sync with
each other. Once all tabs are closed, the tiles will return to the colours they
had before the arrange was started.

This can be installed with::

    pip3 -m pip install lifx-photons-arranger
