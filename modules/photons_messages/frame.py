import binascii

from bitarray import bitarray
from delfick_project.norms import sb
from photons_protocol.messages import T
from photons_protocol.packets import dictobj

emptybt = bitarray("0000000000000000000000000000000000000000000000000000000000000000")
target_cache = {}


def look_at_target(pkt, value):
    if value in (None, "0000000000000000", b"\x00" * 8, emptybt):
        pkt.addressable = True
        pkt.tagged = True
    else:
        pkt.tagged = False

    return value


class FrameHeader(dictobj.PacketSpec):
    fields = [
        ("size", T.Uint16.default(lambda pkt: int(pkt.size_bits(pkt) / 8))),
        ("protocol", T.Uint16.S(12).default(1024)),
        ("addressable", T.Bool.default(lambda pkt: True)),
        (
            "tagged",
            T.Bool.default(lambda pkt: pkt.actual("target") in (None, b"\x00" * 8, emptybt)),
        ),
        ("reserved1", T.Reserved(2, left=True)),
        ("source", T.Uint32),
    ]


class FrameAddress(dictobj.PacketSpec):
    fields = [
        ("target", T.Bytes(64).transform(look_at_target, look_at_target)),
        ("reserved2", T.Reserved(48)),
        ("res_required", T.Bool.default(True)),
        ("ack_required", T.Bool.default(True)),
        ("reserved3", T.Reserved(6)),
        ("sequence", T.Uint8),
    ]


class ProtocolHeader(dictobj.PacketSpec):
    fields = [
        ("reserved4", T.Reserved(64)),
        ("pkt_type", T.Uint16.default(lambda pkt: pkt.Payload.message_type)),
        ("reserved5", T.Reserved(16)),
    ]


class LIFXPacket(dictobj.PacketSpec):
    """
    The LIFXPacket represents protocol 1024.

    It can be used to generate payload messages for this protocol.

    This is the ``parent_packet`` for this protocol. This means
    any message can be represented with this class using a payload as
    ``bytes``. Specific message classes will represent the payload as a
    dictionary of data.
    """

    parent_packet = True

    fields = [
        ("frame_header", FrameHeader),
        ("frame_address", FrameAddress),
        ("protocol_header", ProtocolHeader),
        ("payload", "Payload"),
    ]

    @property
    def Key(self):
        key = self.__dict__.get("Key", None)
        if key is None:
            key = (self.protocol, self.pkt_type, repr(self.payload))
            self.__dict__["Key"] = key
        return key

    @Key.deleter
    def Key(self):
        if "Key" in self.__dict__:
            del self.__dict__["Key"]

    @property
    def serial(self):
        target = self.target
        if target in (None, sb.NotSpecified):
            return None

        serial = target_cache.get(target)
        if serial is None:
            serial = target_cache[target] = binascii.hexlify(target[:6]).decode()

        return serial

    @property
    def represents_ack(self):
        return self.Payload.represents_ack

    def __or__(self, kls):
        """
        Determine if this object is of type ``kls``. It does this by looking at
        the ``protocol`` and ``message_type`` values on the ``kls.Payload`` and this
        instance and returning whether they are equal.
        """
        this_protocol = dictobj.__getitem__(self, "protocol")
        this_protocol = this_protocol if this_protocol is not sb.NotSpecified else self.protocol
        if this_protocol != kls.Payload.Meta.protocol:
            return False

        this_pkt_type = dictobj.__getitem__(self, "pkt_type")
        this_pkt_type = this_pkt_type if this_pkt_type is not sb.NotSpecified else self.pkt_type
        return this_pkt_type == kls.Payload.message_type

    @classmethod
    def message(kls, message_type, *payload_fields, multi=None):
        """
        This is to be used in conjunction with ``photons_protocol.messages.Messages``

        .. code-block:: python

            from photons_protocol.messages import Messages

            class MyMessages(Messages):
                MyMessage = LIFXPacket.message(13
                    , ("field_one", field_one_type)
                    , ("field_two", field_two_type)
                    )

        This method returns a function that when called will return a new class
        representing the message you are creating.

        You may also use the fields from an existing packet by doing something
        like:

        .. code-block:: python

            from photons_protocol.messages import Messages

            class MyMessages(Messages):
                MyMessage = LIFXPacket.message(13
                    , ("field_one", field_one_type)
                    , ("field_two", field_two_type)
                    )

                MyOtherMessage = MyMessage.using(14)

        Here, ``MyOtherMessage`` will use the same fields as ``MyMessage`` but
        will have a ``pkt_type`` of ``14`` instead of ``13``.

        And you can specify multiple replies options with the multi keyword:

        .. code-block:: python

            from photons_protocol.messages import Messages, MultiOptions

            class MyMessages(Messages):
                MyMessage = LIFXPacket.message(13
                    , ("field_one", field_one_type)
                    , ("field_two", field_two_type)

                    , multi = MultiOptions(
                          # expect MymessageReply messages
                          lambda req: MyMessages.MyMessageReply

                          # Use total on the reply packet to determine how many packets to receive
                        , lambda res: res.total
                        )
                    )

                MyMessage = LIFXPacket.message(14
                    , ("total", total_type)
                    )

        If you expect multiple replies but don't know how many to expect you can say:

        .. code-block:: python

            class MyMessages(Messages):
                MyMessage = LIFXPacket.message(13
                    , ("field_one", field_one_type)
                    , ("field_two", field_two_type)

                    , multi = -1
                    )
        """

        def maker(name):
            Payload = type(
                f"{name}Payload",
                (dictobj.PacketSpec,),
                {
                    "fields": list(payload_fields),
                    "message_type": message_type,
                    "represents_ack": message_type == 45,
                },
            )
            Payload.Meta.protocol = 1024
            Payload.Meta.multi = multi

            res = type(name, (LIFXPacket,), {"Payload": Payload, "parent_packet": False})
            res.Meta.parent = LIFXPacket
            res.Meta.multi = multi

            return res

        maker._lifx_packet_message = True
        maker.using = lambda mt, **kwargs: kls.message(mt, *payload_fields, **kwargs)
        return maker

    class Payload(dictobj.PacketSpec):
        message_type = 0
        fields = []


LIFXPacket.Meta.protocol = 1024
LIFXPacket.Payload.Meta.protocol = 1024

# Helper for creating messages
msg = LIFXPacket.message
