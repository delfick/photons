# coding: spec

from photons_socket.messages import Services, DiscoveryMessages

from photons_app.registers import ProtocolRegister
from photons_app.test_helpers import TestCase

from photons_protocol.frame import LIFXPacket

import binascii

describe TestCase, "DiscoveryMessages":
    it "can unpack":
        protocol_register = ProtocolRegister()
        protocol_register.add(1024, LIFXPacket)
        protocol_register.message_register(1024).add(DiscoveryMessages)

        hexd = "29000014f7f15496d073d51261e200004c49465856320101e41ac32cece1d31403000000017cdd0000"

        unpackd = DiscoveryMessages.unpack(hexd, protocol_register = protocol_register)

        expected = DiscoveryMessages.StateService.empty_normalise(**{
                "frame_address":
                { "ack_required": False
                , "res_required": True
                , "reserved2": "4c4946585632"
                , "reserved3": "00"
                , "sequence": 1
                , "target": "d073d51261e20000"
                }
              , "frame_header":
                { "addressable": True
                , "protocol": 1024
                , "reserved1": "00"
                , "size": 41
                , "source": 2522149367
                , "tagged": False
                }
              , "payload":
                { "port": 56700
                , "service": Services.UDP
                }
              , "protocol_header":
                { "reserved4": 1500791505324022500
                , "pkt_type": 3
                , "reserved5": "0000"
                }
              }
            )

        self.assertEqual(repr(unpackd), repr(expected))
        self.assertEqual(binascii.hexlify(expected.pack().tobytes()).decode(), hexd)
