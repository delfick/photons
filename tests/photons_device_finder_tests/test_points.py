# coding: spec

from photons_device_finder import Point, InfoPoints, Device, Filter

from photons_app.test_helpers import TestCase

from photons_messages import LIFXPacket

from unittest import mock

describe TestCase, "Point":
    it "takes in msg and keys":
        msg = mock.Mock(name="msg")
        keys = mock.Mock(name="keys")
        point = Point(msg, keys)

        self.assertIs(point.msg, msg)
        self.assertIs(point.keys, keys)

describe TestCase, "InfoPoints":
    it "has points":
        self.assertEqual(len(InfoPoints), 5)
        device = Device.FieldSpec().empty_normalise(serial="d073d5000001")
        for e in InfoPoints:
            self.assertEqual(type(e.value), Point)
            self.assertEqual(type(e.value.keys), list)

            assert isinstance(e.value.msg, LIFXPacket), e.value.msg
            assert all(type(k) is str for k in e.value.keys), e.value.keys

            for k in e.value.keys:
                assert (
                    k in Device.fields or k in device.property_fields
                ), "Unknown Device field {}".format(k)
                assert k in Filter.fields, "Unknown Filter field {}".format(k)
