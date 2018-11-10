from photons_app.actions import an_action

from photons_protocol.messages import Messages

import binascii
import base64

@an_action()
async def pack(collector, **kwargs):
    """
    Pack json found after the ``--`` into hexlified string

    ``pack -- '{"frame_address": {"ack_required": true, "res_required": true, "reserved2": "000000000000", "reserved3": "00", "sequence": 1, "target": "0000000000000000"}, "frame_header": {"addressable": true, "protocol": 1024, "reserved1": "00", "size": 68, "source": 591976603, "tagged": false}, "payload": {}, "protocol_header": {"pkt_type": 45, "reserved4": "0000000000000000", "reserved5": "0000"}}'``
    """
    extra = collector.configuration["photons_app"].extra_as_json
    protocol_register = collector.configuration["protocol_register"]

    if "extra_payload_kwargs" in kwargs:
        extra.update(kwargs["extra_payload_kwargs"])

    packd = Messages.pack(extra, protocol_register, unknown_ok=True)
    print(binascii.hexlify(packd.tobytes()).decode())

@an_action()
async def pack_payload(collector, reference, **kwargs):
    """
    Pack json found after the ``--`` into hexlified string

    ``pack_payload 117 -- '{"level": 65535, "duration": 10}'``
    """
    extra = collector.configuration["photons_app"].extra_as_json
    protocol_register = collector.configuration["protocol_register"]
    message_register = protocol_register.message_register(1024)

    if "extra_payload_kwargs" in kwargs:
        extra.update(kwargs["extra_payload_kwargs"])

    packd = Messages.pack_payload(reference, extra, message_register)
    print(binascii.hexlify(packd.tobytes()).decode())

@an_action()
async def unpack(collector, **kwargs):
    """
    Unpack hexlified string found after the ``--`` into a json dictionary

    ``unpack -- 310000148205ed33d073d51261e20000000000000000030100000000000000006600000000f4690000ffffac0d00000000``
    """
    bts = binascii.unhexlify(collector.configuration["photons_app"].extra)
    pkt = Messages.unpack(bts, collector.configuration["protocol_register"], unknown_ok=True)
    print(repr(pkt))

@an_action()
async def unpack_base64(collector, **kwargs):
    """
    Unpack base64 string found after the ``--`` into a json dictionary

    ``unpack_base64 -- MQAAFIIF7TPQc9USYeIAAAAAAAAAAAMBAAAAAAAAAABmAAAAAPRpAAD//6wNAAAAAA==``
    """
    bts = base64.b64decode(collector.configuration["photons_app"].extra)
    pkt = Messages.unpack(bts, collector.configuration["protocol_register"], unknown_ok=True)
    print(repr(pkt))
