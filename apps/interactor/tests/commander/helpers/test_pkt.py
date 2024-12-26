from unittest import mock

from delfick_project.errors_pytest import assertRaises
from interactor.commander import helpers as ihp
from interactor.commander.errors import NoSuchPacket
from photons_messages import DeviceMessages, LightMessages


class TestFindPacket:
    def test_it_can_find_a_packet_based_on_pkt_type_integer(self):
        assert ihp.find_packet(23) is DeviceMessages.GetLabel
        assert ihp.find_packet(116) is LightMessages.GetLightPower

    def test_it_can_find_a_packet_based_on_pkt_type_name(self):
        assert ihp.find_packet("GetLabel") is DeviceMessages.GetLabel
        assert ihp.find_packet("StatePower") is DeviceMessages.StatePower

    def test_it_complains_if_we_cant_find_the_packet(self):
        with assertRaises(NoSuchPacket, wanted="GetWat"):
            ihp.find_packet("GetWat")

        with assertRaises(NoSuchPacket, wanted=9001):
            ihp.find_packet(9001)


class TestMakeMessage:
    def test_it_instantiates_the_kls_without_args_if_no_pkt_args(self):
        pkt_type = mock.Mock(name="pkt_type")

        find_packet = mock.Mock(name="find_packet", return_value=DeviceMessages.GetPower)
        with mock.patch("interactor.commander.helpers.find_packet", find_packet):
            pkt = ihp.make_message(pkt_type, {})

        assert isinstance(pkt, DeviceMessages.GetPower)
        find_packet.assert_called_once_with(pkt_type)

    def test_it_instantiates_the_kls_with_args_if_have_pkt_args(self):
        pkt_type = mock.Mock(name="pkt_type")

        find_packet = mock.Mock(name="find_packet", return_value=LightMessages.SetLightPower)
        with mock.patch("interactor.commander.helpers.find_packet", find_packet):
            pkt = ihp.make_message(pkt_type, {"level": 65535, "duration": 10})

        assert isinstance(pkt, LightMessages.SetLightPower)
        assert pkt.payload.as_dict() == {"level": 65535, "duration": 10}
        find_packet.assert_called_once_with(pkt_type)
