# coding: spec

from photons_device_finder import Device, Collection, Collections, Filter, InfoPoints

from photons_app.test_helpers import TestCase

from photons_device_messages import DeviceMessages
from photons_products_registry import Capability
from photons_colour import ColourMessages

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms import spec_base as sb
import uuid
import mock

describe TestCase, "Device":
    before_each:
        self.device = Device.FieldSpec().empty_normalise(serial="d073d5000001")

    it "has property_fields":
        self.assertEqual(self.device.property_fields, ["group_id", "group_name", "location_name", "location_id"])
        for field in self.device.property_fields:
            self.assertEqual(getattr(self.device, field), sb.NotSpecified)

        self.device.group = Collection.FieldSpec().empty_normalise(typ="group", uuid="uuidg", name="blah")
        self.device.location = Collection.FieldSpec().empty_normalise(typ="location", uuid="uuidl", name="meh")

        self.assertEqual(self.device.group_id, "uuidg")
        self.assertEqual(self.device.group_name, "blah")

        self.assertEqual(self.device.location_id, "uuidl")
        self.assertEqual(self.device.location_name, "meh")

    it "modifies as_dict to have the property_fields instead of group and location":
        self.device.label = "kitchen"
        self.device.power = "on"
        self.device.group = Collection.FieldSpec().empty_normalise(typ="group", uuid="uuidg", name="blah")
        self.device.location = Collection.FieldSpec().empty_normalise(typ="location", uuid="uuidl", name="meh")
        self.device.hue = 20
        self.device.saturation = 0.5
        self.device.brightness = 0.6
        self.device.kelvin = 2500
        self.device.firmware_version = 1.2
        self.device.product_id = 22
        self.device.product_identifier = "color_a19"
        self.device.cap = ["multizone", "color"]

        self.assertEqual(self.device.as_dict()
            , { "serial": "d073d5000001"
              , "label": "kitchen"
              , "power": "on"
              , "group_id": "uuidg"
              , "group_name": "blah"
              , "location_id": "uuidl"
              , "location_name": "meh"
              , "hue": 20
              , "saturation": 0.5
              , "brightness": 0.6
              , "kelvin": 2500
              , "firmware_version": 1.2
              , "product_id": 22
              , "product_identifier": "color_a19"
              , 'cap': ["multizone", "color"]
              }
            )

    describe "matches":
        it "says yes if the filter matches all":
            self.device.label = "kitchen"
            self.device.power = "on"
            filtr = Filter.empty()
            assert filtr.matches_all
            assert self.device.matches(filtr)

        it "says yes if the filter matches all and device has no fields":
            filtr = Filter.empty()
            assert filtr.matches_all
            assert self.device.matches(filtr)

        it "says no if the filtr does not match":
            filtr = Filter.from_kwargs(label="bathroom")
            self.device.label = "kitchen"
            assert not self.device.matches(filtr)

        it "says no if the device has nothing on it":
            filtr = Filter.from_kwargs(label="bathroom")
            assert not self.device.matches(filtr)

        it "says yes if the filtr matches":
            filtr = mock.Mock(name="filtr", matches_all=False)
            filtr.matches.return_value = True

            def has(field):
                return field not in ("group", "location")
            filtr.has.side_effect = has

            self.device.label = "kitchen"
            self.device.power = "on"
            self.device.product_id = 22
            self.device.group = Collection.FieldSpec().empty_normalise(typ="group", uuid="uuidg", name="blah")

            assert self.device.matches(filtr)

            self.assertEqual(sorted(filtr.has.mock_calls)
                , sorted([
                      mock.call("label")
                    , mock.call("power")
                    , mock.call("product_id")
                    , mock.call("group")
                    , mock.call("group_id")
                    , mock.call("group_name")
                    , mock.call("serial")
                    ]
                  )
                )

            self.assertEqual(sorted(filtr.matches.mock_calls)
                , sorted([
                      mock.call("label", "kitchen")
                    , mock.call("power", "on")
                    , mock.call("product_id", 22)
                    , mock.call("group_id", "uuidg")
                    , mock.call("group_name", "blah")
                    , mock.call("serial", "d073d5000001")
                    ]
                  )
                )

    describe "set_from_pkt":
        before_each:
            self.collections = Collections()

        it "can take in a LightState":
            pkt = ColourMessages.LightState.empty_normalise(
                  label = "kitchen"
                , power = 0
                , hue = 250
                , saturation = 0.6
                , brightness = 0.7
                , kelvin = 4500
                )

            self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.LIGHT_STATE)

            self.assertEqual(self.device.label, "kitchen")
            self.assertEqual(self.device.power, "off")
            self.assertEqual(self.device.hue, pkt.hue)
            self.assertEqual(self.device.saturation, pkt.saturation)
            self.assertEqual(self.device.brightness, pkt.brightness)
            self.assertEqual(self.device.kelvin, 4500)

            # And test when power is on
            pkt = ColourMessages.LightState.empty_normalise(
                  label = "kitchen"
                , power = 65535
                , hue = 250
                , saturation = 0.6
                , brightness = 0.7
                , kelvin = 4500
                )
            self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.LIGHT_STATE)
            self.assertEqual(self.device.power, "on")

        it "can take in StateGroup":
            group_uuid = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateGroup.empty_normalise(
                  group = group_uuid
                , updated_at = 1
                , label = "group1"
                )

            self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.GROUP)
            self.assertEqual(self.device.group, self.collections.collections["group"][group_uuid])
            self.assertEqual(self.device.group_id, group_uuid)
            self.assertEqual(self.device.group_name, "group1")

            group = self.device.group

            pkt = DeviceMessages.StateGroup.empty_normalise(
                  group = group_uuid
                , updated_at = 2
                , label = "group1renamed"
                )

            self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.GROUP)
            self.assertEqual(self.device.group, self.collections.collections["group"][group_uuid])
            self.assertIs(self.device.group, group)
            self.assertEqual(self.device.group_id, group_uuid)
            self.assertEqual(self.device.group_name, "group1renamed")

            group_uuid2 = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateGroup.empty_normalise(
                  group = group_uuid2
                , updated_at = 2
                , label = "group2"
                )

            self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.GROUP)
            self.assertEqual(self.device.group, self.collections.collections["group"][group_uuid2])
            self.assertIsNot(self.device.group, group)
            self.assertEqual(self.device.group_id, group_uuid2)
            self.assertEqual(self.device.group_name, "group2")

            assert group_uuid in self.collections.collections["group"]
            assert group_uuid2 in self.collections.collections["group"]

        it "can take in StateLocation":
            location_uuid = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateLocation.empty_normalise(
                  location = location_uuid
                , updated_at = 1
                , label = "location1"
                )

            self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.LOCATION)
            self.assertEqual(self.device.location, self.collections.collections["location"][location_uuid])
            self.assertEqual(self.device.location_id, location_uuid)
            self.assertEqual(self.device.location_name, "location1")

            location = self.device.location

            pkt = DeviceMessages.StateLocation.empty_normalise(
                  location = location_uuid
                , updated_at = 2
                , label = "location1renamed"
                )

            self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.LOCATION)
            self.assertEqual(self.device.location, self.collections.collections["location"][location_uuid])
            self.assertIs(self.device.location, location)
            self.assertEqual(self.device.location_id, location_uuid)
            self.assertEqual(self.device.location_name, "location1renamed")

            location_uuid2 = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateLocation.empty_normalise(
                  location = location_uuid2
                , updated_at = 2
                , label = "location2"
                )

            self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.LOCATION)
            self.assertEqual(self.device.location, self.collections.collections["location"][location_uuid2])
            self.assertIsNot(self.device.location, location)
            self.assertEqual(self.device.location_id, location_uuid2)
            self.assertEqual(self.device.location_name, "location2")

            assert location_uuid in self.collections.collections["location"]
            assert location_uuid2 in self.collections.collections["location"]

        it "takes in StateHostFirmware":
            pkt = DeviceMessages.StateHostFirmware.empty_normalise(version=1.22)
            self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.FIRMWARE)
            self.assertEqual(self.device.firmware_version, 1.22)

        it "takes in StateVersion":
            pkt = DeviceMessages.StateVersion.empty_normalise(vendor=1, product=22)
            capability = Capability.FieldSpec().empty_normalise(name="A19", company="lifx", identifier="lifx_product_a19")
            capability_for_ids = mock.Mock(name="capability_for_ids", return_value=capability)

            with mock.patch("photons_device_finder.capability_for_ids", capability_for_ids):
                self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.VERSION)

            self.assertEqual(self.device.product_id, 22)
            self.assertEqual(self.device.product_identifier, "lifx_product_a19")
            self.assertEqual(self.device.cap, ["color", "not_chain", "not_ir", "not_multizone", "variable_color_temp"])

            capability_for_ids.assert_called_once_with(22, 1)

        it "knows about all the capabilities":
            pkt = DeviceMessages.StateVersion.empty_normalise(vendor=1, product=22)
            capability = Capability.FieldSpec().empty_normalise(name="A19", company="lifx", identifier="lifx_product_a19"
                , has_color=True, has_ir=True, has_multizone=True, has_chain=True, has_variable_color_temp=True
                )
            capability_for_ids = mock.Mock(name="capability_for_ids", return_value=capability)

            with mock.patch("photons_device_finder.capability_for_ids", capability_for_ids):
                self.assertIs(self.device.set_from_pkt(pkt, self.collections), InfoPoints.VERSION)

            self.assertEqual(self.device.cap, ["chain", "color", "ir", "multizone", "variable_color_temp"])
