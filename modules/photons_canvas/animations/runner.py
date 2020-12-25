from photons_canvas.animations.infrastructure.finish import Finish
from photons_canvas.animations.run_options import make_run_options
from photons_canvas.animations.infrastructure.state import State
from photons_canvas.animations.infrastructure import cannons
from photons_canvas import Canvas

from photons_app.special import SpecialReference
from photons_app.errors import FoundNoDevices
from photons_app import helpers as hp

from photons_messages import LightMessages

from collections import defaultdict
import logging
import asyncio
import time

log = logging.getLogger("photons_canvas.animations.runner")


class AnimationRunner(hp.AsyncCMMixin):
    def __init__(
        self, sender, reference, run_options, *, final_future, animation_options=None, **kwargs
    ):
        self.sender = sender
        self.kwargs = kwargs
        self.reference = reference
        self.run_options = make_run_options(run_options, animation_options)
        self.final_future = hp.ChildOfFuture(
            final_future, name="AnimationRunner::__init__[final_future]"
        )
        self.original_canvas = Canvas()

        self.started = None
        self.collected = {}
        self.animations_ran = 0
        self.current_animation = None

        self.seen_serials = set()
        self.used_serials = set()

    @property
    def info(self):
        current_animation = None
        if self.current_animation is not None:
            current_animation = self.current_animation.info

        options = self.run_options.as_dict()
        if "animations" in options:
            del options["animations"]

        return {
            "started": self.started,
            "current_animation": current_animation,
            "animations_ran": self.animations_ran,
            "options": options,
        }

    async def start(self):
        return self

    async def finish(self, exc_typ=None, exc=None, tb=None):
        if hasattr(self, "final_future"):
            self.final_future.cancel()

    def make_cannon(self):
        if not self.run_options.noisy_network:
            return cannons.FastNetworkCannon(self.sender, cannons.Sem())
        else:
            sem = cannons.Sem(
                wait_timeout=self.kwargs.get("message_timeout", 1),
                inflight_limit=self.run_options.noisy_network,
            )
            return cannons.NoisyNetworkCannon(self.sender, sem)

    async def run(self):
        cannon = self.make_cannon()
        self.started = time.time()

        animations = self.run_options.animations_iter
        self.combined_state = State(self.final_future)

        async with self.reinstate(), hp.TaskHolder(
            self.final_future, name="AnimationRunner::run[task_holder]"
        ) as ts:
            self.transfer_error(
                ts, ts.add(self.animate(ts, cannon, self.combined_state, animations))
            )

            async for collected in self.collect_parts(ts):
                try:
                    if self.run_options.combined:
                        await self.combined_state.add_collected(collected)
                    else:
                        state = State(self.final_future)
                        await state.add_collected(collected)
                        self.transfer_error(ts, ts.add(self.animate(ts, cannon, state, animations)))
                except asyncio.CancelledError:
                    raise
                except Finish:
                    pass
                except Exception as error:
                    log.exception(hp.lc("Failed to add device", error=error))

    def transfer_error(self, ts, t):
        def process(res, fut):
            if ts.pending == 0 or len(self.combined_state.canvas.parts) == 0:
                fut.cancel()

        try:
            t.add_done_callback(
                hp.transfer_result(self.final_future, errors_only=True, process=process)
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self.final_future.done():
                self.final_future.set_exception(error)

    async def animate(self, ts, cannon, state, animations):
        ans = iter(animations())
        animation = None

        while True:
            self.animations_ran += 1

            try:
                make_animation, background = ans.send(animation)
            except StopIteration:
                break

            with hp.ChildOfFuture(
                self.final_future, name="AnimationRunner::animate[animation_fut]"
            ) as animation_fut:
                animation = make_animation(animation_fut, self.run_options.pauser)
                self.current_animation = animation

                try:
                    await state.set_animation(animation, background)

                    async for messages in state.messages():
                        by_serial = defaultdict(list)
                        for msg in messages:
                            by_serial[msg.serial].append(msg)

                        for serial, msgs in by_serial.items():
                            ts.add(cannon.fire(ts, serial, msgs))
                except asyncio.CancelledError:
                    raise
                except Finish:
                    pass
                except Exception:
                    log.exception("Unexpected error running animation")

    async def collect_parts(self, ts):
        async with hp.tick(
            self.run_options.rediscover_every,
            final_future=self.final_future,
            name="AnimationRunner::collect_parts[tick]",
        ) as ticks:
            async for _ in ticks:
                with hp.just_log_exceptions(log, reraise=[asyncio.CancelledError]):
                    serials = self.reference
                    if isinstance(serials, str):
                        serials = [serials]
                    elif isinstance(serials, SpecialReference):
                        self.reference.reset()
                        try:
                            _, serials = await self.reference.find(
                                self.sender, timeout=self.kwargs.get("find_timeout", 10)
                            )
                        except asyncio.CancelledError:
                            raise
                        except FoundNoDevices:
                            log.warning("Didn't find any devices")
                            continue

                    new = set(serials) - self.seen_serials
                    if not new:
                        continue

                    devices = []
                    collected = []
                    async for device, parts in self.parts_from_serials(new):
                        # Make sure the part isn't known by other animations currently running
                        if device.serial not in self.used_serials:
                            self.used_serials.add(device.serial)
                            self.collected[device.serial] = parts
                            devices.append(device)

                            def process(res):
                                if ts.pending == 0:
                                    self.final_future.cancel()

                            self.original_canvas.add_parts(*parts, with_colors=True)
                            collected.append(parts)

                    yield collected

                    for device in devices:
                        t = ts.add(self.turn_on(device.serial))
                        t.add_done_callback(process)

    @hp.asynccontextmanager
    async def reinstate(self):
        try:
            yield
        finally:
            if not self.run_options.reinstate_on_end:
                return
            await self.sender(
                list(self.original_canvas.restore_msgs()), message_timeout=1, errors=[]
            )

    async def turn_on(self, serial):
        msg = LightMessages.SetLightPower(level=65535, duration=1)
        await self.sender(msg, serial, **self.kwargs)

    async def parts_from_serials(self, serials):
        plans = self.sender.make_plans("parts_and_colors")
        async for serial, _, info in self.sender.gatherer.gather_per_serial(
            plans, serials, **self.kwargs
        ):
            self.seen_serials.add(serial)
            parts = info["parts_and_colors"]
            if parts:
                device = parts[0].device
                if device.cap.has_chain:
                    yield device, parts
