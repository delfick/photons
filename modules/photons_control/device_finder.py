from photons_app.errors import PhotonsAppError, FoundNoDevices, RunErrors
from photons_app.special import FoundSerials, SpecialReference
from photons_app.actions import an_action
from photons_app import helpers as hp

from photons_messages import DeviceMessages, LightMessages
from photons_control.script import FromGenerator
from photons_products import Products

from delfick_project.norms import dictobj, sb, Meta, BadSpecValue
from urllib.parse import parse_qs
from functools import partial
import traceback
import itertools
import binascii
import logging
import fnmatch
import asyncio
import json
import time
import enum
import sys
import re

log = logging.getLogger("photons_control.device_finder")


def log_errors(msg, result):
    e = result.value
    traceback.clear_frames(e.__traceback__)

    if isinstance(e, RunErrors) and len(e.errors) == 1:
        e = e.errors[0]

    if isinstance(e, asyncio.CancelledError):
        return

    exc_info = None
    if not isinstance(e, PhotonsAppError):
        exc_info = (type(e), e, e.__traceback__)

    lc = hp.lc
    if exc_info is None:
        lc = lc.using(exc_typ=type(e).__name__, error=e)

    log.error(lc(msg), exc_info=exc_info)


async def make_device_finder(sender, make_reference, reference, extra):
    if reference not in ("", None, sb.NotSpecified):
        reference = make_reference(reference)
    else:
        reference = DeviceFinder.from_options(extra)

    if not isinstance(reference, DeviceFinder):
        found, serials = await reference.find(sender, timeout=5)
        reference.raise_on_missing(found)
        reference = DeviceFinder.from_options({"serial": serials})

    return reference


@an_action(needs_target=True)
async def device_finder_serials(collector, target, reference, **kwargs):
    """
    Find serials that match the provided filter

    ``find_with_filter -- '{"label": ["kitchen", "loungeroom"], "location_name": "home"}'``

    Not providing options after the ``--`` will find all devices on the network.
    """
    async with target.session() as sender:
        reference = await make_device_finder(
            sender, collector.reference_object, reference, collector.photons_app.extra_as_json
        )

        _, serials = await reference.find(sender, timeout=5)

        for serial in serials:
            print(serial)


@an_action(needs_target=True)
async def device_finder_info(collector, target, reference, **kwargs):
    """
    Print information about devices from the device finder

    ``device_finder_info -- '{"label": ["kitchen", "loungeroom"], "location_name": "office"}'``

    Not providing options after the ``--`` will find all devices on the network.
    """
    async with target.session() as sender:
        reference = await make_device_finder(
            sender, collector.reference_object, reference, collector.photons_app.extra_as_json
        )

        async for device in reference.info(sender):
            print(device.serial)
            print(
                "\n".join(
                    f"  {line}"
                    for line in json.dumps(device.info, sort_keys=True, indent="  ").split("\n")
                )
            )


regexes = {"key_value": re.compile(r"^(?P<key>[\w_]+)=(?P<value>.+)")}


class InvalidJson(PhotonsAppError):
    desc = "String is invalid json"


class Collection(dictobj.Spec):
    """
    Represents either a group or a location. It understands the relationship
    between label and updated_at such that the collections' name corresponds
    to the name with the newest updated_at property
    """

    typ = dictobj.Field(sb.string_spec, wrapper=sb.required)
    uuid = dictobj.Field(sb.string_spec, wrapper=sb.required)
    name = dictobj.Field(sb.string_spec, default="")

    def setup(self, *args, **kwargs):
        super(Collection, self).setup(*args, **kwargs)
        self.newest_timestamp = None

    def add_name(self, timestamp, name):
        if self.newest_timestamp is None or self.newest_timestamp < timestamp:
            self.name = name
            self.newest_timestamp = timestamp

    def __eq__(self, other):
        return isinstance(other, Collection) and self.typ == other.typ and self.uuid == other.uuid


class Collections:
    """
    A collection of collections!

    This knows about groups and locations.
    """

    def __init__(self):
        self.collections = {"group": {}, "location": {}}
        self.collection_spec = Collection.FieldSpec()

    def add_group(self, uuid, updated_at, label):
        return self.add_collection("group", uuid, updated_at, label)

    def add_location(self, uuid, updated_at, label):
        return self.add_collection("location", uuid, updated_at, label)

    def add_collection(self, typ, uuid, updated_at, label):
        if uuid not in self.collections[typ]:
            self.collections[typ][uuid] = self.collection_spec.empty_normalise(typ=typ, uuid=uuid)

        collection = self.collections[typ][uuid]
        collection.add_name(updated_at, label)
        return collection


class boolean(sb.Spec):
    """Take in int/string/bool and convert to a boolean"""

    def normalise_filled(self, meta, val):
        if isinstance(val, int):
            return False if val == 0 else True
        elif isinstance(val, str):
            return False if val.lower() in ("no", "false") else True
        elif isinstance(val, list):
            if len(val) != 1:
                raise BadSpecValue(
                    "Lists can only be turned into a boolean if they have only one item",
                    got=len(val),
                    meta=meta,
                )
            return boolean().normalise(meta.indexed_at(0), val[0])
        return sb.boolean().normalise(meta, val)


class str_ranges(sb.Spec):
    """
    Take in a string of the form ``a-b,c-d,e`` and convert to ``[(a, b), (c, d), (e, e)]``

    Will also work if the value is already of the form [(a, b), (c, d), (e, e)]
    or if the value is a list of ["a-b", "c-d", "e"]
    """

    def normalise_filled(self, meta, val):
        if type(val) is str:
            val = val.split(",")

        if type(val) is list:
            res = []
            for pair in val:
                if type(pair) is not str:
                    res.append(pair)
                else:
                    if "-" in pair:
                        res.append(tuple(v.strip() for v in pair.split("-", 1)))
                    else:
                        res.append((pair.strip(), pair.strip()))
            val = res

        return sb.listof(sb.tuple_spec(sb.float_spec(), sb.float_spec())).normalise(meta, val)


class Filter(dictobj.Spec):
    refresh_info = dictobj.Field(boolean, default=False)
    refresh_discovery = dictobj.Field(boolean, default=False)

    serial = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)

    label = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)
    power = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)

    group_id = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)
    group_name = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)

    location_id = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)
    location_name = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)

    hue = dictobj.Field(str_ranges, wrapper=sb.optional_spec)
    saturation = dictobj.Field(str_ranges, wrapper=sb.optional_spec)
    brightness = dictobj.Field(str_ranges, wrapper=sb.optional_spec)
    kelvin = dictobj.Field(str_ranges, wrapper=sb.optional_spec)

    firmware_version = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)

    product_id = dictobj.Field(sb.listof(sb.integer_spec()), wrapper=sb.optional_spec)

    cap = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)

    @classmethod
    def from_json_str(kls, s):
        """
        Interpret s as a json string and use it to create a Filter using from_options
        """
        try:
            options = json.loads(s)
        except (TypeError, ValueError) as error:
            raise InvalidJson(error=error)
        else:
            if type(options) is not dict:
                raise InvalidJson("Expected a dictionary", got=type(options))
            return kls.from_options(options)

    @classmethod
    def from_key_value_str(kls, s):
        """
        Create a Filter based on the ``key=value key2=value2`` string provided.

        Each key=value pair is separated by a space and arrays are formed by
        separating values by a comma.

        Note that values may not have spaces in them because of how we split
        the key=value pairs. If you need values to have spaces use from_json_str
        or from_options.
        """
        options = {}

        for part in s.split(" "):
            m = regexes["key_value"].match(part)
            if m:
                groups = m.groupdict()
                if groups["key"] not in (
                    "hue",
                    "saturation",
                    "brightness",
                    "kelvin",
                    "refresh_info",
                    "refresh_discovery",
                ):
                    options[groups["key"]] = groups["value"].split(",")
                else:
                    options[groups["key"]] = groups["value"]

        return kls.from_options(options)

    @classmethod
    def from_url_str(kls, s):
        """
        Create a Filter based on ``key=value&otherkey=value2`` string provided

        Where the string is url encoded.
        """
        return kls.from_options(parse_qs(s))

    @classmethod
    def from_kwargs(kls, **kwargs):
        """Create a Filter based on the provided kwarg arguments"""
        return kls.from_options(kwargs)

    @classmethod
    def empty(kls, refresh_info=False, refresh_discovery=False):
        """Create an empty filter"""
        return kls.from_options(
            {"refresh_info": refresh_info, "refresh_discovery": refresh_discovery}
        )

    @classmethod
    def from_options(kls, options):
        """Create a Filter based on the provided dictionary"""
        if isinstance(options, dict):
            for option in options:
                if option not in kls.fields:
                    log.warning(hp.lc("Unknown option provided for filter", wanted=option))

        return kls.FieldSpec().normalise(Meta.empty(), options)

    def has(self, field):
        """Say whether the filter has an opinion on this field"""
        return field in self.fields and self[field] != sb.NotSpecified

    def matches(self, field_name, val):
        """
        Says whether this filter matches against provided filed_name/val pair

        * Always say False for ``refresh_info`` and ``refresh_discovery``
        * Say False if the value on the filter for field_name is NotSpecified
        * Say True if a hsbk value and we are within the range specified in val
        * Say True if value on the filter is a list, and val exists in that list
        * Say True if value on the filter is not a list and matches val
        """
        if field_name in ("refresh_info", "refresh_discovery"):
            return False

        if field_name in self.fields:
            f = self[field_name]
            if f is not sb.NotSpecified:
                if field_name in ("hue", "saturation", "brightness", "kelvin"):
                    return any(val >= pair[0] and val <= pair[1] for pair in f)

                if field_name in self.label_fields and type(val) is str:
                    if type(f) is list:
                        return any(fnmatch.fnmatch(val, pat) for pat in f)
                    else:
                        return fnmatch.fnmatch(val, f)

                if type(f) is list:
                    if type(val) is list:
                        return any(v in val for v in f)
                    else:
                        return val in f
                else:
                    return val == f

        return False

    @property
    def matches_all(self):
        """True if this Filter matches against any device"""
        for field in self.fields:
            if field not in ("refresh_info", "refresh_discovery"):
                if self[field] != sb.NotSpecified:
                    return False
        return True

    @property
    def points(self):
        """Provide InfoPoints enums that match the keys on this filter with values"""
        for e in InfoPoints:
            for key in e.value.keys:
                if self[key] != sb.NotSpecified:
                    yield e

    @property
    def label_fields(self):
        return ("label", "location_name", "group_name")


class DeviceFinder(SpecialReference):
    def __init__(self, fltr, *, finder=None):
        self.fltr = fltr
        self.finder = finder
        super().__init__()

    @hp.asynccontextmanager
    async def a_finder(self, sender):
        finder = None
        try:
            if self.finder:
                yield self.finder
            else:
                finder = Finder(sender)
                yield finder
        finally:
            exc_info = sys.exc_info()

            if finder:
                await finder.finish(*exc_info)

    async def find_serials(self, sender, *, timeout, broadcast=True):
        targets = []

        async with self.a_finder(sender) as finder:
            async for device in finder.find(self.fltr):
                targets.append(binascii.unhexlify(device.serial)[:6])

        return {target: sender.found[target] for target in targets}

    async def info(self, sender):
        async with self.a_finder(sender) as finder:
            async for device in finder.info(self.fltr):
                yield device

    async def serials(self, sender):
        async with self.a_finder(sender) as finder:
            async for device in finder.find(self.fltr):
                yield device

    async def finish(self, exc_typ=None, exc=None, tb=None):
        pass

    @classmethod
    def from_json_str(kls, s, finder=None):
        return DeviceFinder(Filter.from_json_str(s), finder=finder)

    @classmethod
    def from_key_value_str(kls, s, finder=None):
        return DeviceFinder(Filter.from_key_value_str(s), finder=finder)

    @classmethod
    def from_url_str(kls, s, finder=None):
        return DeviceFinder(Filter.from_url_str(s), finder=finder)

    @classmethod
    def from_kwargs(kls, **kwargs):
        finder = None
        if "finder" in kwargs:
            finder = kwargs.pop("finder")
        return DeviceFinder(Filter.from_kwargs(**kwargs), finder=finder)

    @classmethod
    def empty(kls, refresh_info=False, refresh_discovery=False, finder=None):
        return DeviceFinder(
            Filter.empty(refresh_info=refresh_info, refresh_discovery=refresh_discovery),
            finder=finder,
        )

    @classmethod
    def from_options(kls, options, finder=None):
        return DeviceFinder(Filter.from_options(options), finder=finder)


class Point:
    """Used as the value in the InfoPoints enum"""

    def __init__(self, msg, keys, refresh):
        self.msg = msg
        self.keys = keys
        self.refresh = refresh


class InfoPoints(enum.Enum):
    """
    Enum used to determine what information is required for what keys
    """

    LIGHT_STATE = Point(
        LightMessages.GetColor(),
        ["label", "power", "hue", "saturation", "brightness", "kelvin"],
        10,
    )
    VERSION = Point(DeviceMessages.GetVersion(), ["product_id", "cap"], None)
    FIRMWARE = Point(DeviceMessages.GetHostFirmware(), ["firmware_version"], 300)
    GROUP = Point(DeviceMessages.GetGroup(), ["group_id", "group_name"], 60)
    LOCATION = Point(DeviceMessages.GetLocation(), ["location_id", "location_name"], 60)


class Device(dictobj.Spec):
    """
    An object representing a single device.

    Users shouldn't have to interact with these directly
    """

    limit = dictobj.NullableField(sb.any_spec)
    serial = dictobj.Field(sb.string_spec, wrapper=sb.required)

    label = dictobj.Field(sb.string_spec, wrapper=sb.optional_spec)
    power = dictobj.Field(sb.string_spec, wrapper=sb.optional_spec)

    group = dictobj.Field(sb.any_spec, wrapper=sb.optional_spec)
    location = dictobj.Field(sb.any_spec, wrapper=sb.optional_spec)

    hue = dictobj.Field(sb.integer_spec, wrapper=sb.optional_spec)
    saturation = dictobj.Field(sb.float_spec, wrapper=sb.optional_spec)
    brightness = dictobj.Field(sb.float_spec, wrapper=sb.optional_spec)
    kelvin = dictobj.Field(sb.integer_spec, wrapper=sb.optional_spec)

    firmware_version = dictobj.Field(sb.string_spec, wrapper=sb.optional_spec)

    product_id = dictobj.Field(sb.integer_spec, wrapper=sb.optional_spec)

    cap = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)

    def setup(self, *args, **kwargs):
        super().setup(*args, **kwargs)
        self.point_futures = {
            e: hp.ResettableFuture(name=f"Device({self.serial})::setup[point_futures.{e.name}]")
            for e in InfoPoints
        }
        self.point_futures[None] = hp.ResettableFuture(
            name=f"Device::setup({self.serial})[point_futures.None]"
        )
        self.refreshing = hp.ResettableFuture(name=f"Device({self.serial})::[refreshing]")

    @hp.memoized_property
    def final_future(self):
        return hp.create_future(name=f"Device({self.serial})::final_future")

    @property
    def property_fields(self):
        return ["group_id", "group_name", "location_name", "location_id"]

    @property
    def group_id(self):
        if self.group is sb.NotSpecified:
            return sb.NotSpecified
        return self.group.uuid

    @property
    def group_name(self):
        if self.group is sb.NotSpecified:
            return sb.NotSpecified
        return self.group.name

    @property
    def location_name(self):
        if self.location is sb.NotSpecified:
            return sb.NotSpecified
        return self.location.name

    @property
    def location_id(self):
        if self.location is sb.NotSpecified:
            return sb.NotSpecified
        return self.location.uuid

    def as_dict(self):
        actual = super(Device, self).as_dict()
        del actual["group"]
        del actual["limit"]
        del actual["location"]
        for key in self.property_fields:
            actual[key] = self[key]
        return actual

    @property
    def info(self):
        return {k: v for k, v in self.as_dict().items() if v is not sb.NotSpecified}

    def matches_fltr(self, fltr):
        """
        Say whether we match against the provided filter
        """
        if fltr.matches_all:
            return True

        fields = [f for f in self.fields if f != "limit"] + self.property_fields
        has_atleast_one_field = False

        for field in fields:
            val = self[field]
            if val is not sb.NotSpecified:
                has_field = fltr.has(field)
                if has_field:
                    has_atleast_one_field = True
                if has_field and not fltr.matches(field, val):
                    return False

        return has_atleast_one_field

    def set_from_pkt(self, pkt, collections):
        """
        Set information from the provided pkt.

        collections is used for determining the group/location based on the pkt.

        We return a InfoPoints enum representing what type of information was set.
        """
        if pkt | LightMessages.LightState:
            self.label = pkt.label
            self.power = "off" if pkt.power == 0 else "on"
            self.hue = pkt.hue
            self.saturation = pkt.saturation
            self.brightness = pkt.brightness
            self.kelvin = pkt.kelvin
            return InfoPoints.LIGHT_STATE

        elif pkt | DeviceMessages.StateGroup:
            uuid = binascii.hexlify(pkt.group).decode()
            self.group = collections.add_group(uuid, pkt.updated_at, pkt.label)
            return InfoPoints.GROUP

        elif pkt | DeviceMessages.StateLocation:
            uuid = binascii.hexlify(pkt.location).decode()
            self.location = collections.add_location(uuid, pkt.updated_at, pkt.label)
            return InfoPoints.LOCATION

        elif pkt | DeviceMessages.StateHostFirmware:
            self.firmware_version = f"{pkt.version_major}.{pkt.version_minor}"
            return InfoPoints.FIRMWARE

        elif pkt | DeviceMessages.StateVersion:
            self.product_id = pkt.product
            product = Products[pkt.vendor, pkt.product]
            cap = []
            for prop in (
                "has_ir",
                "has_hev",
                "has_color",
                "has_chain",
                "has_relays",
                "has_matrix",
                "has_buttons",
                "has_multizone",
                "has_variable_color_temp",
            ):
                if getattr(product.cap, prop):
                    cap.append(prop[4:])
                else:
                    cap.append("not_{}".format(prop[4:]))
            self.cap = sorted(cap)
            return InfoPoints.VERSION

    def points_from_fltr(self, fltr):
        """Return the relevant messages from this filter"""
        for e in InfoPoints:
            if fltr is None or any(fltr.has(key) for key in e.value.keys) or fltr.matches_all:
                if fltr is not None and fltr.refresh_info:
                    if e.value.refresh is not None:
                        self.point_futures[e].reset()
                yield e

    async def finish(self, exc_typ=None, exc=None, tb=None):
        self.final_future.cancel()
        del self.final_future

    async def refresh_information_loop(self, sender, time_between_queries, collections):
        if self.refreshing.done():
            return

        self.refreshing.reset()
        self.refreshing.set_result(True)
        try:
            await self._refresh_information_loop(sender, time_between_queries, collections)
        finally:
            self.refreshing.reset()

    async def _refresh_information_loop(self, sender, time_between_queries, collections):
        points = iter(itertools.cycle(list(InfoPoints)))

        time_between_queries = time_between_queries or {}

        refreshes = {}
        for e in InfoPoints:
            if e.value.refresh is None:
                refreshes[e] = None
            else:
                refreshes[e] = time_between_queries.get(e.name, e.value.refresh)

        async def gen(reference, sender, **kwargs):
            async with hp.tick(
                1,
                final_future=self.final_future,
                name=f"Device({self.serial})::refresh_information_loop[tick]",
            ) as ticks:
                async for info in ticks:
                    if self.final_future.done():
                        return

                    e = next(points)
                    fut = self.point_futures[e]

                    if fut.done():
                        refresh = refreshes[e]
                        if refresh is None:
                            continue

                        if time.time() - fut.result() < refresh:
                            continue

                    if self.serial not in sender.found:
                        break

                    t = yield e.value.msg
                    await t

        msg = FromGenerator(gen, reference_override=self.serial)
        async for pkt in sender(msg, self.serial, limit=self.limit, find_timeout=5):
            point = self.set_from_pkt(pkt, collections)
            self.point_futures[point].reset()
            self.point_futures[point].set_result(time.time())

    async def matches(self, sender, fltr, collections):
        if fltr is None:
            return True

        async def gen(reference, sender, **kwargs):
            for e in self.points_from_fltr(fltr):
                if self.final_future.done():
                    return
                if not self.point_futures[e].done():
                    yield e.value.msg

        msg = FromGenerator(gen, reference_override=self.serial)
        async for pkt in sender(msg, self.serial, limit=self.limit):
            point = self.set_from_pkt(pkt, collections)
            self.point_futures[point].reset()
            self.point_futures[point].set_result(time.time())

        return self.matches_fltr(fltr)


class DeviceFinderDaemon(hp.AsyncCMMixin):
    def __init__(
        self,
        sender,
        *,
        limit=30,
        finder=None,
        forget_after=30,
        final_future=None,
        search_interval=20,
        time_between_queries=None,
    ):
        self.sender = sender
        self.search_interval = search_interval
        self.time_between_queries = time_between_queries

        final_future = final_future or sender.stop_fut
        self.final_future = hp.ChildOfFuture(
            final_future, name="DeviceFinderDaemon::__init__[final_future]"
        )

        self.own_finder = not bool(finder)
        self.finder = finder or Finder(
            self.sender, self.final_future, forget_after=forget_after, limit=limit
        )

        self.ts = hp.TaskHolder(self.final_future, name="DeviceFinderDaemon::__init__[ts]")
        self.hp_tick = hp.tick

    def reference(self, fltr):
        return DeviceFinder(fltr, finder=self.finder)

    async def start(self):
        self.ts.add(self.search_loop())
        return self

    async def finish(self, exc_typ=None, exc=None, tb=None):
        self.final_future.cancel()
        await self.ts.finish(exc_typ, exc, tb)
        if self.own_finder:
            await self.finder.finish(exc_typ, exc, tb)

    async def search_loop(self):
        refreshing = hp.ResettableFuture(name="DeviceFinderDaemon::search_loop[refreshing]")
        refresh_discovery_fltr = Filter.empty(refresh_discovery=True)

        async def add(streamer):
            if refreshing.done():
                return

            refreshing.set_result(True)

            async for device in self.finder.find(refresh_discovery_fltr):
                await streamer.add_coroutine(
                    device.refresh_information_loop(
                        self.sender, self.time_between_queries, self.finder.collections
                    ),
                    context=device,
                )

        async def ticks():
            async with self.hp_tick(self.search_interval, final_future=self.final_future) as ticks:
                async for info in ticks:
                    yield info

        catcher = partial(log_errors, "Something went wrong in a search")

        async with hp.ResultStreamer(
            self.final_future,
            name="DeviceFinderDaemon::search_loop[streamer]",
            error_catcher=catcher,
        ) as streamer:
            await streamer.add_generator(ticks(), context="finder_tick")
            streamer.no_more_work()

            async for result in streamer:
                if result.successful and result.context == "finder_tick":
                    refreshing.reset()
                    await streamer.add_coroutine(add(streamer))

    async def serials(self, fltr):
        async for device in self.finder.find(fltr):
            yield device

    async def info(self, fltr):
        async for device in self.finder.info(fltr):
            yield device


class Finder(hp.AsyncCMMixin):
    def __init__(self, sender, final_future=None, *, forget_after=30, limit=30):
        self.sender = sender
        self.forget_after = forget_after

        self.limit = limit
        if isinstance(self.limit, int):
            self.limit = asyncio.Semaphore(self.limit)

        self.devices = {}
        self.last_seen = {}
        self.searched = hp.ResettableFuture(name="Finder::__init__[searched]")
        self.collections = Collections()
        self.final_future = hp.ChildOfFuture(
            final_future or self.sender.stop_fut, name="Finder::__init__[final_future]"
        )

    async def find(self, fltr):
        if self.final_future.done():
            return

        refresh = False if fltr is None else fltr.refresh_discovery

        try:
            serials = await self._find_all_serials(refresh=refresh)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Failed to find serials")
            serials = []

        removed = self._ensure_devices(serials)

        catcher = partial(log_errors, "Failed to determine if device matched filter")

        async with hp.ResultStreamer(
            self.final_future, name="Finder::find[streamer]", error_catcher=catcher
        ) as streamer:
            for device in removed:
                await streamer.add_coroutine(device.finish())

            for serial, device in list(self.devices.items()):
                if fltr.matches_all:
                    fut = hp.create_future(name=f"Finder({serial})::find[fut]")
                    fut.set_result(True)
                    await streamer.add_task(fut, context=device)
                else:
                    await streamer.add_coroutine(
                        device.matches(self.sender, fltr, self.collections), context=device
                    )

            streamer.no_more_work()

            async with streamer:
                async for result in streamer:
                    if result.successful and result.value and result.context:
                        yield result.context

    async def info(self, fltr):
        catcher = partial(log_errors, "Failed to find information for device")

        async def find():
            async for device in self.find(fltr):
                await streamer.add_coroutine(
                    device.matches(
                        self.sender, Filter.empty(refresh_info=fltr.refresh_info), self.collections
                    ),
                    context=device,
                )

        streamer = hp.ResultStreamer(
            self.final_future, error_catcher=catcher, name="Finder::info[streamer]"
        )

        async with streamer:
            await streamer.add_coroutine(find(), context=True)
            streamer.no_more_work()

            async for result in streamer:
                if not result.successful:
                    if result.context is True:
                        try:
                            raise result.value
                        finally:
                            del result

                elif result.value and result.context:
                    yield result.context

    async def finish(self, exc_typ=None, exc=None, tb=None):
        self.final_future.cancel()

        async with hp.TaskHolder(
            hp.create_future(name="Finder::finish[task_holder_final_future]"),
            name="Finder::finish[task_holder]",
        ) as ts:
            for serial, device in sorted(self.devices.items()):
                ts.add(device.finish(exc_typ, exc, tb))
                del self.devices[serial]

    async def start(self):
        return self

    async def _find_all_serials(self, *, refresh):
        serials = None
        if self.searched.done() and not refresh:
            serials = self.searched.result()
        else:
            try:
                _, serials = await FoundSerials().find(self.sender, timeout=5)
            except FoundNoDevices:
                serials = []

            self.searched.reset()
            self.searched.set_result(serials)

        return serials

    def _ensure_devices(self, serials):
        removed = []

        if self.final_future.done():
            return [], []

        for serial in serials:
            if serial not in self.devices:
                device = Device.FieldSpec().empty_normalise(serial=serial, limit=self.limit)
                self.devices[serial] = device
            self.last_seen[serial] = time.time()

        for serial, device in list(self.devices.items()):
            if time.time() - self.last_seen[serial] > self.forget_after:
                del self.devices[serial]
                if serial in self.last_seen:
                    del self.last_seen[serial]
                removed.append(device)

        return removed
