# coding: spec

from photons_messages import Services, DiscoveryMessages, protocol_register

from photons_app.test_helpers import print_packet_difference

import binascii

describe "DiscoveryMessages":
    it "can unpack":
        hexd = "29000014f7f15496d073d51261e200004c49465856320101000000000000000003000000017cdd0000"

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
                "protocol_header": {"pkt_type": 3},
            }
        )

        different = print_packet_difference(unpackd, expected)
        assert not different

        assert binascii.hexlify(expected.pack().tobytes()).decode() == hexd
