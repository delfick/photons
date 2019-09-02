from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_messages import LightMessages

collector = library_setup()

lan_target = collector.configuration["target_register"].resolve("lan")


async def doit():
    msg = LightMessages.GetColor()
    async for pkt, _, _ in lan_target.script(msg).run_with(FoundSerials()):
        hsbk = " ".join(
            "{0}={1}".format(key, pkt.payload[key])
            for key in ("hue", "saturation", "brightness", "kelvin")
        )
        print("{0}: {1}".format(pkt.serial, hsbk))


loop = collector.configuration["photons_app"].loop
loop.run_until_complete(doit())
