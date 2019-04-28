from photons_app.errors import PhotonsAppError

from photons_messages import LightMessages, DeviceMessages, MultiZoneMessages, TileMessages
from photons_products_registry import capability_for_ids, enum_for_ids

from input_algorithms import spec_base as sb
from collections import defaultdict

plan_by_key = {}

class Skip:
    """
    Plans that return this instead of messages are saying to the planner
    to not invoke this plan for this device
    """

class NoMessages:
    """
    Plans that return this instead of messages are saying to the planner
    to just call plan.info() and use the result from that rather than processing
    any messages that are sent from the device
    """

class a_plan:
    """
    A decorator for registering a name for a plan. This registry is used by
    make_plans to convert names into plans.
    """
    def __init__(self, key):
        self.key = key

    def __call__(self, item):
        plan_by_key[self.key] = item
        return item

def pktkey(pkt):
    """
    Return a key representing this packet

    This key is a tuple that may be used as a dictionary key.

    It consists of the ``(protocol, pkt_type, <string representing the payload>)``
    """
    return (pkt.protocol, pkt.pkt_type, repr(pkt.payload))

def make_plans(*by_key, **plans):
    """
    Given by_key which is a list of strings and plans which is a dictionary of key to
    plan, return a dictionary of key to plans.

    We will complain if:

    * A key in by_key is not a registered plan
    * A key in by_key is also in plans
    """
    if not by_key and not plans:
        return {}

    count = defaultdict(int)
    for key in by_key:
        count[key] += 1
        if key in plans:
            raise PhotonsAppError("Cannot specify plan by label and by Plan class", specified_twice=key)
        if count[key] > 1:
            raise PhotonsAppError("Cannot specify plan by label more than once", specified_multiple_times=key)

    for key in by_key:
        if key not in plan_by_key:
            raise PhotonsAppError("No default plan for key", wanted=key, available=list(plan_by_key))
        plans[key] = plan_by_key[key]()

    return plans

class Plan:
    """
    Base class for plans. A plan is an object that specifies what messages to
    send to a device, How to process any message that the device sends back and
    how to create a final artifact that represents the value from this plan.

    Usage looks like:

    .. code-block:: python

        class MyPlan(Plan):
            messages = [DeviceMessages.GetPower()]

            class Instance(Plan.Instance):
                def process(self, pkt):
                    if pkt | DeviceMessages.StatePower:
                        self.level = pkt.level
                        return True

                async def info(self):
                    return {"level": self.level}

    There are some properties on the Plan itself:

    * messages - Default None - a list of messages to send to the device.
      If you want to choose based on the device itself, then define messages on
      the Instance where you have access to the deps and serial.
    * dependant_info - Default None - An optional dictionary of key to Plan class
      that is used to get dependency information for this plan. For example if
      you say ``dependant_info = {"c": CapabilityPlan()}`` then the plan will
      only be executed once we have information from the CapabilityPlan and the
      Instance will have ``self.deps = {"c": <info from capability plan>}`` for
      use.
    * default_refresh - Default 10 - Either True if you never want to re-use
      results from this plan. False if you never want to remove the results from
      this plan, or an integer representing the number of seconds before the
      cache expires. If the cache expires then the messages defined by this plan
      are resent to the device. Note that this is overridden if you specify
      refresh when you instantiate the plan.
    * setup - Method - Called by __init__ with all positional and keyword
      arguments used to instantiate the plan except refresh. Note that before
      setup is called, self.refresh will be set on the class as either the
      refresh keyword argument if provided or the default_refresh on the plan
    * Instance - Class - The logic for processing packets from the device and
      getting the final information for the plan.

    The Instance class will be instantiated per device that the planner is
    looking at. It is also possible to define messages on the Instance. If you
    want to have logic for determining what messages to send, then just make
    messages a method with an ``@property`` decorator.

    If you define messages on the instance you have access to:

    * self.parent -- the plan instance used to create this device Instance
    * self.deps -- Dependency information as defined by dependant_info on the parent
    * self.serial -- the serial for this device
    * Anything else on the instance defined in the setup hook

    The Instance has the following hooks and properties:

    * messages - Default None - A list of messages to send to the device. If this
      is not defined, then messages on the parent is used. If this is Skip then
      the plan is not executed for this device.
    * finished_after_no_more_messages - default False - This plan should be
      considered done if it already isn't considered done and we don't have any
      more messages from devices.
    * setup - Method - Any setup specific to this device. You have self.deps,
      self.parent and self.serial at this point.
    * refresh - property - Defaults to self.parent.refresh - The refresh for this
      instance of data.
    * key - Method, defaults to self.parent.__class__ - A key used to represent
      this plan, so that future executions of this plan can reuse the final
      information for this serial without sending more messages.
    * process - Method - does nothing by default, it is used to process all messages
      that the device sends back, not just replies to the messages asked for by
      the plan. You must return True from this method when you have received
      enough information. Once we return True then info will be called to get
      the final result for this plan. Note that if the messages on this plan is
      the NoMessages class then this method will never be called. By  default
      this method raises NotImplementedError.
    * info - Async method - Must be overridden - This is called when the plan is
      considered done for this device and returns whatever information you want.
    """
    messages = None
    dependant_info = None
    default_refresh = 10

    def __init__(self, *args, refresh=sb.NotSpecified, **kwargs):
        self.refresh = self.default_refresh
        if refresh is not sb.NotSpecified:
            self.refresh = refresh
            kwargs["refresh"] = refresh
        self.setup(*args, **kwargs)

    def setup(self, *args, **kwargs):
        pass

    class Instance:
        messages = None
        finished_after_no_more_messages = False

        def __init__(self, serial, parent, deps):
            self.deps = deps
            self.parent = parent
            self.serial = serial
            self.setup()

        def setup(self):
            pass

        @property
        def refresh(self):
            return self.parent.refresh

        def key(self):
            return self.parent.__class__

        def process(self, pkt):
            pass

        async def info(self):
            raise NotImplementedError()

@a_plan("presence")
class PresencePlan(Plan):
    """
    Just return True. To be used with other plans to make sure that this
    serial is returned by gather if no other plans return results
    """
    messages = NoMessages

    class Instance(Plan.Instance):
        async def info(self):
            return True

@a_plan("address")
class AddressPlan(Plan):
    """Return the (ip, port) for this device"""
    messages = []

    class Instance(Plan.Instance):
        def process(self, pkt):
            self.address = pkt._with_sender_address
            return True

        async def info(self):
            return self.address

@a_plan("label")
class LabelPlan(Plan):
    """Return the label of this device"""
    messages = [DeviceMessages.GetLabel()]
    default_refresh = 5

    class Instance(Plan.Instance):
        def process(self, pkt):
            if pkt | DeviceMessages.StateLabel:
                self.label = pkt.label
                return True

        async def info(self):
            return self.label

@a_plan("state")
class StatePlan(Plan):
    """Return LightState.as_dict() for this device"""
    messages = [LightMessages.GetColor()]
    default_refresh = 1

    class Instance(Plan.Instance):
        def process(self, pkt):
            if pkt | LightMessages.LightState:
                self.dct = pkt.payload.as_dict()
                return True

        async def info(self):
            return self.dct

@a_plan("power")
class PowerPlan(Plan):
    """Return ``{"level": 0 - 65535, "on": True | False}`` for this device."""
    messages = [DeviceMessages.GetPower()]
    default_refresh = 1

    class Instance(Plan.Instance):
        def process(self, pkt):
            if pkt | DeviceMessages.StatePower:
                self.level = pkt.level
                self.on = pkt.level > 0
                return True

        async def info(self):
            return {"level": self.level, "on": self.on}

@a_plan("zones")
class ZonesPlan(Plan):
    """
    Return ``[(index, hsbk), ...]`` for this device.

    Will take into account if the device supports extended multizone or not
    """
    default_refresh = 1

    @property
    def dependant_info(kls):
        return {"c": CapabilityPlan()}

    class Instance(Plan.Instance):
        def setup(self):
            self.staging = []

        @property
        def is_multizone(self):
            return self.deps["c"]["cap"].has_multizone

        @property
        def has_extended_multizone(self):
            return self.deps["c"]["has_extended_multizone"]

        @property
        def messages(self):
            if self.is_multizone:
                if self.has_extended_multizone:
                    return [MultiZoneMessages.GetExtendedColorZones()]
                else:
                    return [MultiZoneMessages.GetColorZones(start_index=0, end_index=255)]
            return Skip

        def process(self, pkt):
            if pkt | MultiZoneMessages.StateMultiZone:
                for i, color in enumerate(pkt.colors):
                    if len(self.staging) < pkt.zones_count:
                        self.staging.append((pkt.zone_index + i, color.as_dict()))
                return len(self.staging) == pkt.zones_count

            elif pkt | MultiZoneMessages.StateExtendedColorZones:
                for i, color in enumerate(pkt.colors[:pkt.colors_count]):
                    if len(self.staging) < pkt.zones_count:
                        self.staging.append((pkt.zone_index + i, color.as_dict()))
                return len(self.staging) == pkt.zones_count

        async def info(self):
            return sorted(self.staging)

@a_plan("capability")
class CapabilityPlan(Plan):
    """
    Return ``{"cap": <capability>, "has_extended_multizone": <bool>, "product": <product>}`` for this device

    Where capability is from photons_products_registry.capability_for_ids

    And product is from photons_products_registry.enum_for_ids
    """
    messages = [DeviceMessages.GetHostFirmware(), DeviceMessages.GetVersion()]

    class Instance(Plan.Instance):
        def process(self, pkt):
            if pkt | DeviceMessages.StateHostFirmware:
                self.firmware = pkt
            elif pkt | DeviceMessages.StateVersion:
                self.version = pkt
            return hasattr(self, "firmware") and hasattr(self, "version")

        async def info(self):
            product = enum_for_ids(self.version.product, self.version.vendor)
            cap = capability_for_ids(self.version.product, self.version.vendor)
            has_extended = cap.has_extended_multizone(self.firmware.version_major, self.firmware.version_minor)
            return {"cap": cap, "has_extended_multizone": has_extended, "product": product}

@a_plan("firmware")
class FirmwarePlan(Plan):
    """Return StateHostFirmware.as_dict() for this device"""
    messages = [DeviceMessages.GetHostFirmware()]

    class Instance(Plan.Instance):
        def process(self, pkt):
            if pkt | DeviceMessages.StateHostFirmware:
                self.dct = pkt.payload.as_dict()
                return True

        async def info(self):
            return self.dct

@a_plan("version")
class VersionPlan(Plan):
    """Return StateVersion.as_dict() for this device"""
    messages = [DeviceMessages.GetVersion()]

    class Instance(Plan.Instance):
        def process(self, pkt):
            if pkt | DeviceMessages.StateVersion:
                self.dct = pkt.payload.as_dict()
                return True

        async def info(self):
            return self.dct

@a_plan("firmware_effects")
class FirmwareEffectsPlan(Plan):
    """
    Return ``{"type": <enum>, "options": {...}}``` for each device where strips
    return multizone effect data and tiles return tile effect data.

    Returns Skip for devices that don't have firmware effects
    """
    default_refresh = 1

    @property
    def dependant_info(kls):
        return {"c": CapabilityPlan()}

    class Instance(Plan.Instance):
        @property
        def is_multizone(self):
            return self.deps["c"]["cap"].has_multizone

        @property
        def is_tile(self):
            return self.deps["c"]["cap"].has_chain

        @property
        def messages(self):
            if self.is_multizone:
                return [MultiZoneMessages.GetMultiZoneEffect()]
            elif self.is_tile:
                return [TileMessages.GetTileEffect()]
            return Skip

        def process(self, pkt):
            if pkt | MultiZoneMessages.StateMultiZoneEffect:
                self.pkt = pkt
                return True

            elif pkt | TileMessages.StateTileEffect:
                self.pkt = pkt
                return True

        async def info(self):
            info = {"type": self.pkt.type, "options": {}}

            for k, v in self.pkt.payload.as_dict().items():
                if "reserved" not in k and k not in ("type", "palette_count"):
                    if k == "parameters":
                        for k2 in v:
                            if not k2.startswith("parameter"):
                                info["options"][k2] = v[k2]
                    elif k == "palette":
                        info["options"]["palette"] = v[:self.pkt.palette_count]
                    else:
                        info["options"][k] = v

            return info
