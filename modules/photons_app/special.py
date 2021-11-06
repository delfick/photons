from photons_app.errors import PhotonsAppError, DevicesNotFound
from photons_app import helpers as hp

import binascii


class SpecialReference:
    """
    Subclasses of this implement an await ``find_serials(sender, *, timeout, broadcast=True)``
    that returns the serials to send messages to

    find must be an async function that returns ``(found, serials)``
    where serials is ``["d073d500001", "d073d500002", ...]``
    and found is ``{target: {(service, (ip, port)), ...}, ...}``
    """

    def __init__(self):
        self.found = hp.ResettableFuture(name=f"SpecialReference({self.__class__.__name__}.found)")
        self.finding = hp.ResettableFuture(
            name=f"SpecialReference({self.__class__.__name__}.finding"
        )

    async def find_serials(self, sender, *, timeout, broadcast=True):
        """Must be implemented by the subclass, return ``found`` from this function"""
        raise NotImplementedError()

    def missing(self, found):
        """Hook for saying if anything is missing from found"""
        return []

    def raise_on_missing(self, found):
        """Used to raise an exception if there are missing serials in found"""
        missing = self.missing(found)
        if missing:
            raise DevicesNotFound(missing=missing)

    async def find(self, sender, *, timeout, broadcast=True):
        """
        calls ``await self.find_serials(sender, timeout=timeout, broadcast=broadcast)``, then determines
        the list of serials from the result and memoizes ``(found, serials)``

        So that we only call it once regardless how many times find is called.
        The reset function is used to remove the cache
        """
        if self.finding.done():
            return await self.found

        self.finding.set_result(True)
        t = hp.get_event_loop().create_task(
            self.find_serials(sender, timeout=timeout, broadcast=broadcast)
        )

        def transfer(res):
            if res.cancelled():
                self.found.cancel()
                return

            exc = res.exception()
            if exc:
                if not self.found.done():
                    self.found.set_exception(exc)
                return

            found = res.result()
            serials = [binascii.hexlify(key).decode() for key in found]
            if not self.found.done():
                self.found.set_result((found, serials))

        t.add_done_callback(transfer)
        return await self.found

    def reset(self):
        """Reset our cache from calling find"""
        self.found.reset()
        self.finding.reset()


class FoundSerials(SpecialReference):
    """
    Can be used as the references value to say send packets
    to all the devices found on the network
    """

    async def find_serials(self, sender, *, timeout, broadcast=True):
        return await sender.find_devices(timeout=timeout, broadcast=broadcast, raise_on_none=True)


class HardCodedSerials(SpecialReference):
    """
    A SpecialReference object that finds specific serials

    It will raise DevicesNotFound if it can't find any of the serials
    """

    def __init__(self, serials):
        if type(serials) is str:
            serials = serials.split(",")

        self.targets = []
        for serial in serials:
            if isinstance(serial, bytes):
                serial = serial[:6]
            else:
                try:
                    serial = binascii.unhexlify(serial)[:6]
                except binascii.Error as error:
                    raise PhotonsAppError(
                        "Tried to treat a string as a serial but it wasn't valid hex",
                        error=f'"{type(error).__name__}: {error}"',
                        wanted=serial,
                    )
            self.targets.append(serial)

        self.serials = [binascii.hexlify(target).decode() for target in self.targets]

        super(HardCodedSerials, self).__init__()

    async def find_serials(self, sender, *, timeout, broadcast=True):
        found = getattr(sender, "found", {})

        if not all(target in found for target in self.targets):
            found, _ = await sender.find_specific_serials(
                self.serials, broadcast=broadcast, raise_on_none=False, timeout=timeout
            )

        return {target: found[target] for target in self.targets if target in found}

    def missing(self, found):
        return [binascii.hexlify(target).decode() for target in self.targets if target not in found]


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
            raise PhotonsAppError(
                "Failed to read serials from a file", filename=self.filename, error=error
            )

        if not serials:
            raise PhotonsAppError("Found no serials in file", filename=self.filename)

        self.serials = serials
        self.reference = HardCodedSerials(serials)

    async def find(self, sender, *, timeout, broadcast=True):
        return await self.reference.find(sender, timeout=timeout, broadcast=broadcast)

    def missing(self, found):
        """Hook for saying if anything is missing from found"""
        return self.reference.missing(found)

    def reset(self):
        self.reference.reset()
