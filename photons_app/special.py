from photons_app.errors import DevicesNotFound, PhotonsAppError
from photons_app import helpers as hp

import binascii
import asyncio
import time

class SpecialReference:
    """
    Subclasses of this implement an await find_serials(afr, broadcast, find_timeout)
    that returns the serials to send messages to

    If broadcast is a boolean then we use afr.default_broadcast
    if broadcast is a falsey value then we use afr.default_broadcast
    else we use broadcast as is as the broadcast address

    find must be an async function that returns ``(found, serials)``
    where serials is ``["d073d500001", "d073d500002", ...]``
    and found is ``{target: {(service, (ip, port)), ...}, ...}``

    This class exposes:

    async find(afr, broadcast, find_timeout)
        calls ``await self.find_serials(afr, broadcast, find_timeout)``, then determines
        the list of serials from the result and memoizes ``(found, serials)``

        So that we only call it once regardless how many times find is called.
        The reset function is used to remove the cache

    reset()
        Reset our cache from calling find

    async find_serials(afr, broadcast, find_timeout)
        Must be implemented by the subclass, return ``found`` from this function
    """
    def __init__(self):
        self.found = hp.ResettableFuture()
        self.finding = hp.ResettableFuture()

    def broadcast_address(self, afr, broadcast):
        if type(broadcast) is bool:
            return afr.default_broadcast
        else:
            return broadcast or afr.default_broadcast

    async def find_serials(self, afr, broadcast, find_timeout):
        raise NotImplemented

    async def finish(self):
        """Hook for cleanup"""

    async def find(self, afr, broadcast, find_timeout):
        if self.finding.done():
            return await self.found

        self.finding.set_result(True)
        t = asyncio.get_event_loop().create_task(self.find_serials(afr, broadcast, find_timeout))

        def transfer(res):
            if res.cancelled():
                self.found.cancel()
                return

            exc = res.exception()
            if exc:
                self.found.set_exception(exc)
                return

            found = res.result()
            serials = [binascii.hexlify(key).decode() for key in found]
            self.found.set_result((found, serials))
        t.add_done_callback(transfer)
        return await self.found

    def reset(self):
        self.found.reset()
        self.finding.reset()

class FoundSerials(SpecialReference):
    """
    Can be used as the references value to say send packets
    to all the devices found on the network
    """
    async def find_serials(self, afr, broadcast, find_timeout):
        address = self.broadcast_address(afr, broadcast)
        return await afr.find_devices(address
            , raise_on_none=True, timeout=find_timeout
            )

class HardCodedSerials(SpecialReference):
    """
    A SpecialReference object that finds specific serials

    It will raise DevicesNotFound if it can't find any of the serials
    """
    def __init__(self, serials):
        if type(serials) is str:
            serials = serials.split(",")
        self.targets = [binascii.unhexlify(serial) for serial in serials]
        super(HardCodedSerials, self).__init__()

    async def find_serials(self, afr, broadcast, find_timeout):
        start = time.time()
        found = None
        address = self.broadcast_address(afr, broadcast)

        while not found or any(target[:6] not in found for target in self.targets):
            found = await afr.find_devices(address
                , raise_on_none=False, timeout=find_timeout
                )
            if time.time() - start > find_timeout:
                break

        missing = [binascii.hexlify(target[:6]).decode() for target in self.targets if target[:6] not in found]
        if missing:
            raise DevicesNotFound(missing=missing)

        return {target[:6]: found[target[:6]] for target in self.targets}

class ResolveReferencesFromFile(SpecialReference):
    """
    Resolves to the serials found in the provided file
    """
    def __init__(self, filename):
        self.filename = filename
        try:
            with open(self.filename) as fle:
                serials = [s.strip() for s in fle.readlines() if s.strip()]
        except OSError as error:
            raise PhotonsAppError("Failed to read serials from a file", filename=self.filename, error=error)

        if not serials:
            raise PhotonsAppError("Found no serials in file", filename=self.filename)

        self.reference = HardCodedSerials(serials)

    async def find(self, afr, broadcast, find_timeout):
        return await self.reference.find(afr, broadcast, find_timeout)

    def reset(self):
        self.reference.reset()
