# coding: spec

from photons_transport.fake import WithDevices, pktkeys

from photons_app.test_helpers import TestCase, AsyncTestCase

from photons_messages import DeviceMessages, MultiZoneMessages, Direction

from delfick_project.norms import sb
from unittest import mock
import asynctest
import json

describe AsyncTestCase, "WithDevices":
    async it "is an asynchronous context manager for devices":
        device1 = mock.Mock(name="device1")
        device2 = mock.Mock(name="device2")
        devices = [device1, device2]

        for d in devices:
            d.start = asynctest.mock.CoroutineMock(name="start")
            d.finish = asynctest.mock.CoroutineMock(name="finish")

        async with WithDevices(devices):
            for d in devices:
                d.start.assert_called_once_with()
                self.assertEqual(len(d.finish.mock_calls), 0)

        for d in devices:
            d.finish.assert_called_once_with()

    async it "finishes even on error":
        device1 = mock.Mock(name="device1")
        device2 = mock.Mock(name="device2")
        devices = [device1, device2]

        for d in devices:
            d.start = asynctest.mock.CoroutineMock(name="start")
            d.finish = asynctest.mock.CoroutineMock(name="finish")

        with self.fuzzyAssertRaisesError(ValueError, "NOPE"):
            async with WithDevices(devices):
                for d in devices:
                    d.start.assert_called_once_with()
                    self.assertEqual(len(d.finish.mock_calls), 0)
                raise ValueError("NOPE")

        for d in devices:
            d.finish.assert_called_once_with()

describe TestCase, "pktkeys":
    it "can get us deduped keys to represent the packets":
        msg1 = DeviceMessages.SetPower(level=65535, source=1, sequence=2, target="d073d501")
        msg2 = DeviceMessages.SetLabel(label="bob", source=3, sequence=4, target="d073d502")
        msg3 = DeviceMessages.SetLabel(label="bob", source=5, sequence=6, target="d073d503")
        keys = pktkeys([msg1, msg2, msg3])

        self.assertEqual(keys, [(1024, 21, '{"level": 65535}'), (1024, 24, '{"label": "bob"}')])

    it "can be told to keep duplicates":
        msg1 = DeviceMessages.SetPower(level=65535, source=1, sequence=2, target="d073d501")
        msg2 = DeviceMessages.SetLabel(label="bob", source=3, sequence=4, target="d073d502")
        msg3 = DeviceMessages.SetLabel(label="bob", source=5, sequence=6, target="d073d503")
        keys = pktkeys([msg1, msg2, msg3], keep_duplicates=True)

        self.assertEqual(
            keys,
            [
                (1024, 21, '{"level": 65535}'),
                (1024, 24, '{"label": "bob"}'),
                (1024, 24, '{"label": "bob"}'),
            ],
        )

    it "knows to zero instanceid":
        msg = MultiZoneMessages.SetMultiZoneEffect.empty_normalise(
            source=1, sequence=2, target="d073d511", reserved6=b"hell", parameters={}
        )

        self.assertGreater(msg.instanceid, 0)

        keys = pktkeys([msg])

        reprd = {
            "duration": 0.0,
            "instanceid": 0,
            "parameters": {
                "parameter1": "00000000",
                "parameter2": "00000000",
                "parameter3": "00000000",
                "parameter4": "00000000",
                "parameter5": "00000000",
                "parameter6": "00000000",
                "parameter7": "00000000",
                "speed_direction": 0,
            },
            "reserved6": "6865",
            "reserved7": "00000000",
            "reserved8": "00000000",
            "speed": 5.0,
            "type": "<MultiZoneEffectType.MOVE: 1>",
        }

        self.assertEqual(keys, [(1024, 508, json.dumps(reprd))])
        self.assertGreater(msg.instanceid, 0)

    it "knows to zero reserved fields":
        from photons_protocol.messages import T, Messages
        from photons_messages.frame import msg

        class Messages(Messages):
            SetExample = msg(9001, ("one", T.Reserved(6)), ("two", T.String(10)))

        msg = Messages.SetExample(source=1, sequence=2, target="d073d512", two="stuff")
        self.assertEqual(msg.actual("one"), sb.NotSpecified)

        keys = pktkeys([msg])

        self.assertEqual(keys, [(1024, 9001, '{"one": "00", "two": "stuff"}')])

        self.assertEqual(msg.actual("one"), sb.NotSpecified)
        self.assertEqual(
            repr(msg.payload),
            """{"one": "<class 'delfick_project.norms.spec_base.NotSpecified'>", "two": "stuff"}""",
        )
