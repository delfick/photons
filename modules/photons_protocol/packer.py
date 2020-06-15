from photons_protocol.errors import BadConversion
from photons_protocol.constants import Optional

from collections import defaultdict
from bitarray import bitarray
from lru import LRU
import binascii
import struct


packers = {}
pack_cache = defaultdict(lambda: LRU(0xFFFF))
unpack_cache = defaultdict(lambda: LRU(0xFFFF))


def from_cache(fmt, val, cache):
    key = (fmt, val)
    hashable = False

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


class PackCache:
    @classmethod
    def pack(kls, fmt, val):
        pk = packers.get(fmt)
        if pk is None:
            pk = packers[fmt] = struct.Struct(fmt)
        return pk.pack(val)

    @classmethod
    def from_cache(kls, fmt, val):
        return from_cache(fmt, val, pack_cache)

    @classmethod
    def set_cache(kls, key, val):
        pack_cache[key] = val

    @classmethod
    def to_bitarray(kls, fmt, val, **extra_info):
        b = bitarray(endian="little")
        try:
            if val is Optional:
                val = 0
            b.frombytes(kls.pack(fmt, val))

        except struct.error as error:
            raise BadConversion(
                "Failed trying to convert a value", val=val, fmt=fmt, error=error, **extra_info
            )

        return b

    @classmethod
    def convert(kls, fmt, val, **extra_info):
        if type(fmt) is str:
            try:
                bts = kls.pack(fmt, val)
            except (struct.error, TypeError, ValueError) as error:
                raise BadConversion(
                    "Failed to pack field", val=val, fmt=fmt, error=error, **extra_info
                )
            else:
                b = bitarray(endian="little")
                b.frombytes(bts)
                return b

        elif fmt is bool:
            if val == 1:
                val = True
            elif val == 0:
                val = False

            if type(val) is not bool:
                raise BadConversion(
                    "Trying to convert a non boolean into 1 bit", val=val, **extra_info
                )

            return (
                bitarray("0", endian="little") if val is False else bitarray("1", endian="little")
            )

        else:
            b = bitarray(endian="little")

            try:
                b.frombytes(val)
            except (TypeError, TypeError) as error:
                raise BadConversion(
                    "Failed to convert bytes into bitarray",
                    val=val,
                    val_type=type(val),
                    error=error,
                    **extra_info
                )

            return b


class UnpackCache:
    @classmethod
    def unpack(kls, fmt, val):
        pk = packers.get(fmt)
        if pk is None:
            pk = packers[fmt] = struct.Struct(fmt)
        return pk.unpack(val)

    @classmethod
    def serial(kls, val):
        key, hashable, _, c = kls.from_cache("serial", val.to01())
        if c is None:
            bts = val.tobytes()
            c = (bts, binascii.hexlify(bts[:6]).decode())
            kls.set_cache(key, c)
        return c

    @classmethod
    def from_cache(kls, fmt, val):
        return from_cache(fmt, val, unpack_cache)

    @classmethod
    def set_cache(kls, key, val):
        unpack_cache[key] = val

    @classmethod
    def convert(kls, fmt, val, **extra_info):
        try:
            return kls.unpack(fmt, val)[0]
        except (struct.error, TypeError, ValueError) as error:
            raise BadConversion(
                "Failed to unpack field",
                val=getattr(val, "to01", lambda: val)(),
                fmt=fmt,
                error=error,
                **extra_info
            )
