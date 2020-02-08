# coding: spec

from photons_device_finder import Device, Collection, Collections, Filter, InfoPoints

from photons_messages import DeviceMessages, LightMessages
from photons_products import Products

from delfick_project.norms import sb
from unittest import mock
import pytest
import uuid

describe "Device":

    @pytest.fixture()
    def device(self):
        return Device.FieldSpec().empty_normalise(serial="d073d5000001")

    it "has property_fields", device:
        assert device.property_fields == [
            "group_id",
            "group_name",
            "location_name",
            "location_id",
        ]
        for field in device.property_fields:
            assert getattr(device, field) == sb.NotSpecified

        device.group = Collection.FieldSpec().empty_normalise(
            typ="group", uuid="uuidg", name="blah"
        )
        device.location = Collection.FieldSpec().empty_normalise(
            typ="location", uuid="uuidl", name="meh"
        )

        assert device.group_id == "uuidg"
        assert device.group_name == "blah"

        assert device.location_id == "uuidl"
        assert device.location_name == "meh"

    it "modifies as_dict to have the property_fields instead of group and location", device:
        device.label = "kitchen"
        device.power = "on"
        device.group = Collection.FieldSpec().empty_normalise(
            typ="group", uuid="uuidg", name="blah"
        )
        device.location = Collection.FieldSpec().empty_normalise(
            typ="location", uuid="uuidl", name="meh"
        )
        device.hue = 20
        device.saturation = 0.5
        device.brightness = 0.6
        device.kelvin = 2500
        device.firmware_version = "1.2"
        device.product_id = 22
        device.product_identifier = "color_a19"
        device.cap = ["multizone", "color"]

        assert device.as_dict() == {
            "serial": "d073d5000001",
            "label": "kitchen",
            "power": "on",
            "group_id": "uuidg",
            "group_name": "blah",
            "location_id": "uuidl",
            "location_name": "meh",
            "hue": 20,
            "saturation": 0.5,
            "brightness": 0.6,
            "kelvin": 2500,
            "firmware_version": "1.2",
            "product_id": 22,
            "product_identifier": "color_a19",
            "cap": ["multizone", "color"],
        }

    describe "matches":
        it "says yes if the filter matches all", device:
            device.label = "kitchen"
            device.power = "on"
            filtr = Filter.empty()
            assert filtr.matches_all
            assert device.matches(filtr)

        it "says yes if the filter matches all and device has no fields", device:
            filtr = Filter.empty()
            assert filtr.matches_all
            assert device.matches(filtr)

        it "says no if the filtr does not match", device:
            filtr = Filter.from_kwargs(label="bathroom")
            device.label = "kitchen"
            assert not device.matches(filtr)

        it "says no if the device has nothing on it", device:
            filtr = Filter.from_kwargs(label="bathroom")
            assert not device.matches(filtr)

        it "says yes if the filtr matches", device:
            filtr = mock.Mock(name="filtr", matches_all=False)
            filtr.matches.return_value = True

            def has(field):
                return field not in ("group", "location")

            filtr.has.side_effect = has

            device.label = "kitchen"
            device.power = "on"
            device.product_id = 22
            device.group = Collection.FieldSpec().empty_normalise(
                typ="group", uuid="uuidg", name="blah"
            )

            assert device.matches(filtr)

            assert sorted(filtr.has.mock_calls) == (
                sorted(
                    [
                        mock.call("label"),
                        mock.call("power"),
                        mock.call("product_id"),
                        mock.call("group"),
                        mock.call("group_id"),
                        mock.call("group_name"),
                        mock.call("serial"),
                    ]
                )
            )

            assert sorted(filtr.matches.mock_calls) == (
                sorted(
                    [
                        mock.call("label", "kitchen"),
                        mock.call("power", "on"),
                        mock.call("product_id", 22),
                        mock.call("group_id", "uuidg"),
                        mock.call("group_name", "blah"),
                        mock.call("serial", "d073d5000001"),
                    ]
                )
            )

    describe "set_from_pkt":

        @pytest.fixture()
        def collections(self):
            return Collections()

        it "can take in a LightState", device, collections:
            pkt = LightMessages.LightState.empty_normalise(
                label="kitchen", power=0, hue=250, saturation=0.6, brightness=0.7, kelvin=4500
            )

            assert device.set_from_pkt(pkt, collections) is InfoPoints.LIGHT_STATE

            assert device.label == "kitchen"
            assert device.power == "off"
            assert device.hue == pkt.hue
            assert device.saturation == pkt.saturation
            assert device.brightness == pkt.brightness
            assert device.kelvin == 4500

            # And test when power is on
            pkt = LightMessages.LightState.empty_normalise(
                label="kitchen", power=65535, hue=250, saturation=0.6, brightness=0.7, kelvin=4500
            )
            assert device.set_from_pkt(pkt, collections) is InfoPoints.LIGHT_STATE
            assert device.power == "on"

        it "can take in StateGroup", device, collections:
            group_uuid = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateGroup.empty_normalise(
                group=group_uuid, updated_at=1, label="group1"
            )

            assert device.set_from_pkt(pkt, collections) is InfoPoints.GROUP
            assert device.group == collections.collections["group"][group_uuid]
            assert device.group_id == group_uuid
            assert device.group_name == "group1"

            group = device.group

            pkt = DeviceMessages.StateGroup.empty_normalise(
                group=group_uuid, updated_at=2, label="group1renamed"
            )

            assert device.set_from_pkt(pkt, collections) is InfoPoints.GROUP
            assert device.group == collections.collections["group"][group_uuid]
            assert device.group is group
            assert device.group_id == group_uuid
            assert device.group_name == "group1renamed"

            group_uuid2 = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateGroup.empty_normalise(
                group=group_uuid2, updated_at=2, label="group2"
            )

            assert device.set_from_pkt(pkt, collections) is InfoPoints.GROUP
            assert device.group == collections.collections["group"][group_uuid2]
            assert device.group is not group
            assert device.group_id == group_uuid2
            assert device.group_name == "group2"

            assert group_uuid in collections.collections["group"]
            assert group_uuid2 in collections.collections["group"]

        it "can take in StateLocation", device, collections:
            location_uuid = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateLocation.empty_normalise(
                location=location_uuid, updated_at=1, label="location1"
            )

            assert device.set_from_pkt(pkt, collections) is InfoPoints.LOCATION
            assert device.location == collections.collections["location"][location_uuid]
            assert device.location_id == location_uuid
            assert device.location_name == "location1"

            location = device.location

            pkt = DeviceMessages.StateLocation.empty_normalise(
                location=location_uuid, updated_at=2, label="location1renamed"
            )

            assert device.set_from_pkt(pkt, collections) is InfoPoints.LOCATION
            assert device.location == collections.collections["location"][location_uuid]
            assert device.location is location
            assert device.location_id == location_uuid
            assert device.location_name == "location1renamed"

            location_uuid2 = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateLocation.empty_normalise(
                location=location_uuid2, updated_at=2, label="location2"
            )

            assert device.set_from_pkt(pkt, collections) is InfoPoints.LOCATION
            assert device.location == collections.collections["location"][location_uuid2]
            assert device.location is not location
            assert device.location_id == location_uuid2
            assert device.location_name == "location2"

            assert location_uuid in collections.collections["location"]
            assert location_uuid2 in collections.collections["location"]

        it "takes in StateHostFirmware", device, collections:
            pkt = DeviceMessages.StateHostFirmware.empty_normalise(
                version_major=1, version_minor=20
            )
            assert device.set_from_pkt(pkt, collections) is InfoPoints.FIRMWARE
            assert device.firmware_version == "1.20"

        it "takes in StateVersion", device, collections:
            pkt = DeviceMessages.StateVersion.empty_normalise(vendor=1, product=22)

            assert device.set_from_pkt(pkt, collections) is InfoPoints.VERSION

            assert device.product_id == 22
            assert device.product_identifier == Products[1, 22].identifier
            assert device.cap == [
                "color",
                "not_chain",
                "not_ir",
                "not_matrix",
                "not_multizone",
                "variable_color_temp",
            ]
