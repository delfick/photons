from photons_canvas.animations.infrastructure.events import AnimationEvent
from photons_canvas.animations.infrastructure.finish import Finish
from photons_canvas import Canvas

from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from contextlib import contextmanager
from collections import defaultdict
import logging
import asyncio
import sys

log = logging.getLogger("photons_canvas.infrastructure.state")


class AnimationError(PhotonsAppError):
    pass


@contextmanager
def catch_finish(reraise_exceptions=True):
    try:
        yield
    except asyncio.CancelledError:
        raise
    except Finish:
        pass
    except:
        if reraise_exceptions:
            raise
        log.exception("Unexpected error")


class State:
    def __init__(self, final_future):
        self.final_future = final_future

        self.state = None
        self.by_device = defaultdict(list)
        self.animation = None
        self.background = None

        self.canvas = None

    def __bool__(self):
        return self.canvas is not None and bool(self.canvas.parts)

    @hp.asynccontextmanager
    async def ensure_error_event(self):
        try:
            yield
        except (Finish, asyncio.CancelledError):
            raise
        except:
            exc_typ, exc, tb = sys.exc_info()

            handled = False

            try:
                handled = await self.process_event(AnimationEvent.Types.ERROR, exc)
            except asyncio.CancelledError:
                raise
            except:
                log.exception("Failed to process event")
                raise Finish("Failed to process error")

            if not handled:
                log.exception("unhandled error", exc_info=(exc_typ, exc, tb))
                raise Finish("Unhandled error")

    async def add_collected(self, collected):
        for parts in collected:
            self.add_parts(parts)

        if self.animation:
            # Do this after adding all parts so state.canvas has all parts for all devices
            for parts in collected:
                parts = [p for p in self.canvas.parts if p in parts]
                await self.process_event(AnimationEvent.Types.NEW_DEVICE, parts)

    async def set_animation(self, animation, background):
        if self.animation is not animation:
            self.state = None
            self.animation = animation
            self.background = background

            self.canvas = Canvas()
            await self.add_collected(
                [[p.clone_real_part() for p in ps] for ps in self.by_device.values()]
            )

    def add_parts(self, parts):
        for part in parts:
            self.by_device[part.device].append(part)

        if not self.animation:
            return

        self.canvas.add_parts(*parts, with_colors=self.background)
        self.canvas = self.animation.rearrange(self.canvas)

        self.by_device.clear()
        for part in self.canvas.parts:
            self.by_device[part.device].append(part)

    async def messages(self, device=None):
        started = False

        try:
            with catch_finish():
                await self.process_event(AnimationEvent.Types.STARTED)
                started = True

                async for result in self.animation.stream(self):
                    async with self.ensure_error_event():
                        if not result.successful:
                            try:
                                raise result.value
                            finally:
                                del result

                        if result.context is AnimationEvent.Types.TICK:
                            if not self:
                                continue
                            async for messages in self.send_canvas(
                                await self.process_event(AnimationEvent.Types.TICK)
                            ):
                                yield messages

                        else:
                            await self.process_event(result.context, result.value)
        finally:
            if started and not sys.exc_info()[0]:
                with catch_finish(reraise_exceptions=False):
                    await asyncio.sleep(self.animation.every)
                    async for messages in self.send_canvas(
                        await self.process_event(AnimationEvent.Types.ENDED, force=True)
                    ):
                        yield messages

    async def send_canvas(self, layer):
        if not layer:
            return

        self.canvas = self.canvas.clone()

        msgs = list(
            self.canvas.msgs(
                layer,
                onto=self.canvas.points,
                duration=self.animation.duration,
                acks=self.animation.retries,
                randomize=self.animation.random_orientations,
            )
        )
        yield msgs

        if msgs:
            await self.process_event(AnimationEvent.Types.SENT_MESSAGES, msgs)

    async def process_event(self, typ, value=None, force=False):
        if not force and self.final_future.done():
            raise asyncio.CancelledError()

        if not self.animation:
            return

        event = AnimationEvent(typ, value, self)
        try:
            return await self.animation.process_event(event)
        except asyncio.CancelledError:
            raise
        except Finish:
            raise
        except NotImplementedError:
            log.error(
                hp.lc("Animation does not implement process_event", animation=type(self.animation))
            )
            raise Finish("Animation does not implement process_event")
        except Exception as error:
            log.exception(error)
            raise Finish("Animation failed to process event")
