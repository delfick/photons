from photons_canvas.animations.infrastructure.events import AnimationEvent
from photons_canvas.points import rearrange

from photons_app import helpers as hp

import logging
import asyncio
import time

log = logging.getLogger("photons_canvas.animations.infrastructure.animation")


class Animation:
    every = 0.075
    retries = False
    duration = 0
    num_seconds = None
    message_timeout = 0.3
    random_orientations = False
    skip_next_transition = False

    align_parts_separate = False
    align_parts_straight = False
    align_parts_vertically = False

    overridable = [
        "every",
        "retries",
        "duration",
        "num_seconds",
        "message_timeout",
        "random_orientations",
        "skip_next_transition",
    ]

    def __init__(self, final_future, options, pauser=None):
        self.pauser = pauser
        self.options = options
        self.final_future = final_future

        self.started = None
        self.setup()

    @property
    def info(self):
        name = self.__class__.__name__
        if hasattr(self, "__registered_name__"):
            name = self.__registered_name__
        return {"name": name, "started": self.started, "options": self.options}

    @hp.memoized_property
    def ticker(self):
        return hp.ATicker(
            self.every,
            max_time=self.num_seconds,
            min_wait=False,
            pauser=self.pauser,
            final_future=self.final_future,
            name=f"Animation({self.__class__.__name__})",
        )

    async def stream(self, animation_state):
        self.started = time.time()
        del self.ticker

        async def tick():
            async with self.ticker as ticks:
                async for result in ticks:
                    yield result

        def errors(e):
            if not isinstance(e, asyncio.CancelledError):
                log.error(hp.lc(error=e, error_type=type(e)))

        with hp.ChildOfFuture(self.final_future, name="Animation::streamer[stop_fut]") as stop_fut:
            async with hp.ResultStreamer(
                stop_fut,
                error_catcher=errors,
                exceptions_only_to_error_catcher=True,
                name=f"Animation({self.__class__.__name__})",
            ) as streamer:
                await streamer.add_generator(tick(), context=AnimationEvent.Types.TICK)
                await streamer.add_generator(
                    self.make_user_events(animation_state), context=AnimationEvent.Types.USER_EVENT
                )
                streamer.no_more_work()

                async for result in streamer:
                    if result.value is hp.ResultStreamer.GeneratorComplete:
                        continue
                    yield result

    def setup(self):
        pass

    @hp.memoized_property
    def rearranger(self):
        if self.align_parts_separate:
            return rearrange.Separate()
        elif self.align_parts_straight:
            return rearrange.Straight()
        elif self.align_parts_vertically:
            return rearrange.VerticalAlignment()

    def rearrange(self, canvas):
        arranger = self.rearranger
        if not arranger:
            return canvas
        return rearrange.rearrange(canvas, arranger, keep_colors=True)

    async def process_event(self, event):
        raise NotImplementedError()

    async def make_user_events(self, animation_state):
        if False:
            yield

    def __setattr__(self, key, value):
        if key == "every":
            self.change_every(value)
        else:
            super().__setattr__(key, value)

    def change_every(self, every):
        object.__setattr__(self, "every", every)
        self.ticker.change_after(self.every, set_new_every=True)
