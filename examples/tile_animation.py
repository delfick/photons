#!/usr/bin/python -ci=__import__;o=i("os");s=i("sys");a=s.argv;p=o.path;y=p.join(p.dirname(a[1]),".python");o.execv(y,a)

from photons_canvas.animations import Animation, Finish, AnimationRunner, options
from photons_canvas import point_helpers as php

from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from delfick_project.logging import setup_logging
from delfick_project.norms import dictobj, sb
import logging
import random

log = logging.getLogger("tile_animation")


class Options(dictobj.Spec):
    color = dictobj.Field(options.color_range_spec("rainbow"))
    min_dots_per_tick = dictobj.Field(sb.integer_spec, default=20)


class State:
    def __init__(self, options):
        self.color = options.color.color
        self.remaining = {}
        self.min_per_tick = options.min_dots_per_tick
        if self.min_per_tick <= 0:
            self.min_per_tick = 1

    def add_parts(self, parts):
        for part in parts:
            for point in part.points:
                self.remaining[point] = True

    @property
    def layer(self):
        next_selection = random.sample(
            list(self.remaining), k=min(len(self.remaining), self.min_per_tick)
        )

        def layer(point, canvas):
            if not self.remaining:
                return php.Color.ZERO

            if point in next_selection:
                del self.remaining[point]
                return self.color
            else:
                return canvas[point]

        return layer


class Animation(Animation):
    coords_straight = True

    def setup(self):
        """This method can be used to do any extra setup for all tiles under the animation"""

    async def process_event(self, event):
        """
        This is called for each event related to the running of the animation

        It takes in and event object which has a number of properties on it

        value
            A value associated with the event

        canvas
            The current canvas object used to paint the tiles with

        animation
            The current animation object

        state
            The current state associated with your animation. You can set a new
            state by using ``event.state = new_state``. This new_state will be
            the event.state for the next event

        is_tick
            Is this event a TICK event. This is determined by the animation's
            ``every`` property which is the number of seconds between creating
            a new canvas to paint on the devices. It defaults to 0.075 seconds.

            This event is special and the only one where the return value of
            this function is used. If you want a new canvas to be painted onto
            the devices, you return a Canvas object. Events after this will
            have the last Canvas that was returned. If you don't want new
            values to be painted then return None from this event

            This event will only be used if there are one or more devices used
            by this animation.

        is_error
            For when some error was encountered. The ``value`` is the exception
            that was caught.

        is_end
            When the animation has ended

        is_start
            When the animation has started

        is_user_event
            It's possible to create events yourself and this event happens
            when those are created. It's ``value`` is the event you created.

        is_new_device
            When a device has been added to the animation. The ``value`` is
            the parts associated with that device.

        is_sent_messagse
            When the animation sends messages to the devices. The ``value`` for
            this event are the Set64 messages that were sent
        """
        if event.state is None:
            event.state = State(self.options)

        if event.is_new_device:
            event.state.add_parts(event.value)

        elif event.is_tick:
            if not event.state.remaining:
                if event.canvas.is_parts(brightness=0):
                    raise Finish("Transition complete")

                self.every = 1
                self.duration = 1

            return event.state.layer


async def doit(collector):
    # Get the object that can talk to the devices over the lan
    lan_target = collector.configuration["target_register"].resolve("lan")

    # reference can be a single d073d5000001 string representing one device
    # Or a list of strings specifying multiple devices
    # Or a special reference like we have below
    # More information on special references can be found at
    # https://delfick.github.io/photons-core/photons_app/special.html#photons-app-special
    reference = FoundSerials()

    # Options for our animations
    # The short form used here is a list of animations to run
    # We are saying only animation to run.
    # We provide the Animation class and the Options class associated with that animation
    # The last argument is options to create the Options object with, here we
    # we have no non default options.
    run_options = {"animations": [[(Animation, Options), None]], "animation_limit": 1}

    def error(e):
        log.error(e)

    # And now we run the animation using an AnimationRunner
    photons_app = collector.configuration["photons_app"]

    try:
        with photons_app.using_graceful_future() as final_future:
            async with lan_target.session() as sender:
                await AnimationRunner(
                    sender,
                    reference,
                    run_options,
                    final_future=final_future,
                    message_timeout=1,
                    error_catcher=error,
                ).run()
    except Finish:
        pass


if __name__ == "__main__":
    # Setup the logging
    setup_logging()

    # setup photons and get back the configuration
    collector = library_setup()

    # Run the animation!
    collector.run_coro_as_main(doit(collector))
