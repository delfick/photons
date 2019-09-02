from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_control.transform import PowerToggle

collector = library_setup()

lan_target = collector.configuration["target_register"].resolve("lan")


async def doit():
    await lan_target.script(PowerToggle()).run_with_all(FoundSerials())


loop = collector.configuration["photons_app"].loop
loop.run_until_complete(doit())
