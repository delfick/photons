#!/usr/bin/python -ci=__import__;o=i("os");s=i("sys");a=s.argv;p=o.path;y=p.join(p.dirname(a[1]),".python");o.execv(y,a)

from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_messages import DeviceMessages
from photons_products import Products

from delfick_project.logging import setup_logging
import logging


async def doit(collector):
    lan_target = collector.resolve_target("lan")

    async for pkt in lan_target.send(DeviceMessages.GetVersion(), FoundSerials()):
        if pkt | DeviceMessages.StateVersion:
            product = Products[pkt.vendor, pkt.product]
            print(f"{pkt.serial}: {product.as_dict()}")


if __name__ == "__main__":
    setup_logging(level=logging.ERROR)
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))
