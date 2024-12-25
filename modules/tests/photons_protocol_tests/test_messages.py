from unittest import mock

from photons_protocol.messages import Messages


class TestMessagesMeta:
    def test_it_calls_any_lifx_packet_message_attribute_with_the_name_and_put_onto_resulting_kls(
        self,
    ):
        omsg = mock.Mock(name="omsg")
        tmsg = mock.Mock(name="tmsg")

        one_msg = mock.Mock(name="one", _lifx_packet_message=True, return_value=omsg)
        two_msg = mock.Mock(name="two", _lifx_packet_message=True, return_value=tmsg)

        three_msg = mock.Mock(name="three", _lifx_packet_message=False)
        four_msg = mock.Mock(name="four", spec=[])

        class M(Messages):
            one = one_msg
            two = two_msg
            three = three_msg
            four = four_msg

        assert M.one is omsg
        assert M.two is tmsg
        assert M.three is three_msg
        assert M.four is four_msg

        one_msg.assert_called_once_with("one")
        two_msg.assert_called_once_with("two")

    def test_it_creates_a_by_type_record(self):
        omsg = mock.Mock(name="omsg")
        tmsg = mock.Mock(name="tmsg")

        one_msg = mock.Mock(name="one", _lifx_packet_message=True, return_value=omsg)
        two_msg = mock.Mock(name="two", _lifx_packet_message=True, return_value=tmsg)

        three_msg = mock.Mock(name="three", _lifx_packet_message=False)
        four_msg = mock.Mock(name="four", spec=[])

        class M(Messages):
            one = one_msg
            two = two_msg
            three = three_msg
            four = four_msg

        assert M.by_type == {
            omsg.Payload.message_type: omsg,
            tmsg.Payload.message_type: tmsg,
            three_msg.Payload.message_type: three_msg,
        }

    def test_it_has_the_MessagesMixin(self):

        class M(Messages):
            pass

        assert hasattr(M, "pack")
        assert hasattr(M, "create")
