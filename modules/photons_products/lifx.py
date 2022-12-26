from photons_products import conditions as cond
from photons_products.base import Capability, CapabilityValue, Product, cap_property
from photons_products.enums import Family, VendorRegistry, Zones


class Product(Product):
    vendor = VendorRegistry.LIFX


class Capability(Capability):
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

    .. attribute:: has_relays
        Does this device have relays

    .. attribute:: has_buttons
        Does this device have physical buttons

    .. attribute:: has_unhandled
        This product has StateUnhandled

    .. attribute:: has_extended_multizone
        This product supports extended multizone messages

    .. attribute:: has_variable_color_temp
        Do we have variable kelvin

    .. attribute:: min_kelvin
        The min kelvin of this product

    .. attribute:: max_kelvin
        The max kelvin of this product

    .. attribute:: product
        The product class associate with this capability

    .. attribute:: firmware_major
        the firmware_major associated with this product
        You can create an instance of this capability with your own firmware_major by calling this instance

    .. attribute:: firmware_minor
        the firmware_major associated with this product
        You can create an instance of this capability with your own firmware_minor by calling this instance

    .. autoattribute:: photons_products.lifx.Capability.has_matrix
    .. autoattribute:: photons_products.lifx.Capability.has_multizone
    """

    is_light = True

    zones = CapabilityValue(Zones.SINGLE)

    has_ir = CapabilityValue(False)
    has_hev = CapabilityValue(False)
    has_color = CapabilityValue(False)
    has_chain = CapabilityValue(False)
    has_relays = CapabilityValue(False)
    has_buttons = CapabilityValue(False)

    has_unhandled = CapabilityValue(False).until(0, 0, cond.NameHas("SWITCH"), becomes=True)

    has_extended_multizone = (
        CapabilityValue(False)
        .until(0, 0, cond.Family(Family.LCM3), cond.Capability(has_multizone=True), becomes=True)
        .until(2, 77, cond.Family(Family.LCM2), cond.Capability(has_multizone=True), becomes=True)
    )

    has_variable_color_temp = CapabilityValue(True)

    min_kelvin = CapabilityValue(2500)
    max_kelvin = CapabilityValue(9000)

    @cap_property
    def has_multizone(self):
        """Return whether we have LINEAR zones"""
        return self.zones is Zones.LINEAR

    @cap_property
    def has_matrix(self):
        """Return whether we have MATRIX zones"""
        return self.zones is Zones.MATRIX


class NonLightCapability(Capability):
    zones = None
    is_light = False

    has_ir = None
    has_hev = None
    has_color = None
    has_chain = None
    has_matrix = None
    has_multizone = None
    has_extended_multizone = None
    has_variable_color_temp = None

    max_kelvin = None
    min_kelvin = None
