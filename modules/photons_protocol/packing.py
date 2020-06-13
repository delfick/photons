from photons_protocol.errors import BadConversion
from photons_protocol.types import Optional

from delfick_project.norms import sb, dictobj
from collections import defaultdict
from bitarray import bitarray
from lru import LRU
import binascii
import struct


packers = {}
pack_cache = defaultdict(lambda: LRU(0xFFFF))
unpack_cache = defaultdict(lambda: LRU(0xFFFF))


def pack(fmt, val):
    pk = packers.get(fmt)
    if pk is None:
        pk = packers[fmt] = struct.Struct(fmt)
    return pk.pack(val)


def unpack(fmt, val):
    pk = packers.get(fmt)
    if pk is None:
        pk = packers[fmt] = struct.Struct(fmt)
    return pk.unpack(val)


def from_cache(fmt, val, typ, cache):
    key = (fmt, val)
    hashable = False
    if not typ._allow_callable:
        try:
            hash(key)
        except TypeError:
            hashable = False
        else:
            hashable = True

    c = None
    if hashable:
        c = cache.get(key)

    return key, hashable, val, c


def val_to_bitarray(val, doing):
    """Convert a value into a bitarray"""
    if val is sb.NotSpecified:
        val = b""

    if type(val) is bitarray:
        return val

    if type(val) is str:
        val = binascii.unhexlify(val.encode())

    if type(val) is not bytes:
        raise BadConversion("Couldn't get bitarray from a value", value=val, doing=doing)

    b = bitarray(endian="little")
    b.frombytes(val)
    return b


class BitarraySlice:
    def __init__(self, name, typ, val, size_bits, group, values):
        self.typ = typ
        self.val = val
        self.name = name
        self.group = group
        self.values = values
        self.size_bits = size_bits

    @property
    def fmt(self):
        return self.typ.struct_format

    @property
    def unpackd(self):
        val = self.val
        typ = self.typ
        fmt = typ.struct_format

        if fmt is bool and self.size_bits == 1:
            return False if val.to01() == "0" else True

        original_size = typ.original_size
        if callable(original_size):
            original_size = original_size(self.values)

        if len(val) < original_size:
            padding = bitarray("0" * (original_size - len(val)), endian="little")
            if getattr(self.typ, "left_cut", False):
                val = padding + val
            else:
                val = val + padding

        if fmt is None:
            return val

        key, hashable, val, c = from_cache(typ.struct_format, val.tobytes(), typ, unpack_cache)

        if c is None:
            try:
                c = unpack_cache[key] = unpack(fmt, val)[0]
            except (struct.error, TypeError, ValueError) as error:
                raise BadConversion(
                    "Failed to unpack field",
                    group=self.group,
                    field=self.name,
                    typ=typ,
                    val=getattr(val, "to01", lambda: val)(),
                    error=error,
                )

        return c


class FieldInfo:
    def __init__(self, name, typ, val, size_bits, group):
        self.typ = typ
        self.val = val
        self.name = name
        self.group = group
        self.size_bits = size_bits

    def __eq__(self, other):
        if not isinstance(other, FieldInfo):
            return False

        return (
            self.name == other.name
            and self.typ == other.typ
            and self.val == other.val
            and self.size_bits == other.size_bits
            and self.group == other.group
        )

    @property
    def value(self):
        """Get us the val, taking into account if this is a T.Reserved field"""
        # Reserved is the only case where sb.NotSpecified is allowed
        val = self.val
        if self.typ.__class__.__name__ == "Reserved" and val is sb.NotSpecified:
            return bitarray("0" * self.size_bits, endian="little")
        else:
            return val

    def to_sized_bitarray(self):
        result = self.to_bitarray()
        size_bits = self.size_bits
        if size_bits < len(result):
            if getattr(self.typ, "left_cut", False):
                result = result[-size_bits:]
            else:
                result = result[:size_bits]
        return result

    def to_bitarray(self):
        fmt = self.typ.struct_format
        val = self.value

        if val is sb.NotSpecified:
            raise BadConversion(
                "Cannot pack an unspecified value",
                got=val,
                field=self.name,
                group=self.group,
                typ=self.typ,
            )

        if type(val) is bitarray:
            return val

        key, hashable, val, c = from_cache(fmt, val, self.typ, pack_cache)

        if c is None:
            c = self._to_bitarray(fmt, val)
            if hashable:
                pack_cache[key] = c

        return c

    def _to_bitarray(self, fmt, val):
        if type(fmt) is str:
            return self.struct_format(fmt, val)

        elif fmt is bool:
            if type(val) is not bool:
                raise BadConversion(
                    "Trying to convert a non boolean into 1 bit",
                    got=val,
                    group=self.group,
                    field=self.name,
                )
            return (
                bitarray("0", endian="little") if val is False else bitarray("1", endian="little")
            )

        else:
            b = bitarray(endian="little")
            b.frombytes(val)
            return b

    def struct_format(self, fmt, val):
        b = bitarray(endian="little")
        try:
            if val is Optional:
                val = 0
            b.frombytes(pack(fmt, val))
        except struct.error as error:
            raise BadConversion(
                "Failed trying to convert a value",
                val=val,
                fmt=fmt,
                error=error,
                group=self.group,
                name=self.name,
            )
        return b


class PacketPacking(object):
    @classmethod
    def fields_in(kls, pkt, parent, serial):
        for name, typ in pkt.Meta.all_field_types:
            val = pkt.__getitem__(
                name,
                parent=parent,
                serial=serial,
                allow_bitarray=True,
                unpacking=False,
                do_transform=False,
            )
            size_bits = typ.size_bits
            if callable(size_bits):
                size_bits = size_bits(pkt)
            group = pkt.Meta.name_to_group.get(name, pkt.__class__.__name__)

            if not typ._multiple:
                yield FieldInfo(name, typ, val, size_bits, group)
            else:
                if not isinstance(val, list):
                    raise BadConversion("Expected field to be a list", name=name, val=type(val))

                number = typ._multiple
                if callable(number):
                    number = number(pkt)

                if len(val) != number:
                    raise BadConversion(
                        "Expected correct number of items", name=name, found=len(val), want=number
                    )

                for v in val:
                    yield FieldInfo(name, typ, v, size_bits, group)

    @classmethod
    def pkt_from_bitarray(kls, pkt_kls, value):
        i = 0
        final = pkt_kls()

        for name, typ in pkt_kls.Meta.all_field_types:
            single_size_bits = typ.size_bits
            if callable(single_size_bits):
                single_size_bits = single_size_bits(final)

            multiple = typ._multiple

            size_bits = single_size_bits
            if multiple:
                if callable(multiple):
                    multiple = multiple(final)
                size_bits *= multiple

            val = value[i : i + size_bits]
            i += size_bits

            if multiple and typ.struct_format:
                j = 0
                res = []
                for _ in range(multiple):
                    v = val[j : j + single_size_bits]
                    j += single_size_bits
                    info = BitarraySlice(name, typ, v, single_size_bits, pkt_kls.__name__, final)
                    res.append(info.unpackd)
                final[name] = res
                continue

            info = BitarraySlice(name, typ, val, size_bits, pkt_kls.__name__, final)
            dictobj.__setitem__(final, info.name, info.unpackd)
        return final, i

    @classmethod
    def pack(kls, pkt, payload=None, parent=None, serial=None):
        """
        This uses the ``Meta`` on the packet to determine the order of all the
        fields and uses that to extract values from the object and uses the type
        object for each field to convert the value into a bitarray object.

        Finally, the bitarray object is essentially concated together to create
        one final bitarray object.

        This code assumes the packet has little endian.

        If ``payload`` is provided and this packet is a ``parent_packet`` and
        it's last field has a ``message_type`` property of 0, then that payload
        is converted into a bitarray and added to the end of the result.
        """
        final = bitarray(endian="little")

        for info in kls.fields_in(pkt, parent, serial):
            result = info.to_sized_bitarray()

            if result is None:
                raise BadConversion("Failed to convert field into a bitarray", field=info.as_dict())

            final += result

        # If this is a parent packet with a Payload of message_type 0
        # Then this means we have no payload fields and so must append
        # The entire payload at the end
        # As opposed to individual fields in the payload one at a time
        if getattr(pkt, "parent_packet", False) and pkt.Meta.field_types:
            name, typ = pkt.Meta.field_types[-1]
            if getattr(typ, "message_type", None) == 0:
                final += val_to_bitarray(
                    payload or pkt[name], doing="Adding payload when packing a packet"
                )

        return final

    @classmethod
    def unpack(kls, pkt_kls, value):
        """
        If the ``value`` is not a bitarray already, it is assumed to be ``bytes``
        and converted into a bitarray.

        We then get information about each field from ``Meta`` and use that to
        slice the value into chunks that are used to determine a value for each
        field.

        If this is a ``parent_packet`` and the last field has a ``message_type``
        property of 0, then the remainder of the ``value`` is assigned as
        bytes to that field on the final instance.
        """
        value = val_to_bitarray(value, doing="Making bitarray to unpack")
        final, index = kls.pkt_from_bitarray(pkt_kls, value)

        if getattr(pkt_kls, "parent_packet", False) and index < len(value):
            for name, typ in pkt_kls.Meta.field_types:
                if getattr(typ, "message_type", None) == 0:
                    final[name] = value[index:]

        return final
