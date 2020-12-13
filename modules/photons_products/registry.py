from photons_products.base import Product, ProductsHolder, Capability
from photons_products.enums import VendorRegistry, Zones, Family

from delfick_project.norms import sb, Meta


class LIFXProduct(Product):
    vendor = VendorRegistry.LIFX

    @classmethod
    def _modify_identifier(kls, val):
        if val.startswith("lcmv4_") and len(val) > 6:
            val = val[6:]

        if val[:5] in ("lcm1_", "lcm2_", "lcm3_") and len(val) > 5:
            val = val[5:]

        if val.startswith("16_") or val.startswith("32_") and len(val) > 3:
            val = val[3:]

        return f"lifx_{val}"

    @classmethod
    def _modify_friendly(kls, val):
        if val.startswith("lcmv4 ") and len(val) > 6:
            val = val[6:]

        if val[:5] in ("lcm1 ", "lcm2 ", "lcm3 ") and len(val) > 5:
            val = val[5:]

        if val.startswith("16 ") or val.startswith("32 ") and len(val) > 3:
            val = val[3:]

        def capital(v):
            return f"{v[0].upper()}{v[1:]}"

        val = " ".join(capital(v) for v in val.split(" "))
        return f"LIFX {val}"


class capability_metaclass(type):
    def __new__(*args, **kwargs):
        kls = type.__new__(*args, **kwargs)
        if kls.min_extended_fw is not None:
            spec = sb.tuple_spec(sb.integer_spec(), sb.integer_spec())
            kls.min_extended_fw = spec.normalise(Meta.empty(), kls.min_extended_fw)
        return kls


class Capability(Capability, metaclass=capability_metaclass):
    """
    .. attribute:: is_light
        Is this device a light

    .. attribute:: zones
        The style of zones. So strips are LINEAR and things like the candle and tile are MATRIX

    .. attribute:: has_ir
        Do we have infrared capability

    .. attribute:: has_hev
        Does this device have HEV LEDs

    .. attribute:: has_color
        Do we have hue control

    .. attribute:: has_chain
        Do we have a chain of devices

    .. attribute:: has_variable_color_temp
        Do we have variable kelvin

    .. attribute:: has_relays
        Does this device have relays

    .. attribute:: has_buttons
        Does this device have physical buttons

    .. attribute:: min_kelvin
        The min kelvin of this product

    .. attribute:: max_kelvin
        The max kelvin of this product

    .. attribute:: min_extended_fw
        A tuple of (firmware_major, firmware_minor) that says when this product got
        extended multizone capability. If this product never got that, then this is None

    .. attribute:: product
        The product class associate with this capability

    .. attribute:: firmware_major
        the firmware_major associated with this product
        You can create an instance of this capability with your own firmware_major by calling this instance

    .. attribute:: firmware_minor
        the firmware_major associated with this product
        You can create an instance of this capability with your own firmware_minor by calling this instance

    .. autoattribute:: photons_products.registry.Capability.has_matrix
    .. autoattribute:: photons_products.registry.Capability.has_multizone
    .. autoattribute:: photons_products.registry.Capability.has_extended_multizone
    """

    is_light = True

    zones = Zones.SINGLE

    has_ir = False
    has_hev = False
    has_color = False
    has_chain = False
    has_variable_color_temp = True
    has_relays = False
    has_buttons = False

    min_kelvin = 2500
    max_kelvin = 9000

    min_extended_fw = None

    product = NotImplemented
    firmware_major = 0
    firmware_minor = 0

    def items(self):
        """Yield (attr, value) for all the relevant capabilities"""
        if self.is_light:
            attrs = [
                "zones",
                "has_ir",
                "has_hev",
                "has_color",
                "has_chain",
                "has_matrix",
                "has_multizone",
                "has_extended_multizone",
                "has_variable_color_temp",
                "min_kelvin",
                "max_kelvin",
                "min_extended_fw",
            ]
        else:
            attrs = ["has_relays", "has_buttons"]

        for attr in attrs:
            yield attr, getattr(self, attr)

    def check_firmware(self, min_fw):
        """Return whether our firmware is greater than min_fw"""
        if min_fw is None:
            return False

        desired_major, desired_minor = min_fw
        if self.firmware_major > desired_major:
            return True

        return self.firmware_major >= desired_major and self.firmware_minor >= desired_minor

    @property
    def has_extended_multizone(self):
        """
        Return whether this product has extended_multizone

        Note you may need to first do something like:

        .. code-block:: python

            cap = capability(firmware_major=2, firmware_minor=77)
            assert cap.has_extended_multizone
        """
        return self.check_firmware(self.min_extended_fw)

    @property
    def has_multizone(self):
        """Return whether we have LINEAR zones"""
        return self.zones is Zones.LINEAR

    @property
    def has_matrix(self):
        """Return whether we have MATRIX zones"""
        return self.zones is Zones.MATRIX


class NonLightCapability(Capability):
    is_light = False
    has_chain = None
    has_color = None
    has_matrix = None
    has_multizone = None
    has_extended_multizone = None
    has_variable_color_temp = None

    max_kelvin = None
    min_kelvin = None


class ProductRegistry:
    class LMB_MESH_A21(LIFXProduct):
        pid = 1
        family = Family.LMB
        friendly = "Original 1000"
        identifier = "original_a21"

        class cap(Capability):
            has_color = True

    class LMBG_MESH_GU10(LIFXProduct):
        pid = 3
        family = Family.LMBG
        friendly = "Color 650"
        identifier = "gu10_color"

        class cap(Capability):
            has_color = True

    class LCMV4_A19_WHITE_LV(LIFXProduct):
        pid = 10
        family = Family.LCM1
        friendly = "White 800 (Low Voltage)"
        identifier = "a19_white"

        class cap(Capability):
            has_color = False
            min_kelvin = 2700
            max_kelvin = 6500
            has_variable_color_temp = True

    class LCMV4_A19_WHITE_HV(LIFXProduct):
        pid = 11
        family = Family.LCM1
        friendly = "White 800 (High Voltage)"
        identifier = "a19_white"

        class cap(Capability):
            has_color = False
            min_kelvin = 2700
            max_kelvin = 6500
            has_variable_color_temp = True

    class LCMV4_A21_COLOR(LIFXProduct):
        pid = 15
        family = Family.LCM1
        friendly = "Color 1000"

        class cap(Capability):
            has_color = True

    class LCMV4_BR30_WHITE_LV(LIFXProduct):
        pid = 18
        family = Family.LCM1
        friendly = "White 900 BR30 (Low Voltage)"
        identifier = "br30_white"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = True

    class LCMV4_BR30_WHITE_HV(LIFXProduct):
        pid = 19
        family = Family.LCM1
        friendly = "White 900 BR30 (High Voltage)"
        identifier = "br30_white"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = True

    class LCMV4_BR30_COLOR(LIFXProduct):
        pid = 20
        family = Family.LCM1
        friendly = "Color 1000 BR30"
        identifier = "br30_color"

        class cap(Capability):
            has_color = True

    class LCMV4_A19_COLOR(LIFXProduct):
        pid = 22
        family = Family.LCM1
        friendly = "Color 1000"
        identifier = "a19_color"

        class cap(Capability):
            has_color = True

    class LCM2_A19(LIFXProduct):
        pid = 27
        family = Family.LCM2
        friendly = "A19"

        class cap(Capability):
            has_color = True

    class LCM2_BR30(LIFXProduct):
        pid = 28
        family = Family.LCM2
        friendly = "BR30"

        class cap(Capability):
            has_color = True

    class LCM2_A19_PLUS(LIFXProduct):
        pid = 29
        family = Family.LCM2
        friendly = "A19 Night Vision"

        class cap(Capability):
            has_ir = True
            has_color = True

    class LCM2_BR30_PLUS(LIFXProduct):
        pid = 30
        family = Family.LCM2
        friendly = "BR30 Night Vision"

        class cap(Capability):
            has_ir = True
            has_color = True

    class LCM1_Z(LIFXProduct):
        pid = 31
        family = Family.LCM1
        friendly = "Z"

        class cap(Capability):
            zones = Zones.LINEAR
            has_color = True

    class LCM2_Z(LIFXProduct):
        pid = 32
        family = Family.LCM2
        friendly = "Z"

        class cap(Capability):
            zones = Zones.LINEAR
            has_color = True
            min_extended_fw = (2, 77)

    class LCM2_DOWNLIGHT_OL(LIFXProduct):
        pid = 36
        family = Family.LCM2
        friendly = "Downlight"

        class cap(Capability):
            has_color = True

    class LCM2_DOWNLIGHT_NL(LIFXProduct):
        pid = 37
        family = Family.LCM2
        friendly = "Downlight"

        class cap(Capability):
            has_color = True

    class LCM2_BEAM(LIFXProduct):
        pid = 38
        family = Family.LCM2
        friendly = "Beam"

        class cap(Capability):
            zones = Zones.LINEAR
            has_color = True
            min_extended_fw = (2, 77)

    class LCM2_DOWNLIGHT_WW_IC4(LIFXProduct):
        pid = 39
        family = Family.LCM2
        friendly = "Downlight White to Warm"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = True
            min_kelvin = 1500
            max_kelvin = 9000

    class LCM2_DOWNLIGHT_COLOR_IC4(LIFXProduct):
        pid = 40
        family = Family.LCM2
        friendly = "Downlight"

        class cap(Capability):
            has_color = True

    class LCM2_A19_HK(LIFXProduct):
        pid = 43
        family = Family.LCM2
        friendly = "A19"

        class cap(Capability):
            has_color = True

    class LCM2_BR30_HK(LIFXProduct):
        pid = 44
        family = Family.LCM2
        friendly = "BR30"

        class cap(Capability):
            has_color = True

    class LCM2_A19_PLUS_HK(LIFXProduct):
        pid = 45
        family = Family.LCM2
        friendly = "A19 Night Vision"

        class cap(Capability):
            has_ir = True
            has_color = True

    class LCM2_BR30_PLUS_HK(LIFXProduct):
        pid = 46
        family = Family.LCM2
        friendly = "BR30 Night Vision"

        class cap(Capability):
            has_ir = True
            has_color = True

    class LCM3_MINI_COLOR(LIFXProduct):
        pid = 49
        family = Family.LCM3
        friendly = "Mini Color"

        class cap(Capability):
            has_color = True

    class LCM3_MINI_WW(LIFXProduct):
        pid = 50
        family = Family.LCM3
        friendly = "Mini White to Warm"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = True
            min_kelvin = 1500
            max_kelvin = 4000

    class LCM3_MINI_WHITE(LIFXProduct):
        pid = 51
        family = Family.LCM3
        friendly = "Mini White"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin = 2700
            max_kelvin = 2700

    class LCM3_GU10_COLOR(LIFXProduct):
        pid = 52
        family = Family.LCM3
        friendly = "GU10"

        class cap(Capability):
            has_color = True

    class LCM3_GU10_ST(LIFXProduct):
        pid = 53
        family = Family.LCM3
        friendly = "GU10"

        class cap(Capability):
            has_color = True

    class LCM3_TILE(LIFXProduct):
        pid = 55
        friendly = "Tile"
        family = Family.LCM3

        class cap(Capability):
            zones = Zones.MATRIX
            has_color = True
            has_chain = True

    class LCM3_CANDLE(LIFXProduct):
        pid = 57
        family = Family.LCM3
        friendly = "Candle"

        class cap(Capability):
            zones = Zones.MATRIX
            has_chain = False
            has_color = True
            min_kelvin = 1500
            max_kelvin = 9000

    class LCM3_MINI2_COLOR(LIFXProduct):
        pid = 59
        family = Family.LCM3
        friendly = "Mini Color"

        class cap(Capability):
            has_color = True

    class LCM3_MINI2_WW(LIFXProduct):
        pid = 60
        family = Family.LCM3
        friendly = "Mini White to Warm"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = True
            min_kelvin = 1500
            max_kelvin = 4000

    class LCM3_MINI2_WHITE(LIFXProduct):
        pid = 61
        family = Family.LCM3
        friendly = "Mini White"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin = 2700
            max_kelvin = 2700

    class LCM3_A19(LIFXProduct):
        pid = 62
        family = Family.LCM3
        friendly = "A19"

        class cap(Capability):
            has_color = True

    class LCM3_BR30(LIFXProduct):
        pid = 63
        family = Family.LCM3
        friendly = "BR30"

        class cap(Capability):
            has_color = True

    class LCM3_A19_PLUS(LIFXProduct):
        pid = 64
        family = Family.LCM3
        friendly = "A19 Night Vision"

        class cap(Capability):
            has_ir = True
            has_color = True

    class LCM3_BR30_PLUS(LIFXProduct):
        pid = 65
        family = Family.LCM3
        friendly = "BR30 Night Vision"

        class cap(Capability):
            has_ir = True
            has_color = True

    class LCM3_MINI2_WHITE_INT(LIFXProduct):
        pid = 66
        family = Family.LCM3
        friendly = "Mini White"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin = 2700
            max_kelvin = 2700

    class LCM3_CANDLE_CA(LIFXProduct):
        pid = 68
        family = Family.LCM3
        friendly = "Candle"

        class cap(Capability):
            zones = Zones.MATRIX
            has_chain = False
            has_color = False
            has_variable_color_temp = True
            min_kelvin = 1500
            max_kelvin = 9000

    class LCM3_16_SWITCH(LIFXProduct):
        pid = 70
        family = Family.LCM3
        friendly = "Switch"

        class cap(NonLightCapability):
            has_relays = True
            has_buttons = True

    class LCM3_32_CANDLE_WW(LIFXProduct):
        pid = 81
        family = Family.LCM3
        friendly = "Candle White to Warm"

        class cap(Capability):
            zones = Zones.SINGLE
            has_chain = False
            has_color = False
            has_variable_color_temp = True
            min_kelvin = 2200
            max_kelvin = 6500

    class LCM3_FILAMENT_ST64_CLEAR_US(LIFXProduct):
        pid = 82
        family = Family.LCM3
        friendly = "Filament Clear"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin = 2100
            max_kelvin = 2100

    class LCM3_FILAMENT_ST64_AMBER_US(LIFXProduct):
        pid = 85
        family = Family.LCM3
        friendly = "Filament Amber"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin = 2000
            max_kelvin = 2000

    class LCM3_MINI_WHITE_INTL(LIFXProduct):
        pid = 88
        family = Family.LCM3
        friendly = "Mini White"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin = 2700
            max_kelvin = 2700

    class LCM3_32_SWITCH_I(LIFXProduct):
        pid = 89
        family = Family.LCM3
        friendly = "Switch"

        class cap(NonLightCapability):
            has_relays = True
            has_buttons = True

    class LCM3_A19_CLEAN(LIFXProduct):
        pid = 90
        family = Family.LCM3
        friendly = "Clean"

        class cap(Capability):
            has_hev = True
            has_color = True

    class LCM3_32_MINI_COLOR_US(LIFXProduct):
        pid = 91
        family = Family.LCM3
        friendly = "Color"

        class cap(Capability):
            has_color = True

    class LCM3_32_MINI_COLOR_INTL(LIFXProduct):
        pid = 92
        family = Family.LCM3
        friendly = "Color"

        class cap(Capability):
            has_color = True

    class LCM3_32_BR30_US(LIFXProduct):
        pid = 94
        family = Family.LCM3
        friendly = "BR30"

        class cap(Capability):
            has_color = True

    class LCM3_32_CANDLE_WW_INTL(LIFXProduct):
        pid = 96
        family = Family.LCM3
        friendly = "Candle White to Warm"

        class cap(Capability):
            zones = Zones.SINGLE
            has_chain = False
            has_color = False
            has_variable_color_temp = True
            min_kelvin = 2200
            max_kelvin = 6500

    class LCM3_32_A19_INTL(LIFXProduct):
        pid = 97
        family = Family.LCM3
        friendly = "A19"

        class cap(Capability):
            has_color = True

    class LCM3_32_BR30_INTL(LIFXProduct):
        pid = 98
        family = Family.LCM3
        friendly = "BR30"

        class cap(Capability):
            has_color = True

    class LCM3_A19_CLEAN_INTL(LIFXProduct):
        pid = 99
        family = Family.LCM3
        friendly = "Clean"

        class cap(Capability):
            has_hev = True
            has_color = True

    class LCM3_FILAMENT_ST64_CLEAR_INTL(LIFXProduct):
        pid = 100
        family = Family.LCM3
        friendly = "Filament Clear"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin = 2100
            max_kelvin = 2100

    class LCM3_FILAMENT_ST64_AMBER_INTL(LIFXProduct):
        pid = 101
        family = Family.LCM3
        friendly = "Filament Amber"

        class cap(Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin = 2000
            max_kelvin = 2000

    class LCM3_32_A19_PLUS_US(LIFXProduct):
        pid = 109
        family = Family.LCM3
        friendly = "A19 Night Vision"

        class cap(Capability):
            has_ir = True
            has_color = True

    class LCM3_32_BR30_PLUS_US(LIFXProduct):
        pid = 110
        family = Family.LCM3
        friendly = "BR30 Night Vision"

        class cap(Capability):
            has_ir = True
            has_color = True

    class LCM3_32_A19_PLUS_INTL(LIFXProduct):
        pid = 111
        family = Family.LCM3
        friendly = "A19 Night Vision"

        class cap(Capability):
            has_ir = True
            has_color = True


Products = ProductsHolder(ProductRegistry, Capability)
