from photons_products.enums import VendorRegistry, Family
from photons_products.errors import IncompleteProduct


class Capability:
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
        return []

    def as_dict(self):
        return dict(self.items())


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

            if val is NotImplemented:
                if attr == "friendly":
                    val = classname.lower().replace("_", " ")
                    setattr(kls, attr, val)
                elif attr == "identifier":
                    val = classname.lower()
                    setattr(kls, attr, val)

            if dflt is NotImplemented and val is NotImplemented:
                raise IncompleteProduct("Attribute wasn't overridden", attr=attr, name=kls.name)

            modifier = getattr(parent, f"_modify_{attr}", None)
            if modifier:
                setattr(kls, attr, modifier(val))

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

    .. attribute:: identifier
        The identifier of the product
    """

    name = NotImplemented
    pid = NotImplemented
    cap = NotImplemented
    vendor = NotImplemented
    family = NotImplemented
    friendly = NotImplemented
    identifier = NotImplemented

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
