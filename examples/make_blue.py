from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_messages import DeviceMessages
from photons_colour import Parser

from delfick_project.logging import setup_logging


async def doit(collector):
    lan_target = collector.configuration["target_register"].resolve("lan")
    color_msg = Parser.color_to_msg("blue")
    on_msg = DeviceMessages.SetPower(level=65535)
    script = lan_target.script([color_msg, on_msg])
    await script.run_with_all(FoundSerials())


if __name__ == "__main__":
    setup_logging()
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))
