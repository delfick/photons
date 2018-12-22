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

  lifx lan:tile_falling <reference>

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

tile_falling
  This is just pixels falling from the top to the bottom.

  Essentially we have lines of pixels with the tip being a special colour and
  the rest between a random colour in a hue_range with decreasing brightness
  where each line is of a random length.

  The following are options available for this animation:

  num_iterations -- int -- default -1
    How many iterations before we stop. -1 means never stop

  hue_ranges -- null or list of strings or csv -- default "90-110"
    A string or a list of strings where each string is a comma separated range
    where the range is either '<min>-<max>' or the word 'rainbow'. These numbers
    are used to determine the colour of each pixel in each line. Saying rainbow
    is the same as saying '0-360'.

    For example if you said '0-10,rainbow' then half the lines will be the full
    range of colours and the other half of the lines will have red pixels.

    You can say a single number to represent just that number. For example if
    you said '0-10,100' then half will be between 0 and 10 and the other half
    will all be exactly 100.

    If this is set to null then only the tip will have a nonzero brightness.

  line_tip_hue -- null or hue range -- default 60
    A single hue range like those in hue_ranges. I.e. 'rainbow' or '60' or '0-10'

    If this is set to null then the tip of each line will not be a special colour,
    otherwise it's hue will be a random value in the range specified.

    Note that if both hue_ranges and line_tip_hue are null then hue_ranges will
    remain null and line_tip_hue will become 60.

  blinking_pixels -- boolean -- default true
    Whether pixels should randomly blink as they are moving down.

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
