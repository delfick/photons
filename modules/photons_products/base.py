from photons_products.enums import VendorRegistry, Family
from photons_products.errors import IncompleteProduct

from photons_app.errors import ProgrammerError


class CapabilityValue:
    def __init__(self, value):
        self._value = value
        self.upgrades = []

    def __repr__(self):
        upgrades = [f"({ma}, {mi}, {becomes})" for ma, mi, becomes in self.upgrades]
        if upgrades:
            return f"<CapabilityValue ({self._value}) -> {' -> '.join(upgrades)}>"
        else:
            return f"<CapabilityValue ({self._value})>"

    def __eq__(self, other):
        return (
            isinstance(other, CapabilityValue)
            and self._value == other._value
            and self.upgrades == other.upgrades
        )

    def value(self, cap):
        value = self._value
        for ma, mi, becomes in self.upgrades:
            if (cap.firmware_major, cap.firmware_minor) >= (ma, mi):
                value = becomes

        return value

    def until(self, major, minor, *, becomes):
        if any((ma, mi) >= (major, minor) for ma, mi, _ in self.upgrades):
            raise ProgrammerError("Each .until must be for a greater version number")

        self.upgrades.append((major, minor, becomes))
        return self


class CapabilityRange(CapabilityValue):
    """
    The way this is used means that the metaclass gets two CapabilityValue objects
    """

    def __init__(self, value):
        if not isinstance(value, tuple) or len(value) != 2:
            raise ProgrammerError("Values in a capability range must be a tuple of two values")

        super().__init__(value)

    def value(self, cap):
        raise ProgrammerError("CapabilityRange should only ever be present during definition time")

    def __iter__(self):
        low, high = CapabilityValue(self._value[0]), CapabilityValue(self._value[1])
        for ma, mi, becomes in self.upgrades:
            low.until(ma, mi, becomes=becomes[0])
            high.until(ma, mi, becomes=becomes[1])
        yield from (low, high)


class CapabilityDefinition(type):
    """Used to create a definition for capabilities"""

    def __new__(metaname, classname, baseclasses, attrs):
        caps = {}
        for kls in baseclasses:
            if hasattr(kls, "Meta") and hasattr(kls.Meta, "capabilities"):
                caps.update(kls.Meta.capabilities)

        for name in list(attrs):
            value = attrs[name]
            if isinstance(value, CapabilityValue):
                attrs.pop(name)
                caps[name] = value
            elif name in caps:
                attrs.pop(name)
                caps[name] = CapabilityValue(value)

        instance = type.__new__(metaname, classname, baseclasses, attrs)

        with_meta = [kls for kls in baseclasses if hasattr(kls, "Meta")]

        if with_meta:
            Meta = with_meta[-1].Meta
        else:
            Meta = type("Meta", (), {"capabilities": {}})

        instance.Meta = type("Meta", (Meta,), {"capabilities": caps})
        return instance


class Capability(metaclass=CapabilityDefinition):
    def __init__(self, product, firmware_major=0, firmware_minor=0):
        self.product = product
        self.firmware_major = firmware_major
        self.firmware_minor = firmware_minor

    def __call__(self, firmware_major, firmware_minor):
        return self.__class__(
            self.product, firmware_major=firmware_major, firmware_minor=firmware_minor
        )

    def __repr__(self):
        return f"<Capability {self.product.name}>"

    def __eq__(self, other):
        return (
            self.product == other.product
            and self.firmware_major == other.firmware_major
            and self.firmware_minor == other.firmware_minor
        )

    def items(self):
        for capability in self.capabilities_for_display():
            yield capability, getattr(self, capability)

    def __getattribute__(self, key):
        Meta = object.__getattribute__(self, "Meta")
        if key in Meta.capabilities:
            return Meta.capabilities[key].value(self)
        else:
            return object.__getattribute__(self, key)

    def capabilities_for_display(self):
        return self.Meta.capabilities

    def as_dict(self):
        return dict(self.items())

    class Meta:
        capabilities = {}


class product_metaclass(type):
    def __new__(metaname, classname, baseclasses, attrs):
        if not baseclasses or classname.endswith("Product"):
            return type.__new__(metaname, classname, baseclasses, attrs)

        parent = baseclasses[0]
        kls = type.__new__(metaname, classname, baseclasses, attrs)

        if kls.cap is NotImplemented:
            raise IncompleteProduct("Product doesn't have a capability specified", name=classname)

        kls.name = classname

        kls.cap_kls = kls.cap

        for attr in dir(parent):
            dflt = getattr(parent, attr)
            val = getattr(kls, attr, NotImplemented)

            if dflt is NotImplemented and val is NotImplemented:
                raise IncompleteProduct("Attribute wasn't overridden", attr=attr, name=kls.name)

        instance = kls()
        kls.cap = kls.cap(instance)
        return instance


class Product(metaclass=product_metaclass):
    """
    .. attribute:: name
        The name of the product

    .. attribute:: pid
        The product id of this product

    .. attribute:: cap
        an instance of a Capability object

    .. attribute:: vendor
        A Vendor object

    .. attribute:: family
        The hardware family this product belongs to

    .. attribute:: friendly
        A friendly name for the product
    """

    name = NotImplemented
    pid = NotImplemented
    cap = NotImplemented
    vendor = NotImplemented
    family = NotImplemented
    friendly = NotImplemented

    @property
    def company(self):
        """The name of the self.vendor"""
        return self.vendor.name

    def __eq__(self, other):
        if isinstance(other, tuple):
            return other == (self.vendor, self.pid)
        return isinstance(other, Product) and self.pid == other.pid and self.vendor == other.vendor

    def __hash__(self):
        return hash((self.vendor.vid, self.pid))

    def as_dict(self):
        """Return this product as a dictionary"""
        result = {}
        for attr in dir(Product):
            val = getattr(Product, attr)
            if val is NotImplemented:
                r = result[attr] = getattr(self, attr)
                if hasattr(r, "as_dict"):
                    result[attr] = r.as_dict()
        return result

    def __repr__(self):
        return f"<Product {self.vendor.vid}({self.vendor.name}):{self.pid}({self.name})>"


def make_unknown_product(vd, pd, Capability):
    class Unknown(Product):
        pid = pd
        vendor = VendorRegistry.choose(vd)
        family = Family.UNKNOWN
        friendly = "<<Unknown>>"

        class cap(Capability):
            pass

    return Unknown


class ProductsHolder:
    def __init__(self, products, default_capability_kls):
        self.products = products
        self.default_capability_kls = default_capability_kls

        self.by_pair = {}

        for attr in dir(products):
            if not attr.startswith("_"):
                product = getattr(products, attr)
                if isinstance(product, Product):
                    self.by_pair[(product.vendor, product.pid)] = product

    @property
    def names(self):
        for product in self.by_pair.values():
            yield product.name

    def __getattr__(self, name):
        products = object.__getattribute__(self, "products")

        p = getattr(products, name, None)
        if p:
            return p

        return super().__getattribute__(name)

    def __getitem__(self, key):
        if isinstance(key, (list, tuple)) and len(key) == 2:
            if key not in self.by_pair:
                vid, pid = key
                return make_unknown_product(vid, pid, self.default_capability_kls)
            return self.by_pair[key]
        else:
            p = getattr(self.products, key, None)
            if not p:
                raise KeyError(f"No such product definition: {key}")
            return p
