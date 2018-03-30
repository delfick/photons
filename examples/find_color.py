from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_colour import ColourMessages

collector = library_setup()

lan_target = collector.configuration['target_register'].resolve("lan")

async def doit():
    msg = ColourMessages.GetColor()
    async for pkt, _, _ in lan_target.script(msg).run_with(FoundSerials()):
        hsbk = " ".join("{0}={1}".format(key, pkt.payload[key]) for key in ("hue", "saturation", "brightness", "kelvin"))
        print("{0}: {1}".format(pkt.serial, hsbk))

loop = collector.configuration["photons_app"].uvloop
loop.run_until_complete(doit())
