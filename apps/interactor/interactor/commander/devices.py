import typing as tp

import attrs
import strcs
from interactor.commander import helpers as ihp
from interactor.commander.store import creator
from photons_app.special import FoundSerials, HardCodedSerials
from photons_control.device_finder import Device
from photons_control.device_finder import DeviceFinder as DeviceFinderSelector
from photons_control.device_finder import Filter, Finder
from photons_transport.comms.base import Communication

from . import selector


@attrs.define
class DeviceFinder:
    finder: tp.Annotated[Finder, strcs.FromMeta("finder")]
    sender: tp.Annotated[Communication, strcs.FromMeta("sender")]

    selector: selector.Selector
    timeout: int

    @ihp.memoized_async
    async def filter(self):
        match self.selector.selector:
            case FoundSerials():
                return self.make_filter(None)
            case HardCodedSerials(serials=serials):
                return self.make_filter({"serial": serials})
            case DeviceFinderSelector(fltr=fltr):
                return fltr
            case _:
                _, serials = await self.selector.selector.find(self.sender, timeout=self.timeout)
                return self.make_filter({"serial": serials})

    _filter: Filter = attrs.field(init=False)

    @ihp.memoized_async
    async def device_finder(self):
        return DeviceFinderSelector(await self.filter, finder=self.finder)

    _device_finder: DeviceFinderSelector = attrs.field(init=False)

    def make_filter(self, matcher: dict | str | None) -> Filter:
        if matcher is None:
            return Filter.empty()

        elif type(matcher) is str:
            return Filter.from_key_value_str(matcher)

        else:
            return Filter.from_options(matcher)

    @ihp.memoized_iterable
    async def devices(self):
        async for device in self.finder.info(await self.filter):
            yield device

    _devices: list[Device] = attrs.field(init=False)

    @ihp.memoized_iterable
    async def serials(self):
        async for device in self.finder.find(await self.filter):
            yield device.serial

    _serials: list[str] = attrs.field(init=False)

    async def send(self, msg, add_replies=True, result=None, serials=strcs.NotSpecified, **kwargs):
        """
        Send our message and return a ResultBuilder from the results.

        If add_replies is False then we won't add packets to the result builder
        """
        if result is None:
            result = ihp.ResultBuilder()

        if serials is strcs.NotSpecified:
            serials = await self.serials

        result.add_serials(serials)

        options = dict(kwargs)
        if "message_timeout" not in options:
            options["message_timeout"] = self.timeout
        if "find_timeout" not in options:
            options["find_timeout"] = self.timeout

        async for pkt in self.sender(msg, serials, error_catcher=result.error, **options):
            if add_replies:
                result.add_packet(pkt)

        return result


@creator(DeviceFinder)
def create_device_finder(val: object, /) -> strcs.ConvertResponse[DeviceFinder]:
    if not isinstance(val, dict):
        return

    if val.get("timeout") in (None, -1):
        val["timeout"] = 20

    return val
