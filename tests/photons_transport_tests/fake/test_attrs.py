# coding: spec

from photons_transport.fake import Attrs

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import pytest

describe "Attrs":

    @pytest.fixture()
    def device(self):
        return mock.Mock(name="device")

    @pytest.fixture()
    def attrs(self, device):
        return Attrs(device)

    it "takes in a device", device, attrs:
        assert attrs._attrs == {}
        assert attrs._device is device

    it "can use dictionary syntax", device, attrs:
        val = mock.Mock(name="val")
        key = mock.Mock(name="key")
        attrs[key] = val
        device.validate_attr.assert_called_once_with(key, val)
        assert attrs[key] is val

        device.validate_attr.reset_mock()
        val2 = mock.Mock(name="val")
        key2 = mock.Mock(name="key")
        attrs[key2] = val2
        device.validate_attr.assert_called_once_with(key2, val2)
        assert attrs[key] is val
        assert attrs[key2] is val2

    it "can use object syntax", device, attrs:
        val = mock.Mock(name="val")
        attrs.wat = val
        device.validate_attr.assert_called_once_with("wat", val)
        assert attrs.wat is val

        device.validate_attr.reset_mock()
        val2 = mock.Mock(name="val")
        attrs.wat2 = val2
        device.validate_attr.assert_called_once_with("wat2", val2)
        assert attrs.wat is val
        assert attrs.wat2 is val2

    it "doesn't set key if validate_attr raises an error", device, attrs:
        assert attrs._attrs == {}

        attrs.wat = 2
        attrs["things"] = 3
        expected = {"wat": 2, "things": 3}
        assert attrs._attrs == expected

        device.validate_attr.side_effect = ValueError("NOPE")

        with assertRaises(ValueError, "NOPE"):
            attrs.nope = 2

        with assertRaises(AttributeError):
            attrs.nope

        with assertRaises(ValueError, "NOPE"):
            attrs["hello"] = 3

        with assertRaises(KeyError):
            attrs["hello"]
