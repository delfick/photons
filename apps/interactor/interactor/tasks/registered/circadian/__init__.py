from interactor.tasks.registered.circadian.options import Options
from interactor.tasks.register import registerer

from photons_control.script import FromGenerator
from photons_messages import LightMessages

from datetime import datetime


@registerer
def register(tasks):
    tasks.register("circadian", Options, run)


async def run(final_future, options):
    async def action(reference, sender, **kwargs):
        now = datetime.now()
        if int(now.strftime("%w")) not in options.days:
            return

        serials = []
        async for pkt in sender(LightMessages.GetColor(), reference, **kwargs):
            if pkt | LightMessages.LightState:
                if pkt.saturation < options.break_saturation_threshold:
                    serials.append(pkt.serial)

        if not serials:
            return

        bright, kelv = options.circadian.change_for(
            now,
            min_kelvin=options.min_kelvin,
            max_kelvin=options.max_kelvin,
            min_brightness=options.min_brightness,
            max_brightness=options.max_brightness,
        )

        async def apply_change(reference, sender, **kwargs):
            level = 0
            if now in options.lights_on_range:
                level = 65535

            if options.paused.is_set():
                return

            if options.change_power:
                yield LightMessages.SetLightPower(level=level, duration=1)
            yield LightMessages.SetWaveformOptional(brightness=bright, kelvin=kelv)

        yield FromGenerator(apply_change, reference_override=serials)

    await options.run(final_future, action)
