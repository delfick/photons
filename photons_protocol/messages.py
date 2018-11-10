"""
The messages system is essentially a collection system for all the Protocol
Payloads.

We create collections of messages by defining them as properties on a subclass
of ``photons_protocol.messages.Messages``.

This class is a combination of a mixin class for functionality and a meta class
for defining ``by_type`` on the class.

.. autoclass:: photons_protocol.messages.MessagesMeta

.. autoclass:: photons_protocol.messages.MessagesMixin
    :members:
"""
from photons_protocol.types import Type, MultiOptions
from photons_protocol.errors import BadConversion

from input_algorithms.spec_base import NotSpecified
from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta
from bitarray import bitarray
from textwrap import dedent
import binascii
import inspect
import logging
import struct

log = logging.getLogger("photons_protocol.messages")

T = Type
MultiOptions = MultiOptions

class MessagesMixin:
    """
    Functionality for a collection of Protocol Messages
    """
    @classmethod
    def get_message_type(kls, data, protocol_register):
        """
        Given a ProtocolRegister and some data (bytes or dictionary)
        return ``(pkt_type, Packet, kls, pkt)``

        pkt_type
            The number assigned to this payload type. This code assumes the
            unpacked data has a ``pkt_type`` property that is retrieved for this.

        Packet
            The ``parent_packet`` class for the protocol the data represents.

            If ``data`` is bytes, get the integer from bits 16 to 28 as protocol.

            Use this number in protocol register to find the ``parent_packet``.

        kls
            The payload class representing this protocol and pkt_type.

        pkt
            An instance of the ``parent_packet`` from the data.
        """
        if type(data) is str:
            data = binascii.unhexlify(data)

        if type(data) is bytes:
            b = bitarray(endian="little")
            b.frombytes(data)
            data = b

        protocol = struct.unpack("<H", data[16:16 + 12].tobytes())[0]

        prot = protocol_register.get(protocol)
        if prot is None:
            raise BadConversion("Unknown packet protocol", wanted=protocol, available=list(protocol_register))
        Packet, messages_register = prot

        pkt = Packet.unpack(data)
        message_type = dictobj.__getitem__(pkt, "pkt_type")

        k = None
        for k in (messages_register or [kls]):
            if message_type in k.by_type:
                if pkt.payload is NotSpecified and k.by_type[message_type].Payload.Meta.field_types:
                    raise BadConversion("packet had no payload", got=repr(pkt))
                break

        if k is None:
            return message_type, Packet, None, pkt
        return message_type, Packet, k.by_type.get(message_type), pkt

    @classmethod
    def unpack_pkt(kls, PacketKls, pkt):
        """
        Create a new instance of PacketKls and transfer values from pkt onto it

        Then unpack the payload on pkt and set on the new instance of PacketKls
        """
        result = PacketKls()
        for key, val in pkt.items():
            if key != "payload":
                dictobj.__setattr__(result, key, val)

        existing_payload = pkt.payload
        if existing_payload is not NotSpecified:
            result["payload"] = PacketKls.Payload.unpack(existing_payload)

        return result

    @classmethod
    def unpack(kls, data, protocol_register, unknown_ok=False):
        """
        Return a fully resolved packet instance from the data and protocol_register.

        unknown_ok
            Whether we return an instance of the parent_packet with unresolved
            payload if we don't have a payload class, or if we raise an error
        """
        message_type, Packet, PacketKls, pkt = kls.get_message_type(data, protocol_register)
        if PacketKls:
            return kls.unpack_pkt(PacketKls, pkt)
        elif unknown_ok:
            return pkt
        raise BadConversion("Unknown message type!", pkt_type=message_type)

    @classmethod
    def pack_payload(kls, message_type, data, messages_register=None):
        """
        Given some payload data as a dictionary and it's ``pkt_type``, return a
        hexlified string of the payload.
        """
        for k in (messages_register or [kls]):
            if int(message_type) in k.by_type:
                return k.by_type[int(message_type)].Payload.normalise(Meta.empty(), data).pack()
        raise BadConversion("Unknown message type!", pkt_type=message_type)

    @classmethod
    def pack(kls, data, protocol_register, unknown_ok=False):
        """
        Return a hexlified string of the data.

        This uses ``pkt_type`` and ``protocol`` in the data, along with the
        protocol_register to find the appropriate class to use to perform the
        packing.
        """
        if "pkt_type" in data:
            message_type = data["pkt_type"]
        elif "pkt_type" in data.get("protocol_header", {}):
            message_type = data["protocol_header"]["pkt_type"]
        else:
            raise BadConversion("Don't know how to pack this dictionary, it doesn't specify a pkt_type!")

        if "protocol" in data:
            protocol = data["protocol"]
        elif "frame_header" in data and "protocol" in data["frame_header"]:
            protocol = data["frame_header"]["protocol"]
        else:
            raise BadConversion("Don't know how to pack this dictionary, it doesn't specify a protocol!")

        prot = protocol_register.get(protocol)
        if prot is None:
            raise BadConversion("Unknown packet protocol", wanted=protocol, available=list(protocol_register))
        Packet, messages_register = prot

        for k in (messages_register or [kls]):
            if message_type in k.by_type:
                return k.by_type[message_type].normalise(Meta.empty(), data).pack()
        if unknown_ok:
            return Packet.normalise(Meta.empty(), data).pack()
        raise BadConversion("Unknown message type!", pkt_type=message_type)

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
            baseclasses = baseclasses + (MessagesMixin, )

        attrs["by_type"] = by_type
        kls = type.__new__(metaname, classname, baseclasses, attrs)

        buf = []
        in_kls = None

        try:
            src = inspect.getsource(kls)
        except OSError as error:
            if error.args and error.args[0] == "could not find class definition":
                log.warning("Couldn't find source code for kls\tkls={0}".format(kls))
            else:
                raise
        else:
            for line in src.split('\n'):
                attr = line[:line.find('=')].replace(' ', '')
                if attr and attr[0].isupper() and attr in attrs:
                    if buf and in_kls:
                        if not hasattr(attrs[in_kls].Meta, "caller_source"):
                            attrs[in_kls].Meta.caller_source = dedent("\n".join(buf))
                    buf = []
                    in_kls = attr

                if not line.strip().startswith("#"):
                    buf.append(line)

            if buf and in_kls:
                if not hasattr(attrs[in_kls].Meta, "caller_source"):
                    attrs[in_kls].Meta.caller_source = dedent("\n".join(buf))

        return kls

class Messages(metaclass=MessagesMeta):
    pass
