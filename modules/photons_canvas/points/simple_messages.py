"""
A simplified implementation of messages.

The normal implementation of messages in photons is very flexible and has many
features. Unfortunately this means that when we want to generate 5 Set64
messages every 0.075 seconds we can't make them fast enough.

This file contains a more manual implementation of the Set64 message that tries
to be as efficient as possible to allow us to keep up with the animation.
"""
from photons_messages import TileMessages, MultiZoneMessages
from photons_protocol.packing import PacketPacking
from photons_messages.fields import Color

from delfick_project.norms import sb
from lru import LRU
import binascii
import bitarray
import struct

ColorCache = LRU(0xFFFF)

TargetCache = LRU(1000)

seed_set64 = TileMessages.Set64.create(
    source=0,
    sequence=0,
    target="d073d5000000",
    res_required=False,
    ack_required=False,
    tile_index=0,
    length=1,
    x=0,
    y=0,
    width=8,
    duration=0,
    colors=[],
)

seed_set64_bytes = seed_set64.pack().tobytes()

uint16_packer = struct.Struct("<H")
uint32_packer = struct.Struct("<I")

empty_color = struct.pack("<HHHH", 0, 0, 0, 0)

ZERO = uint16_packer.pack(0)
FULL = uint16_packer.pack(0xFFFF)


def fill(color):
    if color is None:
        return empty_color

    c = ColorCache.get(color)
    if c is not None:
        return c

    h, s, b, k = color

    if h <= 0:
        hb = ZERO
    elif h >= 0x10000:
        hb = FULL
    else:
        hb = uint16_packer.pack(int(0x10000 * (h / 360)) % 0x10000)

    if s <= 0:
        sb = ZERO
    elif s >= 0xFFFF:
        sb = FULL
    else:
        sb = uint16_packer.pack(int(0xFFFF * s))

    if b <= 0:
        bb = ZERO
    elif b >= 0xFFFF:
        bb = FULL
    else:
        bb = uint16_packer.pack(int(0xFFFF * b))

    if k <= 0:
        kb = ZERO
    elif k >= 0xFFFF:
        kb = FULL
    else:
        kb = uint16_packer.pack(int(k))

    c = hb + sb + bb + kb
    ColorCache[color] = c
    return c


class Empty:
    pass


class Payload:
    message_type = 715

    class Meta:
        protocol = 1024

    def __init__(self, bts):
        self._bts = bts

    def __setitem__(self, rng, value):
        if isinstance(rng, int):
            self._bts[rng + 36] = value
        else:
            self._bts[rng.start + 36 : rng.stop + 36] = value

    def __getitem__(self, rng):
        if isinstance(rng, int):
            return self._bts[rng + 36]
        return self._bts[rng.start + 36 : rng.stop + 36]


class Set64:
    Payload = Payload

    def __init__(self, *, bts=None, set_source=False, **kwargs):
        if bts:
            self._bts = bts
        else:
            self._bts = bytearray(seed_set64_bytes)

        self.set_source = set_source
        self.payload = Payload(self._bts)
        self.update(kwargs)

    def update(self, values):
        for k, v in values.items():
            setattr(self, k, v)

    def actual(self, key):
        if key == "duration":
            return self.duration * 1000
        return getattr(self, key)

    def simplify(self):
        return self

    def clone(self):
        return Set64(bts=bytearray(self._bts), set_source=self.set_source)

    def tobytes(self, serial=None):
        return bytes(self._bts)

    @property
    def is_dynamic(self):
        return False

    def pack(self):
        b = bitarray.bitarray(endian="little")
        b.frombytes(bytes(self._bts))
        return b

    def __getitem__(self, rng):
        return self._bts[rng]

    def __setitem__(self, rng, value):
        self._bts[rng] = value

    def __or__(self, other):
        return seed_set64 | other

    @property
    def size(self):
        """returns the size of the total message."""
        return uint16_packer.unpack(self[0:2])[0]

    @size.setter
    def size(self, value):
        self[0:2] = uint16_packer.pack(value)

    @property
    def protocol(self):
        """returns the protocol version of the header."""
        v = uint16_packer.unpack(self[2:4])[0]
        mask = 0b111111111111
        return v & mask

    @protocol.setter
    def protocol(self, value):
        current = uint16_packer.unpack(self[2:4])[0]
        mask = 0b111111111111
        invmask = mask ^ 0xFFFF
        self[2:4] = uint16_packer.pack(current & invmask | value & mask)

    @property
    def addressable(self):
        """returns whether the addressable bit is set."""
        v = self[3]
        return (v >> 4 & 0b1) != 0

    @addressable.setter
    def addressable(self, value):
        v = int(bool(value))
        current = self[3]

        mask = 0b10000
        invmask = mask ^ 0xFF

        self[3] = current & invmask | v << 4 & mask

    @property
    def tagged(self):
        """returns whether the tagged bit is set."""
        v = self[3]
        return (v >> 5 & 0b1) != 0

    @tagged.setter
    def tagged(self, value):
        v = int(bool(value))
        current = self[3]

        mask = 0b100000
        invmask = mask ^ 0xFF

        self[3] = current & invmask | v << 5 & mask

    @property
    def source(self):
        """returns then number used by clients to differentiate themselves from other clients"""
        if not self.set_source:
            return sb.NotSpecified
        return uint32_packer.unpack(self[4:8])[0]

    @source.setter
    def source(self, value):
        self.set_source = True
        if isinstance(value, tuple):
            value = value[1]
        self[4:8] = uint32_packer.pack(value)

    @property
    def serial(self):
        bts = self.target
        s = TargetCache.get(bts)

        if not s:
            s = binascii.hexlify(bts[:6]).decode()
            TargetCache[bts] = s

        return s

    @property
    def target(self):
        """returns the target Serial from the header."""
        return bytes(self[8:16])

    @target.setter
    def target(self, serial):
        bts = TargetCache.get(serial)
        if not bts:
            bts = binascii.unhexlify(serial)[:6] + b"\x00\x00"
            TargetCache[serial] = bts
        self[8:16] = bts

    @property
    def res_required(self):
        """returns whether the response required bit is set in the header."""
        v = self[22]
        return (v & 0b1) != 0

    @res_required.setter
    def res_required(self, value):
        v = int(bool(value))
        current = self[22]

        mask = 0b1
        invmask = mask ^ 0xFF

        self[22] = current & invmask | v & mask

    @property
    def ack_required(self):
        """returns whether the ack required bit is set in the header."""
        v = self[22]
        v = v >> 1
        return (v & 0b1) != 0

    @ack_required.setter
    def ack_required(self, value):
        v = int(bool(value))
        current = self[22]

        mask = 0b10
        invmask = mask ^ 0xFF

        self[22] = current & invmask | v << 1 & mask

    @property
    def sequence(self):
        """returns the sequence ID from the header."""
        return self[23]

    @sequence.setter
    def sequence(self, value):
        self[23] = value

    @property
    def pkt_type(self):
        """returns the Payload ID for the accompanying payload in the message."""
        return uint16_packer.unpack(self[32:34])[0]

    @pkt_type.setter
    def pkt_type(self, value):
        self[32:34] = uint16_packer.pack(value)

    @property
    def tile_index(self):
        return self.payload[0]

    @tile_index.setter
    def tile_index(self, value):
        self.payload[0] = value

    @property
    def length(self):
        return self.payload[1]

    @length.setter
    def length(self, value):
        self.payload[1] = value

    @property
    def x(self):
        return self.payload[3]

    @x.setter
    def x(self, value):
        self.payload[3] = value

    @property
    def y(self):
        return self.payload[4]

    @y.setter
    def y(self, value):
        self.payload[4] = value

    @property
    def width(self):
        return self.payload[5]

    @width.setter
    def width(self, value):
        self.payload[5] = value

    @property
    def duration(self):
        return uint32_packer.unpack(self.payload[6:10])[0] / 1000

    @duration.setter
    def duration(self, value):
        self.payload[6:10] = uint32_packer.pack(int(value * 1000))

    @property
    def colors(self):
        colors = []
        for i in range(64):
            b = bitarray.bitarray(endian="little")
            b.frombytes(bytes(self.payload[10 + i * 8 : 18 + i * 8]))
            colors.append(PacketPacking.unpack(Color, b))
        return colors

    @colors.setter
    def colors(self, colors):
        b = b""
        for color in colors:
            b += fill(color)
        self.payload[10 : 10 + len(colors) * 8] = b


class MultizoneMessagesMaker:
    def __init__(self, serial, cap, colors, *, duration=1, zone_index=0):
        self.cap = cap
        self.serial = serial
        self.colors = colors
        self.duration = duration
        self.zone_index = zone_index

    @property
    def msgs(self):
        if self.cap.has_extended_multizone:
            yield from self.make_new_messages()
        else:
            yield from self.make_old_messages()

    def make_old_messages(self):
        if not self.colors:
            return

        end = self.zone_index
        start = self.zone_index

        current = Empty

        sections = []

        for i, color in enumerate(self.colors):
            i = i + self.zone_index

            if current is Empty:
                current = color
                continue

            if current != color:
                sections.append([start, end, current])
                start = i
                start = i

            current = color
            end = i

        if current is not Empty and (not sections or sections[-1][1] != i):
            sections.append([start, end, current])

        msgs = []
        for start, end, color in sections:
            h, s, b, k = color

            msgs.append(
                MultiZoneMessages.SetColorZones(
                    start_index=start,
                    end_index=end,
                    duration=self.duration,
                    ack_required=True,
                    res_required=False,
                    target=self.serial,
                    hue=h,
                    saturation=s,
                    brightness=b,
                    kelvin=k,
                )
            )
        return msgs

    def make_new_messages(self):
        if not self.colors:
            return

        colors = []
        for c in self.colors:
            if isinstance(c, dict) or getattr(c, "is_dict", False):
                colors.append(c)
            else:
                colors.append(Color(*c))

        return (
            MultiZoneMessages.SetExtendedColorZones(
                duration=self.duration,
                colors_count=len(self.colors),
                colors=colors,
                target=self.serial,
                zone_index=self.zone_index,
                ack_required=True,
                res_required=False,
            ),
        )


__all__ = ["Set64", "MultizoneMessagesMaker"]
