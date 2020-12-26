from interactor.commander import helpers as ihp
from interactor.commander.store import store

from photons_app import helpers as hp

from photons_control.device_finder import Filter, DeviceFinder

from delfick_project.norms import dictobj, sb


class DeviceChangeMixin(dictobj.Spec):
    finder = store.injected("finder")
    sender = store.injected("sender")

    matcher = dictobj.NullableField(
        sb.or_spec(sb.string_spec(), sb.dictionary_spec()),
        help="""
            What lights to target. If this isn't specified then we interact with all
            the lights that can be found on the network.

            This can be specfied as either a space separated key=value string or as
            a dictionary.

            For example,
            "label=kitchen,bathroom location_name=home"
            or
            ``{"label": ["kitchen", "bathroom"], "location_name": "home"}``

            See https://photons.delfick.com/interacting/device_finder.html#valid-filters
            for more information on what filters are available.
        """,
    )

    timeout = dictobj.Field(
        sb.float_spec, default=20, help="The max amount of time we wait for replies from the lights"
    )

    @hp.memoized_property
    def filter(self):
        return self.make_filter(self.matcher)

    @hp.memoized_property
    def device_finder(self):
        return DeviceFinder(self.filter, finder=self.finder)

    def make_filter(self, matcher):
        if matcher is None:
            return Filter.empty()

        elif type(matcher) is str:
            return Filter.from_key_value_str(matcher)

        else:
            return Filter.from_options(matcher)

    @ihp.memoized_iterable
    async def devices(self):
        async for device in self.finder.info(self.filter):
            yield device

    @ihp.memoized_iterable
    async def serials(self):
        async for device in self.finder.find(self.filter):
            yield device.serial

    async def send(self, msg, add_replies=True, result=None, serials=sb.NotSpecified, **kwargs):
        """
        Send our message and return a ResultBuilder from the results.

        If add_replies is False then we won't add packets to the result builder
        """
        if result is None:
            result = ihp.ResultBuilder()

        if serials is sb.NotSpecified:
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
