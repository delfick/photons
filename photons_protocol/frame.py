"""
The LIFXPacket is made up of the following:

frame_header
    .. code_for:: photons_protocol.frame.FrameHeader

frame_address
    .. code_for:: photons_protocol.frame.FrameAddress

protocol_header
    .. code_for:: photons_protocol.frame.ProtocolHeader

payload
    As determined by each payload type
"""
from photons_protocol.types import Type as T
from photons_protocol.packets import dictobj

from input_algorithms import spec_base as sb
import binascii

class FrameHeader(dictobj.PacketSpec):
    fields = [
          ("size", T.Uint16.default(lambda pkt: int(pkt.size_bits(pkt) / 8)))
        , ("protocol", T.Uint16.S(12).default(1024))
        , ("addressable", T.Bool.default(lambda pkt: False if getattr(pkt, "target", None) is None else True))
        , ("tagged", T.Bool.default(lambda pkt: True if getattr(pkt, "target", None) is None else False))
        , ("reserved1", T.Reserved(2, left=True))
        , ("source", T.Uint32)
        ]

class FrameAddress(dictobj.PacketSpec):
    fields = [
          ("target", T.Bytes(64))
        , ("reserved2", T.Reserved(48))
        , ("res_required", T.Bool.default(True))
        , ("ack_required", T.Bool.default(True))
        , ("reserved3", T.Reserved(6))
        , ("sequence", T.Uint8)
        ]

class ProtocolHeader(dictobj.PacketSpec):
    fields = [
          ('reserved4', T.Uint64.default(0))
        , ('pkt_type', T.Uint16.default(lambda pkt: pkt.Payload.message_type))
        , ('reserved5', T.Reserved(16))
        ]

class LIFXPacket(dictobj.PacketSpec):
    """
    The LIFXPacket represents protocol 1024.

    It can be used to generate payload messages for this protocol.

    .. note:: This is the ``parent_packet`` for this protocol. This means
        any message can be represented with this class using a payload as
        ``bytes``. Specific message classes will represent the payload as a
        dictionary of data.

    .. automethod:: photons_protocol.frame.LIFXPacket.message
    """
    parent_packet = True

    fields = [
          ("frame_header", FrameHeader)
        , ("frame_address", FrameAddress)
        , ("protocol_header", ProtocolHeader)
        , ("payload", "Payload")
        ]

    @property
    def serial(self):
        target = self.target
        if target in (None, sb.NotSpecified):
            return None
        return binascii.hexlify(target[:6]).decode()

    @property
    def represents_ack(self):
        return self.Payload.represents_ack

    @classmethod
    def message(kls, message_type, *payload_fields):
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
        """
        def maker(name):
            Payload = type(
                  "{0}Payload".format(name)
                , (dictobj.PacketSpec, )
                , { "fields": list(payload_fields)
                  , "message_type": message_type
                  , "represents_ack": message_type == 45
                  }
                )
            Payload.Meta.protocol = 1024
            res = type(name, (LIFXPacket, ), {"Payload": Payload, "parent_packet": False})
            res.Meta.parent = LIFXPacket
            return res
        maker._lifx_packet_message = True
        maker.using = lambda mt, **kwargs: kls.message(mt, *payload_fields, **kwargs)
        return maker

    class Payload(dictobj.PacketSpec):
        message_type = 0
        fields = []
LIFXPacket.Meta.protocol = 1024
LIFXPacket.Payload.Meta.protocol = 1024
