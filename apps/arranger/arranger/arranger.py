from arranger.colors import convert_K_to_RGB
from arranger.patterns import Patterns

from photons_app import helpers as hp

from photons_canvas.animations import Animation, AnimationRunner
from photons_canvas import point_helpers as php
from photons_messages import TileMessages

from delfick_project.norms import dictobj, sb
import colorsys
import logging
import asyncio

log = logging.getLogger("arranger.arranger")


def color_to_pixels(colors):
    for h, s, b, k in colors:
        if s > 0:
            rgb = colorsys.hsv_to_rgb(h / 360, s, b)
            rgb = tuple(int(p * 255) for p in rgb)
        else:
            if b < 0.01:
                rgb = (0, 0, 0)
            else:
                rgb = convert_K_to_RGB(k)

        yield f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


class Options(dictobj.Spec):
    arranger = dictobj.Field(sb.any_spec, wrapper=sb.required)
    patterns = dictobj.Field(sb.any_spec, wrapper=sb.required)


class State:
    def __init__(self, pattern_maker):
        self.pattern_maker = pattern_maker

        self.started = False
        self.part_to_pattern = {}

    @property
    def changed(self):
        return self.started and any(pattern.has_change for pattern in self.part_to_pattern.values())

    def add_parts(self, parts):
        for part in parts:
            pattern = self.part_to_pattern.get(part)
            if pattern is not None:
                del pattern.pattern_canvas
            else:
                self.part_to_pattern[part] = self.pattern_maker.make(part)

    def have_stream(self):
        self.started = True

    def change_part(self, part_event):
        action, part = part_event

        part = [p for p in self.part_to_pattern if p == part]
        if part:
            part = part[0]
        else:
            part = None

        pattern = self.part_to_pattern.get(part)
        if not self.started or pattern is None:
            return

        serial = part.device.serial
        part_number = part.part_number

        lc = hp.lc.using(serial=serial, part_number=part_number)

        if action == "highlight":
            log.info(lc("Highlighting part"))
            pattern.start_highlight()

        elif action == "changing":
            log.info(lc("Changing part"))
            pattern.is_changing()

        elif action == "changed":
            log.info(lc("Changed part"))
            pattern.changed()

    @property
    def next_layer(self):
        if not self.changed:
            return

        for pattern in self.part_to_pattern.values():
            pattern.progress()

        layers = {part: pattern.layer for part, pattern in self.part_to_pattern.items()}

        def layer(point, canvas):
            parts = list(canvas.point_to_parts[point])
            if parts:
                part = parts[0]
                if part in layers:
                    return layers[part](point, canvas)
            return canvas[point]

        return layer


class ArrangerAnimation(Animation):
    align_parts_separate = True

    def sent_messages(self, parts):
        result = []
        for part in parts:
            pixels = []
            for point, color in zip(
                part.points,
                color_to_pixels([php.Color.ZERO if c is None else c for c in part.colors]),
            ):
                col, row = php.Points.relative(point, part.bounds)
                pixels.append({"col": col, "row": row, "color": color, "key": str(point)})

            real_part = part.real_part
            result.append(
                (
                    {
                        "key": str(real_part),
                        "width": real_part.width,
                        "height": real_part.height,
                        "user_x": real_part.left,
                        "user_y": real_part.top,
                        "serial": real_part.device.serial,
                        "pixels": pixels,
                        "part_number": real_part.part_number,
                    },
                    real_part,
                )
            )
        self.options.arranger.parts_info.send_instruction(result)

    async def process_event(self, event):
        if not event.state:
            event.state = State(self.options.patterns)

        if event.is_sent_messages:
            self.sent_messages(list(event.state.part_to_pattern))
            return

        if event.is_new_device:
            event.state.add_parts(event.value)
            return

        if event.is_user_event:
            value = event.value
            if value == "have_stream":
                event.state.have_stream()
                return

            event.state.change_part(value)

            return

        if event.is_tick:
            return event.state.next_layer

    async def make_user_events(self, animation_state):
        async with hp.ResultStreamer(
            self.final_future, name="ArrangerAnimation::make_user_events[streamer]"
        ) as streamer:
            self.options.arranger.animation_streamer = streamer

            if self.options.arranger.progress_cbs:
                yield "have_stream"

            async for result in streamer:
                if result.successful:
                    yield result.value


class PartsInfo:
    def __init__(self, arranger):
        self.arranger = arranger
        self.reset()

    def get(self, part):
        if part in self.real_parts:
            return (self.real_parts[part], *self.locks[part])
        else:
            return None, None, None

    def reset(self):
        if hasattr(self, "locks"):
            for _, fut in self.locks.values():
                fut.cancel()

        self.info = []
        self.parts = {}
        self.locks = {}
        self.pixels = {}
        self.all_info = []
        self.real_parts = {}

    def start_instruction(self, progress_cb):
        sent = progress_cb.instructions

        try:
            progress_cb({"instruction": "parts", "parts": self.all_info}, do_log=False)
        except:
            log.exception("Failed to send progress")
        else:
            sent["parts"] = True

    def send_instruction(self, parts):
        self.update(parts)
        for progress_cb in self.arranger.progress_cbs:
            sent = progress_cb.instructions
            try:
                if "parts" in sent:
                    progress_cb({"instruction": "parts", "parts": self.info}, do_log=False)
                else:
                    progress_cb({"instruction": "parts", "parts": self.all_info}, do_log=False)
            except:
                log.exception("Failed to send progress")
            else:
                sent["parts"] = True

    def update(self, parts):
        self.info = []
        self.all_info = []

        for part, real_part in parts:
            self.all_info.append(dict(part))

            nxt = dict(part)
            if real_part not in self.pixels:
                self.pixels[real_part] = []

            if self.pixels[real_part] == part["pixels"]:
                del nxt["pixels"]

            if real_part not in self.parts:
                self.parts[real_part] = dict(part)
                self.locks[real_part] = (
                    asyncio.Lock(),
                    hp.ResettableFuture(name="PartsInfo::update[lock_fut]"),
                )

            self.real_parts[real_part] = real_part
            self.info.append(nxt)


class Arranger:
    def __init__(self, final_future, sender, reference, animation_options, cleaners):
        self.sender = sender
        self.cleaners = cleaners
        self.reference = reference
        self.final_future = final_future
        self.animation_options = animation_options

        self.running = False
        self.patterns = Patterns()
        self.parts_info = PartsInfo(self)
        self.progress_cbs = []
        self.animation_fut = None

        self.tasks = hp.TaskHolder(self.final_future, name="Arranger::__init__[tasks]")
        self.cleaners.append(self.tasks.finish)

        self.streamer = hp.ResultStreamer(self.final_future, name="Arranger::__init__[streamer]")
        self.cleaners.append(self.streamer.finish)

        self.animation_streamer = None

    async def animation_event(self, event):
        if self.animation_streamer:
            if not isinstance(event, (str, tuple)):
                await self.animation_streamer.add_generator(event)
            else:
                await self.animation_streamer.add_value(event)

    async def add_highlight(self, part):
        await self.animation_event(("highlight", part))

    async def change_position(self, serial, part_number, new_user_x, new_user_y):
        part, lock, fut = self.parts_info.get((serial, part_number))

        if part is None or fut.cancelled():
            return

        fut.reset()
        fut.set_result((new_user_x, new_user_y))

        if lock.locked():
            return

        lc = hp.lc.using(serial=part.device.serial, part_number=part.part_number)

        async def gen():
            nxt = None

            async with lock:
                while True:
                    key = await fut
                    if fut.cancelled():
                        return

                    if key == nxt:
                        return
                    nxt = key

                    original = {
                        "user_x": part.user_x,
                        "user_y": part.user_y,
                        "width": part.width,
                        "height": part.height,
                    }

                    new_position = {
                        "user_x": new_user_x / 8,
                        "user_y": new_user_y / 8,
                        "width": part.width,
                        "height": part.height,
                    }
                    part.update(**new_position)

                    yield "changing", part

                    try:
                        new_position = await self._change_position(
                            part, new_position["user_x"], new_position["user_y"]
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception as error:
                        part.update(**original)
                        log.error(lc("Failed to change position", error=error))
                    else:
                        if new_position is not None:
                            k = await fut
                            if k == key:
                                part.update(**new_position)
                    finally:
                        yield "changed", part

        await self.animation_event(gen())

    async def _change_position(self, part, new_user_x, new_user_y):
        part.update(new_user_x, new_user_y, part.width, part.height)

        msg = TileMessages.SetUserPosition(
            tile_index=part.part_number, user_x=part.user_x, user_y=part.user_y, res_required=False
        )

        await self.sender(msg, part.device.serial, message_timeout=2)

        plans = self.sender.make_plans("parts")

        async for serial, _, info in self.sender.gatherer.gather(
            plans, part.device.serial, message_timeou=2
        ):
            for found in info:
                if found.part_number != part.part_number:
                    continue

                    new_position = {
                        "user_x": found.user_x,
                        "user_y": found.user_y,
                        "width": found.width,
                        "height": found.height,
                    }

                    log.info(
                        hp.lc(
                            "Replaced position",
                            serial=serial,
                            part_number=part.part_number,
                            user_x=found.user_x,
                            user_y=found.user_y,
                        )
                    )
                    return new_position

    @hp.asynccontextmanager
    async def add_stream(self, progress_cb):
        log.info("Adding stream")
        try:
            self.progress_cbs.append(progress_cb)
            progress_cb.instructions = {}
            self.parts_info.start_instruction(progress_cb)
            await self.animation_event("have_stream")
            yield
        finally:
            log.info("Removing stream")
            self.progress_cbs = [pc for pc in self.progress_cbs if pc != progress_cb]
            if not self.progress_cbs and self.animation_fut:
                self.animation_fut.cancel()

    async def run(self):
        if self.running or self.final_future.done():
            return

        self.running = True
        self.animation_fut = hp.ChildOfFuture(
            self.final_future, name="Arranger::run[animation_fut]"
        )

        run_options = {
            "animations": [
                [(ArrangerAnimation, Options), {"arranger": self, "patterns": self.patterns}]
            ],
            "reinstate_on_end": True,
        }

        try:
            log.info("Starting arranger animation")
            runner = AnimationRunner(
                self.sender,
                self.reference,
                run_options,
                final_future=self.animation_fut,
                message_timeout=1,
                error_catcher=lambda e: False,
                animation_options=self.animation_options,
            )

            async with runner:
                await runner.run()
        finally:
            self.parts_info.reset()

            self.running = False

            self.animation_fut.cancel()
            self.animation_fut = None

            self.animation_streamer = None
