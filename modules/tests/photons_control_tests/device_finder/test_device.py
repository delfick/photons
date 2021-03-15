# coding: spec

from photons_control.device_finder import Device, Collection, Collections, Filter, InfoPoints, Point

from photons_app import helpers as hp

from photons_messages import DeviceMessages, LightMessages

from delfick_project.norms import sb
from unittest import mock
import asyncio
import pytest
import enum
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

    it "has as_dict and info with modified values", device:
        values = {
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
            "cap": ["multizone", "color"],
        }

        info = {"serial": values["serial"]}
        expected = {key: sb.NotSpecified for key in values}
        expected["serial"] = values["serial"]

        def assertChange(field, value):
            setattr(device, field, value)

            for k in values:
                if k.startswith(field):
                    info[k] = values[k]
                    expected[k] = values[k]

            assert device.info == info
            assert device.as_dict() == expected

        assertChange("label", "kitchen")
        assertChange("power", "on")
        assertChange(
            "group", Collection.FieldSpec().empty_normalise(typ="group", uuid="uuidg", name="blah")
        )
        assertChange(
            "location",
            Collection.FieldSpec().empty_normalise(typ="location", uuid="uuidl", name="meh"),
        )
        assertChange("hue", 20)
        assertChange("saturation", 0.5)
        assertChange("brightness", 0.6)
        assertChange("kelvin", 2500)
        assertChange("firmware_version", "1.2")
        assertChange("product_id", 22)
        assertChange("cap", ["multizone", "color"])

        assert device.info == values
        assert device.as_dict() == values

    describe "matches_fltr":
        it "says yes if the filter matches all", device:
            device.label = "kitchen"
            device.power = "on"
            filtr = Filter.empty()
            assert filtr.matches_all
            assert device.matches_fltr(filtr)

        it "says yes if the filter matches all and device has no fields", device:
            filtr = Filter.empty()
            assert filtr.matches_all
            assert device.matches_fltr(filtr)

        it "says no if the filtr does not match", device:
            filtr = Filter.from_kwargs(label="bathroom")
            device.label = "kitchen"
            assert not device.matches_fltr(filtr)

        it "says no if the device has nothing on it", device:
            filtr = Filter.from_kwargs(label="bathroom")
            assert not device.matches_fltr(filtr)

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

            assert device.matches_fltr(filtr)

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
            pkt = LightMessages.LightState.create(
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
            pkt = LightMessages.LightState.create(
                label="kitchen", power=65535, hue=250, saturation=0.6, brightness=0.7, kelvin=4500
            )
            assert device.set_from_pkt(pkt, collections) is InfoPoints.LIGHT_STATE
            assert device.power == "on"

        it "can take in StateGroup", device, collections:
            group_uuid = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateGroup.create(group=group_uuid, updated_at=1, label="group1")

            assert device.set_from_pkt(pkt, collections) is InfoPoints.GROUP
            assert device.group == collections.collections["group"][group_uuid]
            assert device.group_id == group_uuid
            assert device.group_name == "group1"

            group = device.group

            pkt = DeviceMessages.StateGroup.create(
                group=group_uuid, updated_at=2, label="group1renamed"
            )

            assert device.set_from_pkt(pkt, collections) is InfoPoints.GROUP
            assert device.group == collections.collections["group"][group_uuid]
            assert device.group is group
            assert device.group_id == group_uuid
            assert device.group_name == "group1renamed"

            group_uuid2 = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateGroup.create(group=group_uuid2, updated_at=2, label="group2")

            assert device.set_from_pkt(pkt, collections) is InfoPoints.GROUP
            assert device.group == collections.collections["group"][group_uuid2]
            assert device.group is not group
            assert device.group_id == group_uuid2
            assert device.group_name == "group2"

            assert group_uuid in collections.collections["group"]
            assert group_uuid2 in collections.collections["group"]

        it "can take in StateLocation", device, collections:
            location_uuid = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateLocation.create(
                location=location_uuid, updated_at=1, label="location1"
            )

            assert device.set_from_pkt(pkt, collections) is InfoPoints.LOCATION
            assert device.location == collections.collections["location"][location_uuid]
            assert device.location_id == location_uuid
            assert device.location_name == "location1"

            location = device.location

            pkt = DeviceMessages.StateLocation.create(
                location=location_uuid, updated_at=2, label="location1renamed"
            )

            assert device.set_from_pkt(pkt, collections) is InfoPoints.LOCATION
            assert device.location == collections.collections["location"][location_uuid]
            assert device.location is location
            assert device.location_id == location_uuid
            assert device.location_name == "location1renamed"

            location_uuid2 = str(uuid.uuid1()).replace("-", "")
            pkt = DeviceMessages.StateLocation.create(
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
            pkt = DeviceMessages.StateHostFirmware.create(version_major=1, version_minor=20)
            assert device.set_from_pkt(pkt, collections) is InfoPoints.FIRMWARE
            assert device.firmware_version == "1.20"

        it "takes in StateVersion", device, collections:
            pkt = DeviceMessages.StateVersion.create(vendor=1, product=22)

            assert device.set_from_pkt(pkt, collections) is InfoPoints.VERSION

            assert device.product_id == 22
            assert device.cap == [
                "color",
                "not_buttons",
                "not_chain",
                "not_hev",
                "not_ir",
                "not_matrix",
                "not_multizone",
                "not_relays",
                "variable_color_temp",
            ]

    describe "points_from_fltr":

        @pytest.fixture()
        def RF(self):
            class RF:
                def __init__(s, done=False):
                    s.done = done

                def __eq__(s, other):
                    return isinstance(other, hp.ResettableFuture) and bool(other.done()) == s.done

                def __repr__(self):
                    return "<RESETTABLE_FUTURE>"

            return RF

        @pytest.fixture()
        def Points(self, device, RF):

            expect = {e: RF() for e in InfoPoints}
            expect[None] = RF()
            assert device.point_futures == expect

            class IP(enum.Enum):
                ONE = Point("msg1", ["attr1", "attr2", "attr3"], 10)
                TWO = Point("msg2", ["attr4"], None)
                THREE = Point("msg3", ["attr5", "attr6"], 300)

            device.point_futures = {e: hp.ResettableFuture() for e in IP}
            device.point_futures[None] = hp.ResettableFuture()

            with mock.patch("photons_control.device_finder.InfoPoints", IP):
                yield IP

        @pytest.fixture()
        def Fltr(self):
            class Fltr:
                def __init__(s, *fields, refresh_info=False):
                    s.fields = fields
                    s.matches_all = not any(fields)
                    s.refresh_info = refresh_info

                def has(s, field):
                    return field in s.fields

            return Fltr

        it "returns all the InfoPoints for an empty fltr", device:
            assert list(device.points_from_fltr(Filter.empty())) == list(InfoPoints)

        it "only yields points if one of it's keys are on the fltr", device, Points, Fltr:
            for f in device.point_futures.values():
                f.set_result(True)

            fltr = Fltr("attr1", "attr6")
            assert list(device.points_from_fltr(fltr)) == [Points.ONE, Points.THREE]
            assert all(f.done() for f in device.point_futures.values())

            fltr = Fltr("attr4")
            assert list(device.points_from_fltr(fltr)) == [Points.TWO]
            assert all(f.done() for f in device.point_futures.values())

        it "resets futures if we have a refresh_info and a refresh amount", device, Points, Fltr, RF:
            for f in device.point_futures.values():
                f.set_result(True)

            fltr = Fltr("attr1", "attr6", "attr4", refresh_info=True)
            assert list(device.points_from_fltr(fltr)) == [Points.ONE, Points.TWO, Points.THREE]

            assert device.point_futures == {
                None: RF(True),
                Points.ONE: RF(False),
                Points.TWO: RF(True),
                Points.THREE: RF(False),
            }

        it "does not reset futures if we have a refresh_info but fltr doesn't match", device, Points, Fltr, RF:
            for f in device.point_futures.values():
                f.set_result(True)

            fltr = Fltr("attr1", "attr4", refresh_info=True)
            assert list(device.points_from_fltr(fltr)) == [Points.ONE, Points.TWO]

            assert device.point_futures == {
                None: RF(True),
                Points.ONE: RF(False),
                Points.TWO: RF(True),
                Points.THREE: RF(True),
            }

        it "doesn't fail resetting future if already reset", device, Points, Fltr, RF:
            assert all(not f.done() for f in device.point_futures.values())

            fltr = Fltr("attr1", "attr6", "attr4", refresh_info=True)
            assert list(device.points_from_fltr(fltr)) == [Points.ONE, Points.TWO, Points.THREE]

            assert device.point_futures == {
                None: RF(False),
                Points.ONE: RF(False),
                Points.TWO: RF(False),
                Points.THREE: RF(False),
            }

    describe "final_future":
        it "has a memoized final_future", device:
            ff = device.final_future
            assert isinstance(ff, asyncio.Future)
            assert not ff.done()

            assert device.final_future is ff
            del device.final_future

            assert device.final_future is not ff
