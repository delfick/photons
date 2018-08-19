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

from photons_app.errors import ProgrammerError

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

class MultiOptions:
    def __init__(self, determine_res_packet, adjust_expected_number):
        if not callable(determine_res_packet) or not callable(adjust_expected_number):
            raise ProgrammerError("Multi Options expects two callables")

        self.determine_res_packet = determine_res_packet
        self.adjust_expected_number = adjust_expected_number

    class Max:
        """
        A callable that returns -1 if num_results is less than our value

        or num_results if it is larger than our value.
        """
        def __init__(self, value):
            self.value = value

        def __call__(self, results):
            num_results = len(results)
            if num_results >= self.value:
                return num_results
            return -1

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
                  "{0}Payload".format(name)
                , (dictobj.PacketSpec, )
                , { "fields": list(payload_fields)
                  , "message_type": message_type
                  , "represents_ack": message_type == 45
                  }
                )
            Payload.Meta.protocol = 1024
            Payload.Meta.multi = multi

            res = type(name, (LIFXPacket, ), {"Payload": Payload, "parent_packet": False})
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
