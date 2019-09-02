from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_messages import DeviceMessages, LightMessages

from collections import defaultdict

collector = library_setup()

lan_target = collector.configuration["target_register"].resolve("lan")


async def doit():
    getter = [DeviceMessages.GetLabel(), LightMessages.GetColor()]

    info = defaultdict(dict)
    async for pkt, _, _ in lan_target.script(getter).run_with(FoundSerials()):
        if pkt | DeviceMessages.StateLabel:
            info[pkt.serial]["label"] = pkt.label
        elif pkt | LightMessages.LightState:
            hsbk = " ".join(
                "{0}={1}".format(key, pkt[key])
                for key in ("hue", "saturation", "brightness", "kelvin")
            )
            info[pkt.serial]["hsbk"] = hsbk

    for serial, details in info.items():
        print(f"{serial}: {details['label']}: {details['hsbk']}")


loop = collector.configuration["photons_app"].loop
loop.run_until_complete(doit())
