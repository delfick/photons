"""
This module provides an object for finding devices based on filters, which can
also act as a daemon collecting information in the background.

The idea is that you can query the device_finder for information.

.. code-block:: python

    device_finder = DeviceFinder(lan_target)

    serials = await device_finder.serials()
    # serials will be of the form ["d073d5000001", "d073d5000002", "d073d5000003"]

    info = await device_finder.info_for()
    # info will be of the form:
    # {
    #      "d073d512c21d": {
    #          "serial": "d073d512c21d",
    #          "brightness": 0.29999237048905164,
    #          "firmware_version": "1.21",
    #          "group_id": "925fb774c42c11e799e580e650080d3e",
    #          "group_name": "one",
    #          "cap": ["color", "multizone", "variable_color_temp"]
    #          "hue": 0.0,
    #          "kelvin": 3500,
    #          "label": "cupboard",
    #          "location_id": "926647fec42c11e79fb080e650080d3e",
    #          "location_name": "two",
    #          "power": "off",
    #          "product_id": 22,
    #          "product_identifier": "lifx_a19_color",
    #          "saturation": 0.0
    #      },
    #      "d073d514e733": {
    #          "serial": "d073d514e733",
    #          "brightness": 0.29999237048905164,
    #          "firmware_version": "1.20",
    #          "group_id": "925fb774c42c11e799e580e650080d3e",
    #          "group_name": "one",
    #          "cap": ["color", "multizone", "variable_color_temp"]
    #          "hue": 0.0,
    #          "kelvin": 3500,
    #          "label": "tv",
    #          "location_id": "926647fec42c11e79fb080e650080d3e",
    #          "location_name": "two",
    #          "power": "off",
    #          "product_id": 31,
    #          "product_identifier": "lifx_z",
    #          "saturation": 0.0
    #      }
    # }

Or you can use it as a reference in a run_with/run_with_all call:

.. code-block:: python

    device_finder = DeviceFinder(lan_target)

    reference = device_finder.find(group_name="one")
    await lan_target.script(DeviceMessages.SetPower(level=0)).run_with_all(reference)

    reference2 = device_finder.find(hue="0-20", product_identifier=["lifx_color_a19", "lifx_color_br30"])
    for pkt, _, _ in lan_target.script(DeviceMessages.GetPower()).run_with(reference2):
        print(pkt)

Note that if you want the device_finder to update it's idea of what devices are
on the network and what properties those devices have, then you must await on
it's ``start`` method before using it:

.. code-block:: python

    device_finder = DeviceFinder(lan_target)
    await device_finder.start()

    # Use the device_finder as much as you want

    # It's a good idea to finish it when you no longer want to use it
    # Note that it cannot be started again after this.
    await device_finder.finish()

The ``find``, ``serials`` and ``info_for`` methods on ``DeviceFinder`` all take
in keyword arguments to fill out the filter, or it takes in a ``filtr`` keyword
that specifies a filter. Not providing any keyword arguments implies a match all.

Note that if you don't call ``start`` on the device_finder is equivalent to always
having ``force_refresh=True`` in your filter.

.. code-block:: python

    from photons_device_finder import Filter

    # The following four lines are equivalent
    filtr = Filter.from_options({"hue": ["0-10", "30-50"], "label": "one"})
    filtr = Filter.from_kwargs(hue=["0-10", "30-50"], label="one")
    filtr = Filter.from_json_str('{"hue": ["0-10", "30-50"], "label": "one"}')
    filtr = Filter.from_key_value_str('hue=0-10,30-50 label=one')

    # And these two lines are equivalent
    device_finder.find(filtr=filtr)
    device_finder.find(hue=["0-10", "30-50"], label="one")

.. note:: When you use DeviceFinder.find you are creating an instance of
    ``photons_app.special.SpecialReference`` which means it will cache the result
    of finding devices for future calls. If you want to re-use one and have it
    search again, call ``reset`` on it.

.. _finder_filters:

Tasks
-----

See :ref:`tasks`.

.. photons_module_tasks::

Valid Filters
-------------

The filter takes in:

force_refresh:
    Search for devices and their information. This will only refresh information
    required for the rest of the arguments to the Filter.

    i.e. if the filter only matches against labels, then we will only refresh
    the labels on our devices.

serial
    The serial of the device

label
    The label set on the device

power
    Either "on" or "off" depending on whether the device is on or not.

group_id
    The uuid of the group set on this device

group_name
    The name of this group. Note that if you have several devices that have
    the same group, then this will be set to the label of the group
    with the newest updated_at option.

location_id
    The uuid of the location set on this device

location_name
    The name of this location. Note that if you have several devices that have
    the same location_id, then this will be set to the label of the location
    with the newest updated_at option.

hue, saturation, brightness, kelvin
    The hsbk values of the device. You can specify a range by saying something
    like ``10-30``, which would match any device with a hsbk value between 10
    and 30 (inclusive).

firmware_version
    The version of the HostFirmware as a string of "{major}.{minor}".

product_id
    The product id of the device as an integer. You can see the hex product id
    of each device type in the ``photons_products_registry`` module.

product_identifier
    A string identifying the product type of the device. You can find these in
    the ``photons_products_registry`` module.

cap
    A list of strings of capabilities this device has.

    Capabilities include ``ir``, ``color``, ``chain``, ``multizone``, ``variable_color_temp``
    and ``not_ir``, ``not_color``, ``not_chain``, ``not_multizone``, ``not_variable_color_temp``

When a property in the filter is an array, it will match any device that matches
against any of the items in the array.

And a filter with multiple properties will only match devices that match against
all those properties.

Label properties ("product_identifier", "label", "location_name", "group_name")
are matched with globs. So if you have device1 with product_identifier of
``lifx_a19_plus`` and device2 with a product_identifier of ``lifx_br30_plus``
you can filter them both by saying
``Filter.from_kwargs(product_identifier="*_plus")``

.. autoclass:: photons_device_finder.Filter

.. autoclass:: photons_device_finder.DeviceFinder
"""
from photons_app.errors import FoundNoDevices, PhotonsAppError, TimedOut
from photons_app.special import FoundSerials, SpecialReference
from photons_app.actions import an_action
from photons_app import helpers as hp

from photons_messages import LIFXPacket, DeviceMessages, LightMessages
from photons_products_registry import capability_for_ids
from photons_control.script import Pipeline, Repeater

from option_merge_addons import option_merge_addon_hook
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
from input_algorithms.meta import Meta
from collections.abc import Iterable
from urllib.parse import parse_qs
from functools import partial
import binascii
import logging
import fnmatch
import asyncio
import json
import time
import enum
import re

log = logging.getLogger("photons_device_finder")

__shortdesc__ = "Device finder that gathers information about devices in the background"

@option_merge_addon_hook(extras=[
    ("lifx.photons", "control")
  , ("lifx.photons", "messages")
  , ("lifx.photons", "products_registry")
  ])
def __lifx__(collector, *args, **kwargs):
    pass

@option_merge_addon_hook(post_register=True)
def __lifx_post__(collector, **kwargs):
    def resolve(s, target):
        filtr = Filter.from_url_str(s)
        return DeviceFinderWrap(filtr, target)
    collector.configuration["reference_resolver_register"].add("match", resolve)

@an_action(needs_target=True)
async def find_with_filter(collector, target, **kwargs):
    """
    Find serials that match the provided filter

    ``find_with_filter -- '{"label": ["kitchen", "loungeroom"], "product_identifier": "lifx_z"}'``

    Not providing options after the ``--`` will find all devices on the network.
    """
    extra = collector.configuration["photons_app"].extra_as_json
    device_finder = DeviceFinder(target)
    try:
        for serial in await device_finder.serials(**extra):
            print(serial)
    finally:
        await device_finder.finish()

regexes = {
      "key_value": re.compile(r"^(?P<key>[\w_]+)=(?P<value>.+)")
    }

class Done:
    """Used to signify a queue is done"""

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

class Collections(object):
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
        if type(val) is int:
            return False if val == 0 else True
        elif type(val) is str:
            return False if val.lower() in ("no", "false") else True
        return sb.boolean().normalise(meta, val)

class str_ranges(sb.Spec):
    """
    Take in a string of the form ``a-b,c-d,e`` and convert to ``[(a, b), (c, d), (e, e)]``

    Will also work if the value is already of the form [(a, b), (c, d), (e, e)]
    or if the value is a list of ["a-b", "c-d", "e"]
    """
    def normalise_filled(self, meta, val):
        if type(val) is str:
            val = val.split(',')

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
    """
    The options for a filter. Usage looks like:

    .. code-block:: python

        filtr = Filter.FieldSpec().empty_normalise(force_refresh=True, firmware_version="1.22")

        # or
        filtr = Filter.from_json_str('{"force_refresh": true, "firmware_version": "1.22"}')

        # or
        filtr = Filter.from_options({"force_refresh": True, "firmware_version": "1.22"})

        # or
        filtr = Filter.from_kwargs(force_refresh=True, firmware_version="1.22")

        # or
        filtr = Filter.from_key_value_str("force_refresh=true firmware_version=1.22")

        # or
        filtr = Filter.from_url_str("force_refresh=true&firmware_version=1.22")

    .. automethod:: photons_device_finder.Filter.from_options

    .. automethod:: photons_device_finder.Filter.from_kwargs

    .. automethod:: photons_device_finder.Filter.empty

    .. automethod:: photons_device_finder.Filter.from_json_str

    .. automethod:: photons_device_finder.Filter.from_key_value_str

    .. automethod:: photons_device_finder.Filter.from_url_str

    .. autoattribute:: photons_device_finder.Filter.matches_all

    .. automethod:: photons_device_finder.Filter.matches

    .. automethod:: photons_device_finder.Filter.has

    Finally, we have ``has`` which takes in a ``field_name`` and says whether
    """
    force_refresh = dictobj.Field(boolean, default=False)

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
    product_identifier = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)

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
                if groups["key"] not in ("hue", "saturation", "brightness", "kelvin", "force_refresh"):
                    options[groups["key"]] = groups["value"].split(',')
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
    def empty(kls, force_refresh=False):
        """Create an empty filter"""
        return kls.from_options({"force_refresh": force_refresh})

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

        * Always say False for ``force_refresh``
        * Say False if the value on the filter for field_name is NotSpecified
        * Say True if a hsbk value and we are within the range specified in val
        * Say True if value on the filter is a list, and val exists in that list
        * Say True if value on the filter is not a list and matches val
        """
        if field_name == "force_refresh":
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
            if field != "force_refresh":
                if self[field] != sb.NotSpecified:
                    return False
        return True

    @property
    def points(self, for_info=False):
        """Provide InfoPoints enums that match the keys on this filter with values"""
        for e in InfoPoints:
            for key in e.value.keys:
                if self[key] != sb.NotSpecified:
                    yield e

    @property
    def label_fields(self):
        return ("product_identifier", "label", "location_name", "group_name")

class Point(object):
    """Used as the value in the InfoPoints enum"""
    def __init__(self, msg, keys):
        self.msg = msg
        self.keys = keys

class InfoPoints(enum.Enum):
    """
    Enum used to determine what information is required for what keys
    """
    LIGHT_STATE = Point(LightMessages.GetColor(), ["label", "power", "hue", "saturation", "brightness", "kelvin"])
    VERSION = Point(DeviceMessages.GetVersion(), ["product_id", "product_identifier", "cap"])
    FIRMWARE = Point(DeviceMessages.GetHostFirmware(), ["firmware_version"])
    GROUP = Point(DeviceMessages.GetGroup(), ["group_id", "group_name"])
    LOCATION = Point(DeviceMessages.GetLocation(), ["location_id", "location_name"])

class Device(dictobj.Spec):
    """
    An object representing a single device.

    Users shouldn't have to interact with these directly
    """
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
    product_identifier = dictobj.Field(sb.string_spec, wrapper=sb.optional_spec)

    cap = dictobj.Field(sb.listof(sb.string_spec()), wrapper=sb.optional_spec)

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
        del actual["location"]
        for key in self.property_fields:
            actual[key] = self[key]
        return actual

    def matches(self, filtr):
        """
        Say whether we match against the provided filter
        """
        if filtr.matches_all:
            return True

        fields = list(self.fields) + self.property_fields
        has_atleast_one_field = False

        for field in fields:
            val = self[field]
            if val is not sb.NotSpecified:
                has_field = filtr.has(field)
                if has_field:
                    has_atleast_one_field = True
                if has_field and not filtr.matches(field, val):
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
            capability = capability_for_ids(pkt.product, pkt.vendor)
            self.product_identifier = capability.identifier
            cap = []
            for prop in ("has_color", "has_ir", "has_multizone", "has_chain", "has_variable_color_temp"):
                if getattr(capability, prop):
                    cap.append(prop[4:])
                else:
                    cap.append("not_{}".format(prop[4:]))
            self.cap = sorted(cap)
            return InfoPoints.VERSION

class ByTarget(dict):
    def __init__(self, device_spec):
        self.device_spec = device_spec

    def __getitem__(self, target):
        if target not in self:
            self[target] = self.device_spec.empty_normalise(serial = binascii.hexlify(target).decode())
        return super().__getitem__(target)

class InfoStore(object):
    """
    The central part of all our collected information

    Users need not work with this directly.
    """
    def __init__(self, device_finder_loops):
        self.found = hp.ResettableFuture()
        self.device_finder_loops = device_finder_loops
        self.futures = {e: hp.ResettableFuture() for e in InfoPoints}
        self.last_touch = {}
        self.device_spec = Device.FieldSpec()
        self.by_target = ByTarget(self.device_spec)
        self.tasks_by_target = {}
        self.collections = Collections()

    def finish(self):
        for task in self.tasks_by_target.values():
            task.cancel()

    def reset_point(self, point):
        """
        Reset a future for the provided InfoPoints enum

        These futures represent waiting for that information to be filled out
        """
        if point in self.futures:
            self.futures[point].reset()

    def add(self, pkt):
        """
        Add information to the store from this pkt.

        We use set_from_pkt on a Device object to set the information and also
        determine what InfoPoint this effects.

        Finally, we ask the loop to check this InfoPoint in 0.3 seconds and set
        it's future to done if we haven't received more information for this
        InfoPoint in that time.
        """
        typ = self.by_target[pkt.target[:6]].set_from_pkt(pkt, self.collections)
        if typ in self.futures:
            touch = time.time()
            self.last_touch[typ] = touch
            if not self.futures[typ].done():
                asyncio.get_event_loop().call_later(0.3, self.set_future_done, typ, touch)

    def info_for(self, targets):
        """
        Return information based on the provided targets.

        Note that targets is an array of unhexlified serials.
        """
        res = {}
        for target in targets:
            if target in self.by_target:
                info = { k: v
                      for k, v in self.by_target[target].as_dict().items()
                      if v != sb.NotSpecified
                    }
                if info:
                    res[binascii.hexlify(target).decode()] = info
        return res

    def set_future_done(self, typ, touch):
        """
        Called by the ``add`` method and is used to set the future for the
        provided InfoPoint enum if this information hasn't been touched since
        ``add`` was called.
        """
        if typ in self.futures and typ in self.last_touch:
            if self.last_touch[typ] == touch and not self.futures[typ].done():
                self.futures[typ].set_result(True)

    async def found_from_filter(self, filtr, for_info=False, find_timeout=5):
        """
        Determine what InfoPoints correspond to this filtr and wait for them
        all to be done.

        Then return a dictionary of the information we have stored for all
        the devices that match the filter.
        """
        waited = asyncio.Future()

        async def wait():
            if for_info:
                points = InfoPoints
            else:
                points = filtr.points

            for point in points:
                if point in self.futures:
                    await self.futures[point]

            if not waited.done():
                waited.set_result(dict(await self.found))

        try:
            await asyncio.wait_for(wait(), timeout=find_timeout)
        except asyncio.TimeoutError:
            raise TimedOut("Waiting for information to be available")
        else:
            found = dict(await waited)

        for target in list(found):
            if target not in self.by_target:
                del found[target]
                continue

            if not filtr.matches_all:
                if not self.by_target[target].matches(filtr):
                    del found[target]

        return found

    def update_found(self, found, query_new_devices=True):
        """
        Update our idea of what devices on the network.

        We delete information about devices that are no longer on the network.
        """
        for target in list(self.by_target):
            if target not in found:
                del self.by_target[target]

        if query_new_devices:
            for target in found:
                if target not in self.by_target:
                    t = hp.async_as_background(self.device_finder_loops.add_new_device(target))
                    self.tasks_by_target[target] = t
                    t.add_done_callback(partial(self.cleanup_task, target, t))

        # Make sure our targets are in by_target
        # Must happen after calling add_new_device for those that aren't in by_target
        for target in found:
            self.by_target[target]

        self.found.reset()
        self.found.set_result(found)

    def cleanup_task(self, target, t, res):
        if self.tasks_by_target.get(target) is t:
            del self.tasks_by_target[target]

class DeviceFinderLoops(object):
    """
    The engine of this module.

    When ``start`` is called on this we create a few background tasks that collect
    data.

    findings
        This loop (self.finding_loop) will do a loop every ``information_search_interval``
        seconds and ask for information from all the devices it finds.

        This loop attempts to spread out the messages such that we send out each
        message with a one second delay per device.

    service_search
        This loop (self.raw_search_loop) will ask the network for devices
        every ``service_search_interval`` seconds and update the ``store`` to
        only contain devices that are found (i.e. delete those that disappear)

        New devices will have information queried from them when they are
        newly found.

    interpreting
        This loop takes in pkts from the ``queue`` on this instance and will add
        them to the ``store`` (an instance of ``InfoStore``).

        This queue is populated by the ``findings`` loop as well as when we have
        ``force_refresh`` and when new devices are found from ``service_search``
    """
    def __init__(self, target, service_search_interval=20, information_search_interval=30, repeat_spread=1):
        self.target = target
        self.queue = asyncio.Queue()
        self.store = InfoStore(self)
        self.finished = asyncio.Event()
        self.repeat_spread = repeat_spread
        self.service_search_interval = service_search_interval
        self.information_search_interval = information_search_interval

    async def args_for_run(self):
        """Return an afr object. Multiple calls to this will return the same object"""
        if not hasattr(self, "afr_fut"):
            self.afr_fut = asyncio.Future()
            t = hp.async_as_background(self.target.args_for_run())

            def transfer(res):
                if res.cancelled():
                    self.afr_fut.cancel()

                exc = res.exception()
                if exc:
                    self.afr_fut.set_exception(exc)

                self.afr_fut.set_result(res.result())
            t.add_done_callback(transfer)

        return await self.afr_fut

    async def start(self, quickstart=False):
        await self.args_for_run()
        self.findings = hp.async_as_background(self.finding_loop())
        self.ensure_interpreting()
        self.service_search = hp.async_as_background(self.raw_search_loop(quickstart))

    async def finish(self):
        self.finished.set()
        await self.queue.put(Done)

        if hasattr(self, "findings"):
            self.findings.cancel()
        if hasattr(self, "interpreting"):
            self.interpreting.cancel()
        if hasattr(self, "service_search"):
            self.service_search.cancel()

        if hasattr(self, "afr_fut"):
            if self.afr_fut.done() and not self.afr_fut.cancel():
                await self.target.close_args_for_run(self.afr_fut.result())
            self.afr_fut.cancel()

        self.store.finish()

    def ensure_interpreting(self):
        """Make sure the interpreting loop has started"""
        if not hasattr(self, "interpreting"):
            self.interpreting = hp.async_as_background(self.interpret_loop())

    async def send_to_device(self, reference, msg, find_timeout=5):
        """
        Send msg to provided reference with an error_catcher that ignores messages

        Also, put all response packets onto the self.queue.
        """
        script = self.target.script(msg)

        def error_catcher(e):
            log.debug(hp.lc("Error getting information for a device", error=e))

        afr = await self.args_for_run()
        kwargs = {"error_catcher": error_catcher, "find_timeout": find_timeout}

        async for pkt, _, _ in script.run_with(reference, afr, **kwargs):
            if self.finished.is_set():
                break
            await self.queue.put(pkt)

    async def add_new_device(self, target, msgs=None):
        """
        A new device was found, send all our information gathering messages to
        it and put the resulting State messages on the queue for processing.
        """
        if msgs is None:
            msgs = []
            for e in InfoPoints:
                msgs.append(e.value.msg)

        pipeline = Pipeline(*msgs, spread=0.2)
        serial = binascii.hexlify(target).decode()
        await self.send_to_device(serial, pipeline)

    async def refresh_from_filter(self, filtr, for_info=False, find_timeout=5):
        """
        Given this filtr reset the relevant futures on the ``store`` and ask for
        that information from all the devices that we find on the network.

        Finally, return the ``found`` dictionary for devices that match this
        filtr once all the information is back.
        """
        msgs = list(self._msgs_from_filter(filtr, do_reset=True, for_info=for_info))
        reference = FoundSerials()

        if any(msgs):
            await self.send_to_device(reference, msgs, find_timeout=find_timeout)

        await self._update_found(reference, find_timeout)
        return await self.store.found_from_filter(filtr, for_info=for_info)

    def _msgs_from_filter(self, filtr, for_info=False, do_reset=False):
        """Return the relevant messages from this filter"""
        for e in InfoPoints:
            if for_info or any(filtr.has(key) for key in e.value.keys):
                if do_reset:
                    self.store.reset_point(e)
                yield e.value.msg

    async def _update_found(self, special_reference, find_timeout):
        """Update our idea of found from the provided special reference"""
        afr = await self.args_for_run()
        found, _ = await special_reference.find(afr, timeout=find_timeout)
        self.store.update_found(found)

    async def raw_search_loop(self, quickstart=False):
        """
        An endless loop that searches for new devices on the network

        Run every ``service_search_interval`` seconds

        After the first attempt we will send out queries to any new devices we
        find so that we don't have to wait for the ``findings`` loop to do a pass.
        """
        first = True
        while True:
            if self.finished.is_set():
                break

            try:
                afr = await self.args_for_run()
                found = await afr.find_devices(ignore_lost=True)
                query_new_devices = quickstart or not first
                self.store.update_found(found, query_new_devices=query_new_devices)
                first = False
            except asyncio.CancelledError:
                raise
            except FoundNoDevices:
                pass
            except Exception as error:
                log.exception(hp.lc("Unexpected error getting new serials", error=error))

            await asyncio.sleep(self.service_search_interval)

    async def finding_loop(self):
        """
        Endless loop of finding devices on the network and doing a spaced out
        information discovery of those devices.
        """
        getter = [e.value.msg for e in InfoPoints]
        pipeline = Pipeline(*getter, spread=self.repeat_spread, short_circuit_on_error=True)
        repeater = Repeater(pipeline, min_loop_time=self.information_search_interval)
        await self.send_to_device(FoundSerials(), repeater)

    async def interpret_loop(self):
        """
        Endless loop of looking at ``queue`` for packets and giving them to our
        ``store``.
        """
        while True:
            if self.finished.is_set():
                break

            try:
                nxt = await self.queue.get()

                if nxt is Done:
                    break

            except asyncio.CancelledError:
                raise
            except Exception as error:
                log.error(hp.lc("Failed to get item off the queue", error=error))
            else:
                try:
                    self.interpret(nxt)
                except Exception as error:
                    log.error(hp.lc("Failed to interpret item from queue", error=error))

    def interpret(self, item):
        """
        Add a pkt to the ``store``.

        Log an error and do nothing if the provided item is not a LIFXPacket.
        """
        if not isinstance(item, LIFXPacket):
            log.error(hp.lc("Got item off the queue that wasn't a lifx binary packet", got=item))
            return
        self.store.add(item)

class DeviceFinder(object):
    """
    Used by users to find devices based on filters.

    You can activate the daemon functionality by awaiting on ``start``.
    Not doing this is equivalent to always using force_refresh with your filters.

    When you are finished with this object, await on it's ``finish`` method.

    .. automethod:: photons_device_finder.DeviceFinder.serials

    .. automethod:: photons_device_finder.DeviceFinder.info_for

    .. automethod:: photons_device_finder.DeviceFinder.find

    .. automethod:: photons_device_finder.DeviceFinder.start

    .. automethod:: photons_device_finder.DeviceFinder.finish

    .. automethod:: photons_device_finder.DeviceFinder.args_for_run
    """
    _merged_options_formattable = True

    def __init__(self, target, service_search_interval=20, information_search_interval=30, repeat_spread=1):
        self.loops = DeviceFinderLoops(target
            , service_search_interval = service_search_interval
            , information_search_interval = information_search_interval
            , repeat_spread = repeat_spread
            )
        self.daemon = False

    async def start(self, quickstart=False):
        """
        Put the DeviceFinder into daemon mode and start the background threads.

        By doing this, we will use cached information when using the device_finder
        unless the filter specifically sets force_refresh to True.

        If ``quickstart`` is provided as True then we will gather information
        from devices on the network without spreading out the messages. This will
        allow us to gather information quicker at the cost of much more network
        traffic.
        """
        await self.loops.start(quickstart=quickstart)
        self.daemon = True

    async def args_for_run(self):
        """
        Return an args_for_run object from our target

        Multiple calls to this will return the same object
        """
        return await self.loops.args_for_run()

    async def finish(self):
        """Stop the background tasks"""
        await self.loops.finish()

    def find(self, **kwargs):
        """
        Return a SpecialReference object that may be used with run_with/run_with_all

        It will tell the script to send messages to the devices it can find that
        match the filter we create from the passed in kwargs.
        """
        return self._find(kwargs)

    async def serials(self, **kwargs):
        """
        Return a list of hexlified serials of the devices we can find that match
        the filter created from the passed in kwargs.
        """
        reference = self._find(kwargs)
        afr = await self.args_for_run()
        _, serials = await reference.find(afr, timeout=5)
        return serials

    async def info_for(self, **kwargs):
        """
        Return a dictionary of {serial: information} of the devices we can find
        that match the filter created from the passed in kwargs.
        """
        reference = self._find(kwargs, for_info=True)
        afr = await self.args_for_run()
        found, _ = await reference.find(afr, timeout=5)
        return self.loops.store.info_for(found.keys())

    def _find(self, kwargs, for_info=False):
        """
        Used by DeviceFinder to create a filter from the kwargs and then return
        a SpecialReference object that uses that filter with our ``store`` to
        instruct what devices we have filtered.
        """
        # Make sure the loops is taking in messages
        self.loops.ensure_interpreting()

        if "filtr" in kwargs:
            filtr = kwargs.pop("filtr")
            if kwargs:
                raise PhotonsAppError("Please either specify filters or a filtr, not both")
        else:
            filtr = Filter.from_options(kwargs)

        return self._reference(filtr, for_info=for_info)

    def _reference(self, filtr, for_info=False):
        """Return a SpecialReference instance that uses the provided filtr"""
        class Reference(SpecialReference):
            async def find_serials(s, afr, *, timeout, broadcast=True):
                if filtr.force_refresh or not self.daemon:
                    found = await self.loops.refresh_from_filter(filtr, for_info=for_info, find_timeout=timeout)
                else:
                    found = await self.loops.store.found_from_filter(filtr, for_info=for_info, find_timeout=timeout)

                if not found:
                    raise FoundNoDevices()

                if hasattr(afr, "found") and isinstance(afr.found, dict):
                    afr.found.update(found)

                return found

        ref = Reference()
        items = filtr.items()
        if isinstance(items, Iterable):
            if all(v is sb.NotSpecified for k, v in items if k not in ("force_refresh", "serial")):
                if filtr["serial"] != sb.NotSpecified:
                    ref.serials = filtr["serial"]

        return ref

class DeviceFinderWrap(SpecialReference):
    """
    A wrap around DeviceFinder for providing to the reference resolver

    This makes sure our DeviceFinder is cleaned up at the end
    """
    def __init__(self, filtr, target):
        self.finder = DeviceFinder(target)
        self.reference = self.finder.find(filtr=filtr)

    async def find(self, afr, *, timeout, broadcast=True):
        return await self.reference.find(afr, timeout=timeout, broadcast=broadcast)

    def reset(self):
        self.reference.reset()

    async def finish(self):
        await self.finder.finish()
