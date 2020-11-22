"""
The messages system is essentially a collection system for all the Protocol
Payloads.

We create collections of messages by defining them as properties on a subclass
of ``photons_protocol.messages.Messages``.

This class is a combination of a mixin class for functionality and a meta class
for defining ``by_type`` on the class.
"""
from photons_protocol.types import Type, MultiOptions
from photons_protocol.errors import BadConversion

from bitarray import bitarray
from textwrap import dedent
import binascii
import inspect
import logging

log = logging.getLogger("photons_protocol.messages")

T = Type
MultiOptions = MultiOptions


class PacketTypeExtractor:
    @classmethod
    def packet_type(kls, data):
        if isinstance(data, dict):
            return kls.packet_type_from_dict(data)
        elif isinstance(data, bytes):
            return kls.packet_type_from_bytes(data)
        elif isinstance(data, bitarray):
            return kls.packet_type_from_bitarray(data)
        else:
            raise BadConversion("Can't determine packet type from data", got=data)

    @classmethod
    def packet_type_from_dict(kls, data):
        if "protocol" in data:
            protocol = data["protocol"]
        elif "frame_header" in data and "protocol" in data["frame_header"]:
            protocol = data["frame_header"]["protocol"]
        else:
            raise BadConversion("Couldn't work out protocol from dictionary", got=data)

        if "pkt_type" in data:
            pkt_type = data["pkt_type"]
        elif "pkt_type" in data.get("protocol_header", {}):
            pkt_type = data["protocol_header"]["pkt_type"]
        else:
            raise BadConversion("Couldn't work out pkt_type from dictionary", got=data)

        return protocol, pkt_type

    @classmethod
    def packet_type_from_bitarray(kls, data):
        if len(data) < 28:
            raise BadConversion("Data is too small to be a LIFX packet", got=len(data) // 8)

        b = bitarray(endian="little")
        b.extend(data[16 : 16 + 12])
        protbts = b.tobytes()
        protocol = protbts[0] + (protbts[1] << 8)

        pkt_type = None

        if protocol == 1024:
            if len(data) < 288:
                raise BadConversion(
                    "Data is too small to be a LIFX packet", need_atleast=36, got=len(data) // 8
                )

            ptbts = data[256 : 256 + 16].tobytes()
            pkt_type = ptbts[0] + (ptbts[1] << 8)

        return protocol, pkt_type

    @classmethod
    def packet_type_from_bytes(kls, data):
        if len(data) < 4:
            raise BadConversion("Data is too small to be a LIFX packet", got=len(data))

        b = bitarray(endian="little")
        b.frombytes(data[2:4])
        protbts = b[:12].tobytes()
        protocol = protbts[0] + (protbts[1] << 8)

        pkt_type = None

        if protocol == 1024:
            if len(data) < 36:
                raise BadConversion(
                    "Data is too small to be a LIFX packet", need_atleast=36, got=len(data)
                )
            pkt_type = data[32] + (data[33] << 8)

        return protocol, pkt_type


def sources_for(kls):
    buf = []
    in_kls = None

    try:
        src = inspect.getsource(kls)
    except SyntaxError:
        # Likely the tests
        # Seems inspect.getsource doesn't look at coding in python3.9
        return
    except OSError as error:
        if error.args and error.args[0] == "could not find class definition":
            log.warning("Couldn't find source code for kls\tkls={0}".format(kls))
        else:
            raise
    else:
        for line in src.split("\n"):
            attr = line[: line.find("=")].replace(" ", "")
            if attr and attr[0].isupper():
                if buf and in_kls:
                    yield in_kls, dedent("\n".join(buf))

                buf = []
                in_kls = attr

            if not line.strip().startswith("#"):

                buf.append(line)

        if buf and in_kls:
            yield in_kls, dedent("\n".join(buf))


class MessagesMixin:
    """
    Functionality for a collection of Protocol Messages
    """

    @classmethod
    def get_packet_type(kls, data, protocol_register):
        """
        Given a ProtocolRegister and some data (bytes or dictionary)
        return ``(protocol, pkt_type, Packet, kls, data)``

        protocol
            The number specifying the "protocol" of this message. This is
            likely to always be 1024.

        pkt_type
            The number assigned to this payload type. This code assumes the
            unpacked data has a ``pkt_type`` property that is retrieved for this.

        Packet
            The ``parent_packet`` class for the protocol the data represents.

            If ``data`` is bytes, get the integer from bits 16 to 28 as protocol.

            Use this number in protocol register to find the ``parent_packet``.

        kls
            The payload class representing this protocol and pkt_type.

            This is None if the protocol/pkt_type pair is unknown

        data
            If the data was a dictionary, bytes or bitarray then returned as is
            if the data was a str, then we return it as unhexlified bytes
        """
        if isinstance(data, str):
            data = binascii.unhexlify(data)

        protocol, pkt_type = PacketTypeExtractor.packet_type(data)

        prot = protocol_register.get(protocol)
        if prot is None:
            raise BadConversion(
                "Unknown packet protocol", wanted=protocol, available=list(protocol_register)
            )
        Packet, messages_register = prot

        mkls = None
        for k in messages_register:
            if pkt_type in k.by_type:
                mkls = k.by_type[pkt_type]
                break

        return protocol, pkt_type, Packet, mkls, data

    @classmethod
    def unpack_bytes(kls, data, protocol, pkt_type, protocol_register, unknown_ok=False):
        if isinstance(data, str):
            data = binascii.unhexlify(data)

        if isinstance(data, bytes):
            b = bitarray(endian="little")
            b.frombytes(data)
            data = b

        prot = protocol_register.get(protocol)
        if prot is None:
            raise BadConversion(
                "Unknown packet protocol", wanted=protocol, available=list(protocol_register)
            )
        Packet, messages_register = prot

        mkls = None
        for k in messages_register:
            if pkt_type in k.by_type:
                mkls = k.by_type[pkt_type]
                break

        if mkls is None:
            if unknown_ok:
                mkls = Packet
            else:
                raise BadConversion("Unknown message type!", protocol=protocol, pkt_type=pkt_type)

        return mkls.create(data)

    @classmethod
    def create(kls, data, protocol_register, unknown_ok=False):
        """
        Return a fully resolved packet instance from the data and protocol_register.

        unknown_ok
            Whether we return an instance of the parent_packet with unresolved
            payload if we don't have a payload class, or if we raise an error
        """
        protocol, pkt_type, Packet, PacketKls, data = kls.get_packet_type(data, protocol_register)

        if PacketKls:
            return PacketKls.create(data)

        if unknown_ok:
            return Packet.create(data)

        raise BadConversion("Unknown message type!", protocol=protocol, pkt_type=pkt_type)

    @classmethod
    def pack_payload(kls, pkt_type, data, messages_register=None):
        """
        Given some payload data as a dictionary and it's ``pkt_type``, return a
        hexlified string of the payload.
        """
        for k in messages_register or [kls]:
            if int(pkt_type) in k.by_type:
                return k.by_type[int(pkt_type)].Payload.create(data).pack()
        raise BadConversion("Unknown message type!", pkt_type=pkt_type)

    @classmethod
    def pack(kls, data, protocol_register, unknown_ok=False):
        """
        Return a hexlified string of the data.

        This uses ``pkt_type`` and ``protocol`` in the data, along with the
        protocol_register to find the appropriate class to use to perform the
        packing.
        """
        protocol, pkt_type, Packet, PacketKls, data = kls.get_packet_type(data, protocol_register)

        if PacketKls is None:
            if not unknown_ok:
                raise BadConversion("Unknown message type!", protocol=protocol, pkt_type=pkt_type)
            PacketKls = Packet

        return PacketKls.create(data).pack()


class MessagesMeta(type):
    """
    This metaclass puts ``by_type`` on the created class.

    This is a dictionary of {pkt_type: kls} where we get pkt_type from the
    ``kls.Payload.message_type`` where kls is each message defined on the class.

    As a bonus, this puts ``caller_source`` on the ``Meta`` of each message which
    is the lines that make up it's definition. This is used for ``photons-docs``.
    """

    def __new__(metaname, classname, baseclasses, attrs):
        by_type = {}
        for attr, val in attrs.items():
            if getattr(val, "_lifx_packet_message", False):
                m = attrs[attr] = val(attr)
                if hasattr(m, "Payload") and hasattr(m.Payload, "message_type"):
                    by_type[m.Payload.message_type] = m
            elif hasattr(val, "Payload") and getattr(val.Payload, "message_type"):
                by_type[attrs[attr].Payload.message_type] = attrs[attr]

        if MessagesMixin not in baseclasses:
            baseclasses = baseclasses + (MessagesMixin,)

        attrs["by_type"] = by_type
        kls = type.__new__(metaname, classname, baseclasses, attrs)

        for attr, source in sources_for(kls):
            if attr in attrs:
                if not hasattr(attrs[attr].Meta, "caller_source"):
                    attrs[attr].Meta.caller_source = source

        return kls


class Messages(metaclass=MessagesMeta):
    pass
