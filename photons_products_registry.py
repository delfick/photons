from option_merge_addons import option_merge_addon_hook
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb

from photons_app.errors import PhotonsAppError

from enum import Enum

__shortdesc__ = "A registry of LIFX products"

__doc__ = """
.. code_for:: photons_products_registry.LIFIProductRegistry

Device capabilities can be retrieved as properties from
``photons_products_registry.Capabilities``

However, it's better to use ``photons_products_registry.capability_for_ids``
to get these objects.

For example:

.. code-block:: python

    from photons_products_registry import capability_for_ids
    from photons_device_messages import DeviceMessages

    async for pkt, _, _ in target.script(DeviceMessages.GetVersion()).run_with(reference):
        if pkt | DeviceMessages.StateVersion:
            cap = capability_for_ids(pkt.product, pkt.vendor)
            print("{}: {}".format(pkt.serial, cap))

.. autofunction:: photons_products_registry.capability_for_ids

.. code_for:: photons_products_registry.Capability

.. show_capabilities:: photons_products_registry.Capabilities
"""

class UnknownProduct(PhotonsAppError):
    desc = "Unknown product"

@option_merge_addon_hook()
def __lifx__(collector, *args, **kwargs):
    pass

class LIFIProductRegistry(Enum):
    LMB_MESH_A21            = 1
    LMBG_MESH_GU10          = 3

    LCMV4_A19_WHITE_LV      = 10
    LCMV4_A19_WHITE_HV      = 11
    LCMV4_BR30_WHITE_LV     = 18
    LCMV4_BR30_COLOR        = 20
    LCMV4_A19_COLOR         = 22

    LCM2_A19                = 27
    LCM2_BR30               = 28
    LCM2_A19_PLUS           = 29
    LCM2_BR30_PLUS          = 30
    LCM1_Z                  = 31
    LCM2_Z                  = 32

    LCM2_DOWNLIGHT_OL       = 36
    LCM2_DOWNLIGHT_NL       = 37

    LCM2_BEAM               = 38

    LCM2_A19_HK             = 43
    LCM2_BR30_HK            = 44
    LCM2_A19_PLUS_HK        = 45
    LCM2_BR30_PLUS_HK       = 46

    LCM3_MINI_COLOR         = 49
    LCM3_MINI_DAY_DUSK      = 50
    LCM3_MINI_DAY           = 51

    LCM3_GU10_COLOR         = 52

    LCM3_TILE               = 55

    LCM3_MINI2_COLOR        = 59
    LCM3_MINI2_DAY_DUSK     = 60
    LCM3_MINI2_WHITE        = 61

class VendorRegistry(Enum):
    EMPTY    = 0
    LIFI     = 1

class ProductRegistries(Enum):
    EMPTY = Enum("Empty", [("NONE", 0)])
    LIFI = LIFIProductRegistry

def capability_for_enum(en):
    for key, member in Capabilities.__members__.items():
        if key == en.name:
            return member
    return DefaultCapability

def capability_for_ids(pid, vid):
    """Return a capability object for this pid/vid pair"""
    return capability_for_enum(enum_for_ids(pid, vid)).value

def enum_for_ids(pid, vid):
    for key, val in VendorRegistry.__members__.items():
        if val.value == vid:
            registry = getattr(ProductRegistries, key)
            for key, member in registry.value.__members__.items():
                if int(member.value) == pid:
                    return member
    raise UnknownProduct(vid=vid, pid=pid)

def product_names():
    names = {}
    for e in VendorRegistry:
        if e != VendorRegistry.EMPTY:
            vid = e.value
            registry = ProductRegistries[e.name].value
            for p in registry:
                pid = p.value
                ident = "{}.{}".format(vid, pid)
                try:
                    names[ident] = Capabilities[p.name].value.name
                except KeyError:
                    pass
    return names

L = LIFIProductRegistry

class Capability(dictobj.Spec):
    """Represents the capability for a device"""
    name = dictobj.Field(sb.string_spec, wrapper=sb.required)
    company = dictobj.Field(sb.string_spec, wrapper=sb.required)
    identifier = dictobj.Field(sb.string_spec, wrapper=sb.required)

    has_color = dictobj.Field(sb.boolean, default=True)
    has_ir = dictobj.Field(sb.boolean, default=False)
    has_multizone = dictobj.Field(sb.boolean, default=False)
    has_variable_color_temp = dictobj.Field(sb.boolean, default=True)
    has_chain = dictobj.Field(sb.boolean, default=False)

def capability(name, company, identifier, **kwargs):
    return Capability.FieldSpec().empty_normalise(name=name, company=company, identifier=identifier, **kwargs)

def lifx_capability(name, identifier, **kwargs):
    return capability(name, "LIFX", "lifx_{0}".format(identifier), **kwargs)

lc = lifx_capability
class Capabilities(Enum):
    LMB_MESH_A21            = lc("Original 1000", "original")
    LMBG_MESH_GU10          = lc("Color 650", "gu10_color")

    LCMV4_A19_WHITE_LV      = lc("White 800", "a19_white", has_color=False)
    LCMV4_A19_WHITE_HV      = lc("White 800", "a19_white", has_color=False)
    LCMV4_BR30_WHITE_LV     = lc("White 900 BR30", "br30_white", has_color=False)
    LCMV4_BR30_COLOR        = lc("Color 1000 BR30", "br30_color")
    LCMV4_A19_COLOR         = lc("Color 1000", "a19_color")

    LCM2_A19                = lc("LIFX A19", "a19")
    LCM2_BR30               = lc("LIFX BR30", "br30")
    LCM2_A19_PLUS           = lc("LIFX+ A19", "a19_plus", has_ir=True)
    LCM2_BR30_PLUS          = lc("LIFX+ BR30", "br30_plus", has_ir=True)
    LCM1_Z                  = lc("LIFX Z", "z", has_multizone=True)
    LCM2_Z                  = lc("LIFX Z", "z", has_multizone=True)

    LCM2_DOWNLIGHT_OL       = lc("LIFX DOWNLIGHT O", "downlight_o")
    LCM2_DOWNLIGHT_NL       = lc("LIFX DOWNLIGHT N", "downlight_n")

    LCM2_BEAM               = lc("LIFX Beam", "beam", has_multizone=True)

    LCM2_A19_HK             = lc("LIFX A19", "a19")
    LCM2_BR30_HK            = lc("LIFX BR30", "br30")
    LCM2_A19_PLUS_HK        = lc("LIFX+ A19", "a19_plus", has_ir=True)
    LCM2_BR30_PLUS_HK       = lc("LIFX+ BR30", "br30_plus", has_ir=True)

    LCM3_MINI_COLOR         = lc("LIFX Mini Color", "mini_color")
    LCM3_MINI_DAY_DUSK      = lc("LIFX Mini Day Dusk", "mini_day_dusk", has_color=False)
    LCM3_MINI_DAY           = lc("LIFX Mini Day", "mini_day", has_color=False)

    LCM3_GU10_COLOR         = lc("LIFX GU10 Color", "gu10_color")

    LCM3_TILE               = lc("LIFX Tile", "tile", has_chain=True)

    LCM3_MINI2_COLOR        = lc("LIFX Mini Color", "mini_color")
    LCM3_MINI2_DAY_DUSK     = lc("LIFX Mini Day Dusk", "mini_day_dusk", has_color=False)
    LCM3_MINI2_WHITE        = lc("LIFX Mini White", "mini_white", has_color=False)

DefaultCapability = capability("Unknown", "unknown", "Unknown")
