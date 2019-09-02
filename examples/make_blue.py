from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_messages import DeviceMessages
from photons_colour import Parser

collector = library_setup()

lan_target = collector.configuration["target_register"].resolve("lan")


async def doit():
    color_msg = Parser.color_to_msg("blue")
    on_msg = DeviceMessages.SetPower(level=65535)
    script = lan_target.script([color_msg, on_msg])
    await script.run_with_all(FoundSerials())


loop = collector.configuration["photons_app"].loop
loop.run_until_complete(doit())
