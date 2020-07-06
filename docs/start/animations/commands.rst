.. _tile_animation_commands:

Starting animations from the Command Line
=========================================

All the built in animations can be started from ``animate`` command.

For example, to find all the tiles on the network and start a sequence of
animations on them::

    $ lifx lan:animate

This will default to looping through a few of the animations available.

A specific device may be specified with a :term:`reference`::

    $ lifx lan:animate match:label=wall

And a particular animation may be started::

    # all tiles on the network
    $ lifx lan:animate balls

    # A particular set of tiles
    $ lifx lan:animate balls match:label=wall

All the available tiles can be seen with the ``help`` option::

    $ lifx lan:animate help

To list the options for an animation, run::

    $ lifx lan:animation help falling

Providing Animation options
---------------------------

There a number of options available when running tile animations that can be
specified after a ``--`` on the command line::

    # Make the tiles return to their previous state when the animation is stopped
    $ lifx lan:animate -- '{"animations": ["balls", "falling"], "reinstate_on_end": true}'

When a specific animation is specified, options for that animation are the
object, and animation options are under ``run_options``::

    $ lifx lan:animate balls -- '{"num_balls": 2, "run_options": {"reinstate_on_end": true}}'

If can be useful to specify all the options in a file and edit them there
instead of directly on the command line:

.. code-block:: json

    {
      "num_balls": 2,
      "run_options": {
        "reinstate_on_end": true
      }
    }

And then reference using the ``file://`` option::

    $ lifx lan:animate balls -- file://options.json

Multiple animations may be run at the same time and the rest of the examples
show the options as if they were specified in ``options.json`` as shown above
but run with::

    $ lifx lan:animate -- file://options.json

Animations are specified in an animations list:

.. code-block:: json

    {
      "animations": [["balls", { "num_seconds": 10 }], "swipe"]
    }

This will run the ``balls`` animation for 10 seconds, followed by the ``swipe``
animation and will then start the loop again. The number of animations run
before this loop ends can be provided with the ``animation_limit`` option:

.. code-block:: json

    {
      "animations": [["balls", { "num_seconds": 10 }], "swipe"],
      "animation_limit": 4
    }

This will stop after 4 animations have run. So in this case each animation will
run twice.

Animations will start with the current colours on the tiles when they start.
This can be turned off when the animation is specified with three items in
the array:

.. code-block:: json

    {
      "animations": [
        ["balls", { "num_seconds": 10 }],
        ["swipe", false, null]
      ],
      "animation_limit": 4
    }

With these options, the swipe animation won't start with the state of the
tiles after the ball animation's time is up.

.. note:: ``null`` for the options value will make the animation use default
    values for all it's options.

Available options
-----------------

The ``run options`` expose the following options:

combined - boolean - default True
    Whether to join all found tiles into one animation

reinstate_on_end - boolean - default False
    Whether to return the tiles to how they were before the animation

reinstate_duration - float - default 1
    The duration used when reinstating state

noisy_network - integer - default to environment
    Whether to use the "noisy network" logic. This allows tile animations
    to perform better when the network is "noisy" and there is a lot of
    packet loss.

    If this option is not provided, then photons will use the options as
    explained in the :ref:`configuration section <noisy_networks_config>`.

rediscover_every - integer (seconds) - default 20
    This value is the number of seconds it should take before photons will try
    rediscover devices on the network to add to the animation.

animation_limit - integer - 0
    The number of animations to run before stop running any new animations.

    It defaults to no limit

animation_chooser - "cycle" or "random" - default cycle
    The strategy for determining which animation to run next. By default the
    code will just choose the next sequential animation given in the list.

    If "random" is chosen then the next animation will be randomly chosen
    from the list.
    
transition_chooser - "cycle" or "random" - default cycle
    This is the same as ``animation_chooser`` but applies to any transition
    animations that have been specified.

transitions - dictionary  of options - default to have no affect
    These are animations that are run in between animations. There are a few
    options available:

    run_first
        Run a transition before the first feature animation

    run_last
        Run a transition after the last feature animation (unless animations
        are cancelled)

    run_between
        Run transitions between feature animations

    animations
        Same option as in the ``animations`` option of the root options.

animations - list - default to a small selection of available animations
    The different animations to be run.

    These are a list of

    * ``<name>``
    * ``<name>, <options>``
    * ``<name>, <background>, <options>``

    ``name``
        This is the name of the registered animation.

        If it's a tuple of ``(Animation, Options)`` where those are the classes
        that represent the animation, then a new animation is created from
        those options.

    ``background``
        If this value is not not specified, or null or true, then the current
        colors on the tiles are used as the starting canvas for the animation.

        If this value is false, then the starting canvas for the animation will
        be empty.

    ``options``
        A dictionary of options relevant to the animation.

    For example, ``[["balls", {"num_seconds": 10}], "swipe"]`` says to run
    the ``balls`` animation for 10 seconds, and then the ``swipe`` animation.

Special animation options
-------------------------

There are some options that aren't specific to an animation, can be specified
for an animation. For example::

    $ lifx lan:animate balls -- '{"num_seconds": 10}'

The ``balls`` animation doesn't actually know about ``num_seconds`` but the
engine of the animations knows that after 10 seconds, it should stop that
animation.

The following are those options:

every - integer in seconds - default usually 0.075
    This is the number in seconds between each "tick" event

retries - boolean - default usually false
    Whether to retry messages. You likely don't want to set this to true

duration - float in seconds - default usually 0
    The number of seconds the tile will take to transition each pixel to a
    new colour. Some animations will change this value depending on what it's
    doing. For example, the builtin ``color_cycle`` animation uses this option
    heavily to make everything look pretty and yet consume very little CPU.

num_seconds - float seconds - default no limit
    As mentioned above, this option will let the engine know to stop the
    animation after this many seconds

message_timeout - float seconds
    When retrying messages, this is how long we wait before we give up waiting
    for a reply

random_orientations - boolean - default false
    Whether to ignore the orientation of the tile and just use a random one.

    I highly recommend running::
        
        $ lifx lan:animate swipe -- '{"random_orientations": true}'

skip_next_transition - boolean - default false
    If transitions are given to the animation, then this option will ensure
    that no transition will follow this animation.
