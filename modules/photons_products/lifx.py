from photons_products.base import Product, Capability, CapabilityValue
from photons_products.enums import VendorRegistry, Zones


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

    .. attribute:: has_extended_multizone
        Does this device/firmware support the extended multizone messages.

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
    """

    is_light = True

    zones = CapabilityValue(Zones.SINGLE)

    has_ir = CapabilityValue(False)
    has_hev = CapabilityValue(False)
    has_color = CapabilityValue(False)
    has_chain = CapabilityValue(False)
    has_relays = CapabilityValue(False)
    has_buttons = CapabilityValue(False)
    has_extended_multizone = CapabilityValue(False)
    has_variable_color_temp = CapabilityValue(True)

    min_kelvin = CapabilityValue(2500)
    max_kelvin = CapabilityValue(9000)

    def capabilities_for_display(self):
        if self.is_light:
            return [
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
            ]
        else:
            return ["has_relays", "has_buttons"]

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
