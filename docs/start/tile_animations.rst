.. _tile_animations:

Tile Animations
===============

Photons provides some actions for simple animations on the tiles.

Currently implemented is ``tile_time``, ``tile_marquee`` and ``tile_pacman``.

For example::

  lifx lan:tile_time <reference> -- '{options}'

  lifx lan:tile_marquee <reference> -- '{"text": "hello there"}'

Where the options are optional and are as follows:

background
  All the animation actions take in a background option of a dictionary containing
  ``{"type", "hue", "saturation", "brightness", "kelvin"}``

  type can be ``specified`` or ``current``. If ``current`` then the hsbk values
  are ignored and the background of the animation is whatever the tile is
  set to.

  if type is ``specified`` then it'll use the specified hsbk values as the
  background.

tile_time
  This also has the following options:

  hour24 -- boolean -- default true
    If true, then display in 24 hour time

  number_color -- hsbk dictionary -- default 200, 0.24, 0.5, 3500
    The color for the numbers

  progress_bar_color -- hsbk dictionary -- default 0, 1, 0.4, 3500
    The color of the progress bar

  full_height_progress -- boolean -- default false
    If false then the progress bar is just the bottom pixels

tile_marquee
  This also has the following options

  text_color -- hsbk dictionary -- default 200, 0.24, 0.5, 3500
    The color of the text

  text -- string -- required
    The text to scroll across the tiles
