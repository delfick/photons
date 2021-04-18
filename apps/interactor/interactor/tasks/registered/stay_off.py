from interactor.tasks.time_specs import time_range_spec
from interactor.tasks.register import DeviceTask
from interactor.tasks.register import registerer

from photons_messages import LightMessages

from delfick_project.norms import dictobj, sb
from datetime import datetime


@registerer
def register(tasks):
    tasks.register("stay_off", Options, run)


class Options(DeviceTask):
    lights_off_range = dictobj.Field(
        time_range_spec(default_start="23:00", default_end="06:00"),
        help="""
    Specified as a tuple of ("HH:MM", "HH:MM"), all times starting as first time
    and ending at second time will result in telling the light to power off.
    """,
    )

    duration = dictobj.Field(
        sb.float_spec,
        default=1,
        help="""
    The duration used when turning off the lights.
    """,
    )

    async def status(self, name):
        status = await super().status(name)
        status.update(
            {
                "lights_off": datetime.now() in self.lights_off_range,
            }
        )
        return status


async def run(final_future, options):
    async def action(reference, sender, **kwargs):
        if datetime.now() in options.lights_off_range:
            yield LightMessages.SetLightPower(level=0, duration=options.duration)

    await options.run(final_future, action)
