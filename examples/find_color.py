#!/usr/bin/python3 -ci=__import__;o=i("os");s=i("sys");a=s.argv;p=o.path;y=p.join(p.dirname(a[1]),".python");o.execv(y,a)

import logging

from delfick_project.logging import setup_logging
from photons_app.executor import library_setup
from photons_app.special import FoundSerials
from photons_messages import LightMessages


async def doit(collector):
    lan_target = collector.resolve_target("lan")

    msg = LightMessages.GetColor()
    async for pkt in lan_target.send(msg, FoundSerials()):
        if pkt | LightMessages.LightState:
            hsbk = " ".join(f"{key}={pkt.payload[key]}" for key in ("hue", "saturation", "brightness", "kelvin"))
            print(f"{pkt.serial}: {hsbk}")


if __name__ == "__main__":
    setup_logging(level=logging.ERROR)
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))
