"""
Here we create classes that represent the individual fields in the LIFX packets

By default we have the following types:

.. photons_protocol_types::

Each type is an instance of:

.. autoclass:: photons_protocol.types.Type
    :members:
"""

from photons_protocol.errors import BadSpecValue, BadConversion

from photons_app.errors import ProgrammerError
from photons_app import helpers as hp

from input_algorithms import spec_base as sb
from bitarray import bitarray
import functools
import operator
import binascii
import logging
import json
import enum
import re

log = logging.getLogger("photons_protocol.packets.builder")

Optional = type("Optional", (), {})()

regexes = {
      "version_number": re.compile("(?P<major>\d+)\.(?P<minor>\d+)")
    }

class Type(object):
    """
    A specification of how to pack and unpack bits from/to a packet

    struct_format
        Either a ``struct`` format specifier, ``None`` or ``bool``.

        ``bool`` represents a single byte indicating 0 or 1

        ``None`` represents treating the field as just bytes

    conversion
        A input_algorithms spec or a type representing what form the value should take in Python land

    .. note:: Calling an instance allows us to set ``size_bits`` which is an integer
      representing the number of ``bits`` this field should use.
    """
    size_bits = NotImplemented
    _enum = sb.NotSpecified
    _bitmask = sb.NotSpecified
    _dynamic = sb.NotSpecified
    _default = sb.NotSpecified
    _override = sb.NotSpecified
    _many_kls = sb.NotSpecified
    _many_size = sb.NotSpecified
    _transform = sb.NotSpecified
    _unpack_transform = sb.NotSpecified

    _many = False
    _optional = False
    _allow_float = False
    _version_number = False
    _allow_callable = False

    def __init__(self, struct_format, conversion):
        self.conversion = conversion
        self.struct_format = struct_format

    def __call__(self, size_bits, left=sb.NotSpecified):
        """
        Return us a new instance with a different size_bits

        This is a shortcut for calling ``self.S(<size_bits>, left=<left>)``
        """
        return self.S(size_bits, left=left)

    def S(self, size_bits, left=sb.NotSpecified):
        """Return a new instance with a different size_bits"""
        result = self.__class__(self.struct_format, self.conversion)
        result.size_bits = size_bits
        result._enum = self._enum
        result._many = self._many
        result._bitmask = self._bitmask
        result._default = self._default
        result._dynamic = self._dynamic
        result._override = self._override
        result._many_kls = self._many_kls
        result._many_size = self._many_size
        result._transform = self._transform
        result._unpack_transform = self._unpack_transform
        result._optional = self._optional
        result._allow_float = self._allow_float
        result._version_number = self._version_number
        result._allow_callable = self._allow_callable
        result.original_size = getattr(self, "original_size", size_bits)
        if left is not sb.NotSpecified:
            result.left_cut = left
        elif hasattr(self, "left_cut"):
            result.left_cut = self.left_cut
        return result

    @classmethod
    def t(kls, name, struct_format, conversion):
        """Create a new type"""
        return type(name, (kls, ), {})(struct_format, conversion)

    def allow_float(self):
        """Set the _allow_float option"""
        res = self.S(self.size_bits)
        res._allow_float = True
        return res

    def version_number(self):
        """Set the _version_number option"""
        res = self.S(self.size_bits)
        res._version_number = True
        return res

    def enum(self, enum):
        """Set the _enum option"""
        res = self.S(self.size_bits)
        res._enum = enum
        return res

    def dynamic(self, dynamiser):
        """Set a function that returns what fields make up this one chunk of bytes"""
        res = self.S(self.size_bits)
        res._dynamic = dynamiser
        return res

    def many(self, manyiser, sizer=sb.NotSpecified):
        """
        Set options to convert this field into a list of items

        manyiser is a function that takes in the packet and returns the class to use for the list.

        sizer is either a number, which is the number of bits used by each item in the list
        or a function that takes in ``(pkt, item)`` and returns the size of bits for that item in the list

        If sizer is not specified, then the length of each item will be the size_bits of the kls returned
        by manyiser

        We convert the field into a list of instances of that kls.
        """
        res = self.S(self.size_bits)
        res._many = True
        res._many_kls = manyiser
        res._many_size = sizer
        return res

    def bitmask(self, bitmask):
        """Set the _bitmask option"""
        res = self.S(self.size_bits)
        res._bitmask = bitmask
        return res

    def transform(self, pack_func, unpack_func):
        """Set a ``pack_func`` and ``unpack_func`` for transforming the value for use"""
        for f in (pack_func, unpack_func):
            if not callable(f):
                raise ProgrammerError("Sorry, transform can only be given two callables")

        res = self.S(self.size_bits)
        res._transform = pack_func
        res._unpack_transform = unpack_func
        return res

    def allow_callable(self):
        res = self.S(self.size_bits)
        res._allow_callable = True
        return res

    def default(self, value):
        """Set a default value for this field"""
        res = self.S(self.size_bits)
        if not callable(value):
            res._default = lambda pkt: value
        else:
            res._default = value
        return res

    def optional(self):
        """Set the _optional option"""
        res = self.S(self.size_bits)
        res._optional = True
        return res

    def override(self, value):
        """Set the _override option"""
        res = self.S(self.size_bits)
        if not callable(value):
            res._override = lambda pkt: value
        else:
            res._override = value
        return res

    @classmethod
    def install(kls, *types):
        """Create many types at the same time! and put them onto the Type class"""
        for name, size, fmt, conversion in types:
            if size is not None:
                setattr(kls, name, kls.t(name, fmt, conversion)(size))
            else:
                setattr(kls, name, kls.t(name, fmt, conversion))

    def spec(self, pkt, unpacking=False, transform=True):
        """
        Return an input_algorithms spec object for normalising values before and
        after packing/unpacking

        This spec has the default and override on the class applied to it

        Where override and default are called with ``pkt`` before being used.

        We support:

        int
            An integer which can also be an enum or bitmask

            .. autofunction:: photons_protocol.types.integer_spec

        bool
            .. autofunction:: photons_protocol.types.boolean

        float
            .. autofunction:: photons_protocol.types.float_spec

        str
            .. autofunction:: photons_protocol.types.bytes_as_string_spec

        bytes
            .. autofunction:: photons_protocol.types.bytes_spec

        (bool, int)
            .. autofunction:: photons_protocol.types.boolean_as_int_spec

        (list, str, ",")
            .. autofunction:: photons_protocol.types.csv_spec

        json
            Converts the value into a json compatible object
        """
        spec = self._maybe_transform_spec(pkt, self._spec(pkt, unpacking=unpacking), unpacking, transform=transform)

        if self._allow_callable:
            spec = callable_spec(spec)

        if self._override is not sb.NotSpecified:
            return overridden(self._override, pkt)

        if self._default is not sb.NotSpecified:
            return defaulted(spec, self._default, pkt)

        if self._optional:
            return optional(spec)

        return spec

    def _maybe_transform_spec(self, pkt, spec, unpacking, transform=True):
        """
        Return a wrapped spec with do_transform

        This happens if we are not unpacking and have a _transform
        """
        if transform and not unpacking and self._transform is not sb.NotSpecified:
            return transform_spec(pkt, spec, self.do_transform)
        else:
            return spec

    def _spec(self, pkt, unpacking=False):
        """
        Return an input_algorithms spec object for normalising values before and
        after packing/unpacking
        """
        spec = self.spec_from_conversion(pkt, unpacking)

        if spec is not None:
            if self._many:
                return self.many_wrapper(spec, pkt, unpacking=unpacking)
            if self._dynamic is sb.NotSpecified:
                return spec
            else:
                return self.dynamic_wrapper(spec, pkt, unpacking=unpacking)

        raise BadConversion("Cannot create a specification for this conversion", conversion=self.conversion, type=self.__class__.__name__)

    def spec_from_conversion(self, pkt, unpacking):
        """Get us a specification from our conversion type"""
        conversion = self.conversion

        if conversion in static_conversion_from_spec:
            return static_conversion_from_spec[conversion]

        elif conversion is bytes:
            return bytes_spec(pkt, self.size_bits)

        elif conversion is int:
            return self.make_integer_spec(pkt, unpacking)

        elif conversion is str:
            return bytes_as_string_spec(pkt, self.size_bits, unpacking=unpacking)

        elif conversion == (list, str, ","):
            return csv_spec(pkt, self.size_bits, unpacking=unpacking)

    def dynamic_wrapper(self, spec, pkt, unpacking=False):
        """A wrapper to convert to and from dynamic fields"""
        from photons_protocol.packets import dictobj
        kls = type("parameters", (dictobj.PacketSpec, ), {"fields": list(self._dynamic(pkt))})
        return expand_spec(kls, spec, unpacking)

    def many_wrapper(self, spec, pkt, unpacking=False):
        """A wrapper to convert to and from list fields"""
        return many_spec(self._many_kls(pkt), self._many_size, pkt, spec, unpacking)

    def make_integer_spec(self, pkt, unpacking):
        """Make an integer spec that respects enum, bitmask and allow_float/version_number"""
        enum = None
        if self._enum is not sb.NotSpecified:
            enum = self._enum

        bitmask = None
        if self._bitmask is not sb.NotSpecified:
            bitmask = self._bitmask

        if self._version_number:
            return version_number_spec(unpacking=unpacking)

        return integer_spec(pkt, enum, bitmask, unpacking=unpacking, allow_float=self._allow_float)

    def do_transform(self, pkt, value):
        """Perform transformation on a value"""
        if self._transform is sb.NotSpecified:
            return value
        else:
            return self._transform(pkt, value)

    def untransform(self, value):
        """Perform the reverse transformation on a value"""
        if self._unpack_transform is sb.NotSpecified:
            return value
        else:
            return self._unpack_transform(value)

class callable_spec(sb.Spec):
    """Allow callables to pass through"""

    def __init__(self, spec):
        self.spec = spec

    def normalise_filled(self, meta, val):
        if callable(val):
            return val
        return self.spec.normalise(meta, val)

class transform_spec(sb.Spec):
    """
    Apply an untransform on some value

    This is only used when we get a spec for unpacking
    """
    def __init__(self, pkt, spec, do_transform):
        self.pkt = pkt
        self.spec = spec
        self.do_transform = do_transform

    def normalise(self, meta, val):
        if val not in (sb.NotSpecified, Optional):
            val = self.do_transform(self.pkt, val)
        return self.spec.normalise(meta, val)

class many_spec(sb.Spec):
    """
    Expand our list of objects

    We assume the fields are represented as bytes and so return it as such
    when not unpacking.

    Otherwise we return a list of instances of ``kls``.

    Either by unpacking using ``kls`` if val is bytes, or by instantiating ``kls``
    with each val if it is a list.
    """
    def __init__(self, kls, sizer, pkt, spec, unpacking):
        self.kls = kls
        self.pkt = pkt
        self.spec = spec
        self.sizer = sizer
        self.unpacking = unpacking

    def normalise(self, meta, val):
        if self.unpacking:
            return self.unpack(meta, val)
        else:
            return self.pack(meta, val)

    def unpack(self, meta, val):
        if type(val) in (bitarray, bytes):
            res = []
            bts = self.spec.normalise(meta, val)

            i = -1
            while True:
                i += 1
                nxt = self.kls.unpack(bts)
                res.append(nxt)

                size = len(self.bytes_spec_for(nxt).normalise(meta.indexed_at(i), bts))
                bts = bts[size:]
                if not bts:
                    break

            return res
        elif isinstance(val, list):
            return val
        else:
            raise BadSpecValue("Expected to unpack bytes", found=val, transforming_into_list_of=self.kls)

    def pack(self, meta, val):
        if type(val) not in (bytes, bitarray):
            try:
                if type(val) is not list:
                    raise BadSpecValue("Not a list")

                items = sb.listof(sb.dictionary_spec()).normalise(meta, val)
            except BadSpecValue as error:
                raise BadSpecValue("Sorry, many fields only supports a list of dictionary of values", error=error)
            else:
                res = []
                for i, v in enumerate(items):
                    nxt = self.kls(**v)
                    spec = self.bytes_spec_for(nxt)
                    if hasattr(self.kls.Meta, "cache"):
                        items = tuple(sorted(nxt.items()))
                        if items not in self.kls.Meta.cache:
                            self.kls.Meta.cache[items] = nxt.pack()
                        packd = self.kls.Meta.cache[items]
                    else:
                        packd = nxt.pack()
                    res.append(spec.normalise(meta.indexed_at(i), packd))
                val = functools.reduce(operator.add, res)

        # The spec is likely a T.Bytes and will ensure we have enough bytes length in the result
        return self.spec.normalise(meta, val)

    def bytes_spec_for(self, item):
        if self.sizer is sb.NotSpecified:
            size = self.kls.size_bits(item)
        elif callable(self.sizer):
            size = self.sizer(self.pkt, item)
        else:
            size = self.sizer
        return bytes_spec(self.pkt, size)

class expand_spec(sb.Spec):
    """
    Expand our dynamic fields

    We assume the fields are represented as bytes and so return it as such
    when not unpacking.

    Otherwise we return an instance of ``kls``.

    Either by unpacking using ``kls`` if val is bytes, or by instantiating ``kls``
    with the val if it is a dictionary.
    """
    def __init__(self, kls, spec, unpacking):
        self.kls = kls
        self.spec = spec
        self.unpacking = unpacking

    def normalise(self, meta, val):
        if self.unpacking:
            if type(val) in (bitarray, bytes):
                return self.kls.unpack(self.spec.normalise(meta, val))
            elif isinstance(val, self.kls):
                return val
            else:
                raise BadSpecValue("Expected to unpack bytes", found=val, transforming_into=self.kls)
        else:
            if type(val) not in (bytes, bitarray):
                try:
                    fields = sb.dictionary_spec().normalise(meta, val)
                except BadSpecValue as error:
                    raise BadSpecValue("Sorry, dynamic fields only supports a dictionary of values", error=error)
                else:
                    val = self.kls(**fields).pack()

            # The spec is likely a T.Bytes and will ensure we have enough bytes length in the result
            return self.spec.normalise(meta, val)

class optional(sb.Spec):
    """Return Optional if NotSpecified, else use the spec"""
    def __init__(self, spec):
        self.spec = spec

    def normalise_empty(self, meta):
        return Optional

    def normalise_filled(self, meta, val):
        if val is Optional:
            return val
        return self.spec.normalise(meta, val)

class version_number_spec(sb.Spec):
    """Normalise a value as a version string"""
    def setup(self, unpacking=False):
        self.unpacking = unpacking

    def normalise_filled(self, meta, val):
        """
        Convert to and from a string into an integer
        """
        if self.unpacking:
            if type(val) is str:
                if not regexes["version_number"].match(val):
                    raise BadSpecValue("Expected string to match \d+.\d+", got=val, meta=meta)
                return val

            val = sb.integer_spec().normalise(meta, val)
            major = val >> 0x10
            minor = val & 0xFF
            return f"{major}.{minor}"
        else:
            if type(val) is int:
                return val

            val = sb.string_spec().normalise(meta, val)
            m = regexes["version_number"].match(val)
            if not m:
                raise BadSpecValue("Expected version string to match (\d+.\d+)", wanted=val, meta=meta)

            groups = m.groupdict()
            major = int(groups["major"])
            minor = int(groups["minor"])
            return (major << 0x10) + minor

class integer_spec(sb.Spec):
    """
    Normalise an integer

    Take into account whether we have ``enum`` or ``bitmask`` and ``allow_float``

    .. automethod:: photons_protocol.types.integer_spec.normalise_filled
    """
    def setup(self, pkt, enum, bitmask, unpacking=False, allow_float=False):
        self.pkt = pkt
        self.enum = enum
        self.bitmask = bitmask
        self.unpacking = unpacking
        self.allow_float = allow_float
        if self.enum and self.bitmask:
            raise ProgrammerError("Sorry, can't specify enum and bitmask for the same type")

    def normalise_filled(self, meta, val):
        """
        If we don't have an enum or bitmask

        * Return the value as is if it's a float and we allow floats
        * Return the value as is if it's an integer
        * Complain otherwise

        If we have an enum option then convert the value into that enum

        If we have a bitmask option then convert the value into a list of the
        applicable bitmasks.
        """
        if self.enum is None and self.bitmask is None:
            if self.allow_float and type(val) is float:
                return val
            return sb.integer_spec().normalise(meta, val)

        if self.enum:
            return enum_spec(self.pkt, self.enum, unpacking=self.unpacking).normalise(meta, val)
        else:
            return bitmask_spec(self.pkt, self.bitmask, unpacking=self.unpacking).normalise(meta, val)

class bitmask_spec(sb.Spec):
    """
    A bitmask is essentially an Enum with values that can be used as a mask.

    This enum must not have a member with a value of 0

    when unpacking, we are converting into a list of members from the enum.

    When packing we are converting members into a final sum'd integer.

    We accept values from the enum as:
    * String name of the member
    * String repr of the member
    * The value of the member
    * The member itself

    The bitmask may also be a callable that takes in the whole pkt and must return an Enum
    """
    def setup(self, pkt, bitmask, unpacking=False):
        self.pkt = pkt
        self.bitmask = bitmask
        self.unpacking = unpacking

    def normalise_filled(self, meta, val):
        bitmask = self.determine_bitmask()

        if val in (0, False):
            if self.unpacking:
                return []
            else:
                return 0

        if not self.unpacking:
            if type(val) is int:
                return val

        if val == "set()":
            val = set()

        if type(val) is str and val.startswith("{") and val.endswith("}"):
            val = val[1:-1].split(", ")

        if not isinstance(val, list) and not isinstance(val, set):
            val = [val]

        if self.unpacking:
            return self.unpack(bitmask, meta, val)
        else:
            return self.pack(bitmask, meta, val)

    def determine_bitmask(self):
        """
        Work out our bitmask value.

        if it's a callable and not an Enum class we call it with our packet to determine the bitmask.

        The bitmask must then be a subclass of enum.Enum

        And the bitmask must not have a member with the value zero
        """
        bitmask = self.bitmask
        if type(bitmask) is not enum.EnumMeta and callable(self.bitmask):
            bitmask = bitmask(self.pkt)

        try:
            if not issubclass(bitmask, enum.Enum):
                raise ProgrammerError("Bitmask is not an enum! got {0}".format(repr(bitmask)))
        except TypeError:
            raise ProgrammerError("Bitmask is not an enum! got {0}".format(repr(bitmask)))

        for name, member in bitmask.__members__.items():
            if member.value == 0:
                raise ProgrammerError("A bitmask with a zero value item makes no sense: {0} in {1}".format(name, repr(bitmask)))

        return bitmask

    def unpack(self, bitmask, meta, val):
        """Get us a list of bitmask members contained within the value"""
        result = []
        for v in val:
            if isinstance(v, bitmask):
                result.append(v)
            elif isinstance(v, enum.Enum):
                raise BadConversion("Can't convert value of wrong Enum", val=v, wanted=bitmask, got=type(v), meta=meta)
            else:
                if type(v) is int:
                    for name, member in bitmask.__members__.items():
                        if type(v) is int and v & member.value:
                            result.append(member)
                else:
                    found = False
                    for name, member in bitmask.__members__.items():
                        if v == name or v == repr(member):
                            result.append(member)
                            found = True
                            break

                    if not found:
                        raise BadConversion("Can't convert value into value from mask", val=v, wanted=bitmask)

        return set(result)

    def pack(self, bitmask, meta, val):
        """Return us a sum'd value of the bitmask members referred to by val"""
        final = 0
        used = []
        for v in val:
            if isinstance(v, bitmask):
                if v not in used:
                    final += v.value
                    used.append(v)
            elif isinstance(v, enum.Enum):
                raise BadConversion("Can't convert value of wrong Enum", val=v, wanted=bitmask, got=type(v), meta=meta)
            else:
                found = False
                for name, member in bitmask.__members__.items():
                    if v == name or v == repr(member) or v == member.value:
                        if member not in used:
                            final += member.value
                            used.append(member)
                        found = True
                        break

                if not found:
                    raise BadConversion("Can't convert value into mask", mask=bitmask, got=v)

        return final

class enum_spec(sb.Spec):
    """
    Convert between enum members and their corresponding value.

    Enum may either be a enum.Enum class or a callable that takes in the packet and returns an enum.Enum.

    When unpacking, we are converting into a member of the enum.

    When not unpacking, we are converting into the value of that member of the enum
    """
    def setup(self, pkt, enum, unpacking=False):
        self.pkt = pkt
        self.enum = enum
        self.unpacking = unpacking

    def normalise_filled(self, meta, val):
        em = self.determine_enum()

        if self.unpacking:
            return self.unpack(em, meta, val)
        else:
            return self.pack(em, meta, val)

    def unpack(self, em, meta, val):
        """Get us a member of the enum"""
        if isinstance(val, em):
            return val
        elif isinstance(val, enum.Enum):
            raise BadConversion("Can't convert value of wrong Enum", val=val, wanted=em, got=type(val), meta=meta)

        available = []
        for name, member in em.__members__.items():
            available.append((name, member.value))
            if val == name or val == repr(member) or val == member.value:
                return member

        # Only here if didn't match any members
        raise BadConversion("Value is not a valid value of the enum", val=val, enum=em, available=available, meta=meta)

    def pack(self, em, meta, val):
        """Get us the value of the specified member of the enum"""
        available = []
        for name, member in em.__members__.items():
            available.append((name, member.value))
            if val == name or val == repr(member) or val == member.value or val is member:
                return member.value

        if isinstance(val, enum.Enum):
            raise BadConversion("Can't convert value of wrong Enum", val=val, wanted=em, got=type(val), meta=meta)
        else:
            raise BadConversion("Value wasn't a valid enum value", val=val, available=available, meta=meta)

    def determine_enum(self):
        """
        Work out our enum value.

        if it's a callable and not an Enum class we call it with our packet to determine the enum.

        The bitmask must then be a subclass of enum.Enum
        """
        em = self.enum
        if type(em) is not enum.EnumMeta and callable(em):
            em = em(self.pkt)

        try:
            if not issubclass(em, enum.Enum):
                raise ProgrammerError("Enum is not an enum! got {0}".format(repr(em)))
        except TypeError:
            raise ProgrammerError("Enum is not an enum! got {0}".format(repr(em)))

        return em

class overridden(sb.Spec):
    """Normalise any value into an overridden value"""
    def setup(self, default_func, pkt):
        self.pkt = pkt
        self.default_func = default_func

    def normalise(self, meta, val):
        return self.default_func(self.pkt)

class defaulted(sb.Spec):
    """Normalise NotSpecified into a default value"""
    def setup(self, spec, default_func, pkt):
        self.pkt = pkt
        self.spec = spec
        self.default_func = default_func

    def normalise_empty(self, meta):
        return self.default_func(self.pkt)

    def normalise_filled(self, meta, val):
        return self.spec.normalise(meta, val)

class boolean(sb.Spec):
    """
    Normalise a value into a boolean

    .. automethod:: photons_protocol.types.boolean.normalise_filled
    """
    def normalise_empty(self, meta):
        raise BadSpecValue("Must specify boolean values", meta=meta)

    def normalise_filled(self, meta, val):
        """
        Booleans are returned as is.

        Integers are returned as True or False depending on whether they are 0 or 1

        Otherwise an error is raised
        """
        if type(val) is bool:
            return val
        if val in (0, 1):
            return bool(val)
        raise BadSpecValue("Could not convert value into a boolean", val=val, meta=meta)

class boolean_as_int_spec(sb.Spec):
    """
    Normalise a boolean value into an integer

    .. automethod:: photons_protocol.types.boolean_as_int_spec.normalise_empty

    .. automethod:: photons_protocol.types.boolean_as_int_spec.normalise_filled
    """
    def normalise_empty(self, meta):
        """Must specify boolean values"""
        raise BadSpecValue("Must specify boolean values", meta=meta)

    def normalise_filled(self, meta, val):
        """
        Booleans are returned as integer 0 or 1.

        Integers are returned as is if they are 0 or 1

        Otherwise an error is raised
        """
        if type(val) is bool:
            return int(val)
        if val in (0, 1):
            return val
        raise BadSpecValue("BoolInts must be True, False, 0 or 1", got=val, meta=meta)

class csv_spec(sb.Spec):
    """
    Normalise csv in and out of being a list of string or bytes

    .. automethod:: photons_protocol.types.csv_spec.normalise_filled
    """
    def __init__(self, pkt, size_bits, unpacking=False):
        self.pkt = pkt
        self.size_bits = size_bits
        self.unpacking = unpacking

    def normalise_filled(self, meta, val):
        """
        When we're unpacking, we are getting csv bytes and turning into a list of strings

        When we're packing, we are getting a list of strings that should turn into comma separated bytes
        """
        if self.unpacking:
            if type(val) is list:
                return val

            if type(val) is bitarray:
                val = val.tobytes()
            if type(val) is bytes:
                val = bytes_as_string_spec(self.pkt, self.size_bits, self.unpacking).normalise(meta, val)
            if type(val) is str:
                return val.split(',')
        else:
            if type(val) is list:
                val = ",".join(val)
            return bytes_as_string_spec(self.pkt, self.size_bits, self.unpacking).normalise(meta, val)

class bytes_spec(sb.Spec):
    """
    Ensure we have the right length of bytes

    This spec has no notion of packing or unpacking because it should be bitarray
    in either case.

    For good measure we just always convert string and bytes to bitarray

    .. automethod:: photons_protocol.types.bytes_spec.normalise_filled
    """
    def __init__(self, pkt, size_bits):
        self.pkt = pkt
        self.size_bits = size_bits

    def normalise_filled(self, meta, val):
        """
        * If we get a string, unhexlify it
        * convert the bytes into a bitarray
        * If we don't have a ``size_bits`` then return as is
        * If we do have size_bits, then either pad with 0s or cut off at the limit
        """
        if val in (None, 0):
            val = b""

        b = self.to_bitarray(meta, val)

        size_bits = self.size_bits
        if callable(size_bits):
            size_bits = self.size_bits(self.pkt)

        if size_bits is NotImplemented:
            return b

        if len(b) > size_bits:
            return b[:size_bits]
        elif len(b) < size_bits:
            return (b + bitarray('0' * (size_bits - len(b))))
        else:
            return b

    def to_bitarray(self, meta, val):
        """Return us the val as a bitarray"""
        if type(val) is bitarray:
            return val

        b = bitarray(endian="little")
        if type(val) is str:
            # We care about when the single quotes aren't here for when we copy output from `lifx unpack` into a `lifx pack`
            # This is because we say something like `lifx pack -- '{"thing": "<class 'input_algorithms.spec_base.NotSpecified'>"}'
            # And the quotes cancel each other out
            if val in ("<class input_algorithms.spec_base.NotSpecified>", "<class 'input_algorithms.spec_base.NotSpecified'>"):
                val = ""

            try:
                b.frombytes(binascii.unhexlify(val))
            except binascii.Error as error:
                raise BadConversion("Failed to turn str into bytes", meta=meta, val=val, error=error)
        else:
            try:
                b.frombytes(val)
            except TypeError as error:
                raise BadConversion("Failed to get a bitarray from the value", value=val, meta=meta)

        return b

class bytes_as_string_spec(sb.Spec):
    """
    Look for the null byte and use that to create a str

    .. automethod:: photons_protocol.types.bytes_as_string_spec.normalise_filled
    """
    def __init__(self, pkt, size_bits, unpacking=False):
        self.pkt = pkt
        self.size_bits = size_bits
        self.unpacking = unpacking

    def normalise_filled(self, meta, val):
        """
        If we're unpacking, then:

        * If a string, return as is
        * If bytes, find the null byte and cut off there

        If we're packing, then just use ``bytes_spec``
        """
        if self.unpacking:
            if type(val) is str:
                return val

            if type(val) is bitarray:
                val = val.tobytes()

            if b"\x00" in val:
                val = val[:val.find(b"\x00")]

            try:
                return val.decode()
            except UnicodeDecodeError as error:
                log.warning(hp.lc("Can't turn bytes into string, so just returning bytes", error=error))
                return val
            except Exception as error:
                raise BadSpecValue("String before the null byte could not be decoded", val=val, erorr=error)
        else:
            if type(val) is str:
                val = val.encode()
            return bytes_spec(self.pkt, self.size_bits).normalise(meta, val)

class float_spec(sb.Spec):
    """
    Make sure we can convert value into a float

    .. automethod:: photons_protocol.types.float_spec.normalise_filled
    """
    def normalise_filled(self, meta, val):
        if type(val) is bool:
            raise BadSpecValue("Converting a boolean into a float makes no sense", got=val, meta=meta)

        try:
            return float(val)
        except (TypeError, ValueError) as error:
            raise BadSpecValue("Failed to convert value into a float", got=val, error=error, meta=meta)

Type.install(
      ("Bool",     1,    bool, bool)

    , ("Int8",     8,    "<b",  int)
    , ("Uint8",    8,    "<B",  int)
    , ("BoolInt",  8,    "<?",  (bool, int))

    , ("Int16",    16,   "<h",  int)
    , ("Uint16",   16,   "<H",  int)

    , ("Int32",    32,   "<i",  int)
    , ("Uint32",   32,   "<I",  int)

    , ("Int64",    64,   "<q",  int)
    , ("Uint64",   64,   "<Q",  int)

    , ("Float",    32,   "<f",  float)
    , ("Double",   64,   "<d",  float)

    , ("Bytes",    None, None, bytes)
    , ("String",   None, None, str)
    , ("Reserved", None, None, bytes)

    , ("CSV",      None, None, (list, str, ","))
    , ("JSON",     None, None, json)
    )

json_spec = sb.match_spec(
      (bool, sb.any_spec())
    , (int, sb.any_spec())
    , (float, sb.any_spec())
    , (str, sb.any_spec())
    , (list, lambda: sb.listof(json_spec))
    , (type(None), sb.any_spec())
    , fallback=lambda: sb.dictof(sb.string_spec(), json_spec)
    )

# Here so we don't have to instantiate these every time we get a value from a packet
static_conversion_from_spec = {
      any: sb.any_spec()
    , bool: boolean()
    , float: float_spec()
    , (bool, int): boolean_as_int_spec()
    , json: json_spec
    }
