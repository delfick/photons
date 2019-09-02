# coding: spec

from photons_messages import Services, DiscoveryMessages, protocol_register

from photons_app.registers import ProtocolRegister
from photons_app.test_helpers import TestCase

import binascii

describe TestCase, "DiscoveryMessages":
    it "can unpack":
        hexd = "29000014f7f15496d073d51261e200004c49465856320101e41ac32cece1d31403000000017cdd0000"

        unpackd = DiscoveryMessages.unpack(hexd, protocol_register=protocol_register)

        expected = DiscoveryMessages.StateService.empty_normalise(
            **{
                "frame_address": {
                    "ack_required": False,
                    "res_required": True,
                    "reserved2": "4c4946585632",
                    "reserved3": "00",
                    "sequence": 1,
                    "target": "d073d51261e20000",
                },
                "frame_header": {
                    "addressable": True,
                    "protocol": 1024,
                    "reserved1": "00",
                    "size": 41,
                    "source": 2522149367,
                    "tagged": False,
                },
                "payload": {"port": 56700, "service": Services.UDP},
                "protocol_header": {
                    "reserved4": "e41ac32cece1d314",
                    "pkt_type": 3,
                    "reserved5": "0000",
                },
            }
        )

        self.assertEqual(repr(unpackd), repr(expected))
        self.assertEqual(binascii.hexlify(expected.pack().tobytes()).decode(), hexd)
