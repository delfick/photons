from photons_products.enums import VendorRegistry, Zones
from photons_products.base import Product, Capability


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
