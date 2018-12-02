.. _tile_animations:

Tile Animations
===============

Photons provides some actions for simple animations on the tiles.

Currently implemented is ``tile_time``, ``tile_marquee``, ``tile_nyan`` and
``tile_pacman``.

For example::

  lifx lan:tile_time <reference> -- '{options}'

  lifx lan:tile_marquee <reference> -- '{"text": "hello there"}'

  lifx lan:tile_nyan <reference>

  lifx lan:tile_twinkles <reference>

  lifx lan:tile_pacman <reference>

  lifx lan:tile_gameoflife <reference>

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

  user_coords -- boolean -- default false
    If this is true, then we use the (user_x, user_y) values from the tiles to
    determine what to display on the tiles. By default we assume the tiles are
    in a horizontal row.

  num_iterations -- int -- default -1
    How many iterations before we stop. -1 means never stop

  direction -- left or right -- default left
    The direction the text goes in

tile_nyan
  This also has the following options

  user_coords -- boolean -- default false
    If this is true, then we use the (user_x, user_y) values from the tiles to
    determine what to display on the tiles. By default we assume the tiles are
    in a horizontal row.

  num_iterations -- int -- default -1
    How many iterations before we stop. -1 means never stop

tile_pacman
  This also has the following options

  user_coords -- boolean -- default false
    If this is true, then we use the (user_x, user_y) values from the tiles to
    determine what to display on the tiles. By default we assume the tiles are
    in a horizontal row.

  num_iterations -- int -- default -1
    How many iterations before we stop. -1 means never stop

tile_twinkles
  This displays dots on the tiles like twinkling stars! It also has the following
  options.

  num_iterations -- int -- default -1
    How many iterations before we stop. -1 means never stop

  pallete -- optional string
    The colours to use, this a choice between. Not specifying this means random
    colours

  num_twinkles -- int -- default 20
    The number of twinkles to display

  fade_in_speed -- float -- default 0.125
    How long to take to fade in a twinkle

  fade_out_speed -- float -- default 0.078
    How long to take to fade out a twinkle

tile_gameoflife
  This simulates the conway's game of life (https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life)

  Pixels turn on to represent ``alive`` cells and turn off to represent ``dead``
  cells.

  We will randomly turn on cells with random colors every second and then
  iterate using the rules of the simulation

  This also has the following options

  user_coords -- boolean -- default false
    If this is true, then we use the (user_x, user_y) values from the tiles to
    determine what to display on the tiles. By default we assume the tiles are
    in a horizontal row.

  num_iterations -- int -- default -1
    How many iterations before we stop. -1 means never stop

  new_color_style -- ``random`` or ``average`` -- default ``average``
    This determines what color we set points that become alive. If random then
    we choose a random color. If average then we set the color to be the average
    of it's surrounding neighbours.

    Note that the randomly placed cells every second are random colors regardless
    of this option.

  iteration_delay -- float -- default 0.1
    The amount of seconds between each iteration of the simulation. Note that
    0.1 is the smallest value.

Starting an animation programmatically
--------------------------------------

You can start the animation in a script by doing something like the following
assuming you already have a lan target object:

.. code-block:: python

    from photons_tile_paint.addon import Animations

    import asyncio

    # Cancel this final_future when you want to stop the animation
    final_future = asyncio.Future()

    async with target.session() as afr:
        options = {"text": "hello there"}
        reference = "d073d5000001"
        await Animations.tile_marquee.animate(target, afr, final_future, reference, options)

For more information about valid objects for the reference, see :ref:`photons_app_special`
