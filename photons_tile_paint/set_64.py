"""
Tile animations requires packing many Set64 messages in a short amount of
time. This file exists to make that as efficient as possible by creating a class
that can pack a Set64 for tile animation with as much caching power as
possible

Don't use this directly, always use it via the
photons_tile_paint.animation.canvas_to_msgs function
"""
from photons_messages.fields import hsbk, Color as ProtocolColor
from photons_messages import TileMessages
from photons_protocol.messages import T

from input_algorithms import spec_base as sb
from bitarray import bitarray
from lru import LRU
import functools
import binascii
import operator
import struct

class Set64Maker:
    """
    One of these is made as the set_64_maker callable. It contains as much
    of the Set64 message packd as we can and then provides a fake Set64
    that photons can use to create the messages
    """
    class Target:
        """Used to cache the bits for our target"""
        def __init__(self, val):
            self.bytes = val
            self.serial = binascii.hexlify(val[:6]).decode()

            self.packd = bitarray(endian="little")
            self.packd.frombytes(val)

    class Set64:
        """
        The actual fake message

        We assume this is used via canvas_to_msgs and so we expect kwargs to
        contain "ack_required", "tile_index", "width", "duration" and "colors"

        And we assume target is set via a setter property and .update() is
        called with source and sequence

        Because this is for tile animations, the rest of the payload is always
        length=1, x=0, y=0; and res_required is always False

        We use a real TileMessages.Set64 to get the packed bits for the parts
        that do not change, which is stored on the maker (the instance of Set64Maker)
        """
        def __init__(self, maker, **kwargs):
            self.kwargs = kwargs
            self.maker = maker
            self.extra = {}

        def pack(self):
            bits = []

            # Frame header
            bits.append(self.maker.frame_header_start)
            bits.append(self.maker.source_bits(self.extra["source"]))

            # Frame Address
            bits.append(self.extra["target"].packd)
            if self.kwargs["ack_required"]:
                bits.append(self.maker.frame_address_with_acks_middle)
            else:
                bits.append(self.maker.frame_address_without_acks_middle)
            bits.append(self.maker.sequence_bits[self.extra["sequence"]])

            # Protocol Header
            bits.append(self.maker.protocol_header_packd)

            # Payload
            bits.append(self.maker.tile_index_bits[self.kwargs["tile_index"]])
            bits.append(self.maker.payload_middle)
            bits.append(self.maker.width_bits[self.kwargs["width"]])
            bits.append(self.maker.duration_bits(self.kwargs["duration"]))
            bits.append(self.maker.colors_bits(self.kwargs["colors"]))

            return functools.reduce(operator.add, bits)

        def tobytes(self, serial=None):
            return self.pack().tobytes()

        def simplify(self):
            return self

        def clone(self):
            res = self.__class__(self.maker, **self.kwargs)
            res.update(self.extra)
            return res

        def update(self, extra):
            self.extra.update(extra)

            if "target" in extra and not isinstance(extra["target"], self.maker.Target):
                self.target = extra["target"]

        @property
        def target(self):
            if "target" in self.extra:
                return self.extra["target"].bytes
            return sb.NotSpecified

        @target.setter
        def target(self, val):
            self.update({"target": self.maker.make_target(val)})

        @property
        def serial(self):
            if "target" not in self.extra:
                return "000000000000"
            return self.extra["target"].serial

        @property
        def res_required(self):
            return False

        @property
        def ack_required(self):
            return self.kwargs["ack_required"]

        @property
        def source(self):
            return self.extra["source"]

        @source.setter
        def source(self, val):
            """Source is set on the clone by the photons_transport writer"""
            self.extra["source"] = val

        @property
        def sequence(self):
            return self.extra["sequence"]

        @property
        def is_dynamic(self):
            return False

        @property
        def colors(self):
            return self.kwargs.get("colors", [])

    def __init__(self):
        self.targets_cache = LRU(1000)
        self.source_bits_cache = LRU(10)
        self.duration_bits_cache = LRU(10)

        self.cache = ProtocolColor.Meta.cache

        msg = TileMessages.Set64(
              source = 0
            , sequence = 0
            , target = None
            , res_required = False
            , ack_required = True

            , tile_index = 0
            , length = 1
            , x = 0
            , y = 0
            , width = 8
            , duration = 0
            , colors = [{"hue": 0, "saturation": 0, "brightness": 0, "kelvin": 3500}]
            )

        self.frame_header_start = msg.frame_header.pack()[:-32]

        self.frame_address_with_acks_middle = msg.frame_address.pack()[64:-8]
        msg.ack_required = False
        self.frame_address_without_acks_middle = msg.frame_address.pack()[64:-8]

        self.protocol_header_packd = msg.protocol_header.pack()

        # tile_index, width, duration and colors are variable
        self.payload_middle = msg.payload.pack()[8:-8 -32 - (64 * 64)]

        self.uint8_bits = {val: self.bits(T.Uint8, val) for val in range(256)}

        self.width_bits = self.uint8_bits
        self.sequence_bits = self.uint8_bits
        self.tile_index_bits = self.uint8_bits

    def bits(self, typ, val):
        bits = bitarray(endian="little")
        bits.frombytes(struct.pack(typ.struct_format, val))
        return bits

    def source_bits(self, val):
        if val not in self.source_bits_cache:
            self.source_bits_cache[val] = self.bits(T.Uint32, val)
        return self.source_bits_cache[val]

    def duration_bits(self, val):
        if val not in self.duration_bits_cache:
            self.duration_bits_cache[val] = self.bits(T.Uint32, int(val * 1000))
        return self.duration_bits_cache[val]

    def colors_bits(self, colors):
        res = []
        for color in colors:
            fields = color.cache_key
            if fields not in self.cache:
                bits = []
                bits.append(self.bits(hsbk[0][1], int(65535 * (color.hue / 360))))
                bits.append(self.bits(hsbk[1][1], int(65535 * color.saturation)))
                bits.append(self.bits(hsbk[2][1], int(65535 * color.brightness)))
                bits.append(self.bits(hsbk[3][1], color.kelvin))
                self.cache[fields] = functools.reduce(operator.add, bits)
            res.append(self.cache[fields])
        return functools.reduce(operator.add, res)

    def make_target(self, target):
        if target not in self.targets_cache:
            val = target
            if isinstance(target, str):
                val = binascii.unhexlify(target)

            if isinstance(val, bytes) and len(val) == 6:
                val += b"\x00\x00"

            self.targets_cache[target] = self.Target(val)
        return self.targets_cache[target]

    def __call__(self, **kwargs):
        return self.Set64(self, **kwargs)

# Used to create a message that photons thinks is a valid Set64
# It is a callable that requires keyword arguments for
# ack_required, tile_index, width, duration, colors
set_64_maker = Set64Maker()
