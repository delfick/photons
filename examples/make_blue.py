from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_control.colour import ColourParser
from photons_messages import DeviceMessages

from delfick_project.logging import setup_logging


async def doit(collector):
    lan_target = collector.resolve_target("lan")
    color_msg = ColourParser.color_to_msg("blue")
    on_msg = DeviceMessages.SetPower(level=65535)
    await lan_target.send([color_msg, on_msg], FoundSerials())


if __name__ == "__main__":
    setup_logging()
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))
