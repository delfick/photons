from photons_protocol.errors import BadConversion

from delfick_project.norms import sb
from bitarray import bitarray
import binascii


class UnsetRepr(type):
    def __repr__(kls):
        return "<Unset>"


class Unset(metaclass=UnsetRepr):
    """Used to specify a value that has not been set"""


class OptionalRepr(type):
    def __repr__(kls):
        return "<Optional>"


class Optional(metaclass=OptionalRepr):
    pass


class unbound_bytes_spec(sb.Spec):
    def setup(self, location):
        self.location = location

    def normalise(self, meta, val):
        return ensure_bitarray(val, **self.location)


class UnboundBytes:
    struct_format = None

    is_optional = False
    has_default = False
    has_transform = False
    has_side_effect = False

    def __init__(self, field):
        self.pack_spec = unbound_bytes_spec(field.location)
        self.unpack_spec = self.pack_spec

    def do_pack_transform(self, pkt, value):
        return value

    def do_unpack_transform(self, pkt, value):
        return value

    def get_default(self, pkt):
        return bitarray(endian="little")


def ensure_bitarray(val, **extra_info):
    """Convert a bytes or bitarray value into a bitarray"""
    if val is sb.NotSpecified:
        val = b""

    if type(val) is bitarray:
        return val

    if type(val) is str:
        val = binascii.unhexlify(val.encode())

    if type(val) is not bytes:
        raise BadConversion("Couldn't get bitarray from a value", value=val, **extra_info)

    b = bitarray(endian="little")
    b.frombytes(val)
    return b
