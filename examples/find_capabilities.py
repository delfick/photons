from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_products_registry import capability_for_ids
from photons_messages import DeviceMessages

from delfick_project.logging import setup_logging
import logging


async def doit(collector):
    lan_target = collector.configuration["target_register"].resolve("lan")

    async for pkt, _, _ in lan_target.script(DeviceMessages.GetVersion()).run_with(FoundSerials()):
        if pkt | DeviceMessages.StateVersion:
            try:
                cap = capability_for_ids(pkt.product, pkt.vendor)
            except:
                pass
            else:
                print("{}: {}".format(pkt.serial, cap))


if __name__ == "__main__":
    setup_logging(level=logging.ERROR)
    collector = library_setup()
    collector.run_coro_as_main(doit(collector))
