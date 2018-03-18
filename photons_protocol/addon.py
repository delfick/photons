from photons_protocol.messages import Messages
from photons_protocol.frame import LIFXPacket
from photons_app.actions import an_action

from option_merge_addons import option_merge_addon_hook
import binascii

__shortdesc__ = "The underlying core of the Photons Protocol interface"

@option_merge_addon_hook(post_register=True)
def __lifx__(collector, **kwargs):
    collector.configuration["protocol_register"].add(1024, LIFXPacket)
    collector.configuration["protocol_register"].message_register(1024).add(Messages)

@an_action()
async def pack(collector, **kwargs):
    """
    Pack json found after the ``--`` into hexlified string

    For example ``pack -- '{"frame_address": {"ack_required": true, "res_required": true, "reserved2": "000000000000", "reserved3": "00", "sequence": 1, "target": "0000000000000000"}, "frame_header": {"addressable": true, "protocol": 1024, "reserved1": "00", "size": 68, "source": 591976603, "tagged": false}, "payload": {}, "protocol_header": {"pkt_type": 45, "reserved4": "0000000000000000", "reserved5": "0000"}}'``
    """
    extra = collector.configuration["photons_app"].extra_as_json
    if "extra_payload_kwargs" in kwargs:
        extra.update(kwargs["extra_payload_kwargs"])
    print(binascii.hexlify(Messages.pack(extra, collector.configuration["protocol_register"], unknown_ok=True).tobytes()).decode())

@an_action()
async def pack_payload(collector, reference, **kwargs):
    """
    Pack json found after the ``--`` into hexlified string

    for example ``pack_payload 117 -- '{"level": 65535, "duration": 10}'``
    """
    extra = collector.configuration["photons_app"].extra_as_json
    if "extra_payload_kwargs" in kwargs:
        extra.update(kwargs["extra_payload_kwargs"])
    print(binascii.hexlify(Messages.pack_payload(reference, extra, collector.configuration["protocol_register"][1024][1]).tobytes()).decode())

@an_action()
async def unpack(collector, **kwargs):
    """
    Unpack hexlified string found after the ``--`` into a json dictionary

    for example ``unpack -- 310000148205ed33d073d51261e20000000000000000030100000000000000006600000000f4690000ffffac0d00000000``
    """
    bts = binascii.unhexlify(collector.configuration["photons_app"].extra)
    pkt = Messages.unpack(bts, collector.configuration["protocol_register"], unknown_ok=True)
    print(repr(pkt))
