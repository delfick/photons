# coding: spec

from photons_transport.fake import pktkeys

from photons_messages import DeviceMessages, MultiZoneMessages

from delfick_project.norms import sb
from unittest import mock
import json


describe "pktkeys":
    it "can get us deduped keys to represent the packets":
        msg1 = DeviceMessages.SetPower(level=65535, source=1, sequence=2, target="d073d501")
        msg2 = DeviceMessages.SetLabel(label="bob", source=3, sequence=4, target="d073d502")
        msg3 = DeviceMessages.SetLabel(label="bob", source=5, sequence=6, target="d073d503")
        keys = pktkeys([msg1, msg2, msg3])

        assert keys == [(1024, 21, '{"level": 65535}'), (1024, 24, '{"label": "bob"}')]

    it "can be told to keep duplicates":
        msg1 = DeviceMessages.SetPower(level=65535, source=1, sequence=2, target="d073d501")
        msg2 = DeviceMessages.SetLabel(label="bob", source=3, sequence=4, target="d073d502")
        msg3 = DeviceMessages.SetLabel(label="bob", source=5, sequence=6, target="d073d503")
        keys = pktkeys([msg1, msg2, msg3], keep_duplicates=True)

        assert keys == [
            (1024, 21, '{"level": 65535}'),
            (1024, 24, '{"label": "bob"}'),
            (1024, 24, '{"label": "bob"}'),
        ]

    it "knows to zero instanceid":
        msg = MultiZoneMessages.SetMultiZoneEffect.create(
            source=1, sequence=2, target="d073d511", reserved6=b"hell", parameters={}
        )

        assert msg.instanceid > 0

        keys = pktkeys([msg])
        assert keys == [(1024, 508, mock.ANY)]

        dct = json.loads(keys[0][-1])
        assert dct["instanceid"] == 0
        assert msg.instanceid > 0

    it "knows to zero reserved fields":
        from photons_protocol.messages import T, Messages
        from photons_messages.frame import msg

        class Messages(Messages):
            SetExample = msg(9001, ("one", T.Reserved(6)), ("two", T.String(10)))

        msg = Messages.SetExample(source=1, sequence=2, target="d073d512", two="stuff")
        assert msg.actual("one") == sb.NotSpecified

        keys = pktkeys([msg])

        assert keys == [(1024, 9001, '{"one": "00", "two": "stuff"}')]

        assert msg.actual("one") == sb.NotSpecified
        assert (
            repr(msg.payload)
            == """{"one": "<class 'delfick_project.norms.spec_base.NotSpecified'>", "two": "stuff"}"""
        )
