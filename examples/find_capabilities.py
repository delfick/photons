from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from photons_products_registry import capability_for_ids
from photons_device_messages import DeviceMessages

collector = library_setup()

lan_target = collector.configuration['target_register'].resolve("lan")

async def doit():
    async for pkt, _, _ in lan_target.script(DeviceMessages.GetVersion()).run_with(FoundSerials()):
        if pkt | DeviceMessages.StateVersion:
            cap = capability_for_ids(pkt.product, pkt.vendor)
            print("{}: {}".format(pkt.serial, cap))

loop = collector.configuration["photons_app"].loop
loop.run_until_complete(doit())
