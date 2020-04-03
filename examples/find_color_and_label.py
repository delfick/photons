from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_messages import DeviceMessages, LightMessages

from delfick_project.logging import setup_logging
from collections import defaultdict
import logging


async def doit(collector):
    lan_target = collector.resolve_target("lan")

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


if __name__ == "__main__":
    setup_logging(level=logging.ERROR)
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))
