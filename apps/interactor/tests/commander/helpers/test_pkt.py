# coding: spec

from interactor.commander.errors import NoSuchPacket
from interactor.commander import helpers as ihp

from photons_messages import DeviceMessages, LightMessages


from delfick_project.errors_pytest import assertRaises
from unittest import mock
import pytest

describe "find_packet":

    it "can find a packet based on pkt_type integer":
        assert ihp.find_packet(23) is DeviceMessages.GetLabel
        assert ihp.find_packet(116) is LightMessages.GetLightPower

    it "can find a packet based on pkt_type name":
        assert ihp.find_packet("GetLabel") is DeviceMessages.GetLabel
        assert ihp.find_packet("StatePower") is DeviceMessages.StatePower

    it "complains if we can't find the packet":
        with assertRaises(NoSuchPacket, wanted="GetWat"):
            ihp.find_packet("GetWat")

        with assertRaises(NoSuchPacket, wanted=9001):
            ihp.find_packet(9001)

describe "make_message":
    it "instantiates the kls without args if no pkt_args":
        pkt_type = mock.Mock(name="pkt_type")

        find_packet = mock.Mock(name="find_packet", return_value=DeviceMessages.GetPower)
        with mock.patch("interactor.commander.helpers.find_packet", find_packet):
            pkt = ihp.make_message(pkt_type, {})

        assert isinstance(pkt, DeviceMessages.GetPower)
        find_packet.assert_called_once_with(pkt_type)

    it "instantiates the kls with args if have pkt_args":
        pkt_type = mock.Mock(name="pkt_type")

        find_packet = mock.Mock(name="find_packet", return_value=LightMessages.SetLightPower)
        with mock.patch("interactor.commander.helpers.find_packet", find_packet):
            pkt = ihp.make_message(pkt_type, {"level": 65535, "duration": 10})

        assert isinstance(pkt, LightMessages.SetLightPower)
        assert pkt.payload.as_dict() == {"level": 65535, "duration": 10}
        find_packet.assert_called_once_with(pkt_type)
