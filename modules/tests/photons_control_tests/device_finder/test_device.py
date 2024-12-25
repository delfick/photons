
import asyncio
import enum
import uuid
from unittest import mock

import pytest
from delfick_project.norms import sb
from photons_app import helpers as hp
from photons_control.device_finder import (
    Collection,
    Collections,
    Device,
    DeviceType,
    Filter,
    InfoPoints,
    Point,
)
from photons_messages import DeviceMessages, LightMessages

class TestDevice:

    @pytest.fixture()
    def device(self):
        return Device.FieldSpec().empty_normalise(serial="d073d5000001")

    def test_it_has_property_fields(self, device):
        assert device.property_fields == [
            "group_id",
            "group_name",
            "location_name",
            "location_id",
            "firmware_version",
            "abilities",
            "product_name",
            "product_type",
        ]
        for field in device.property_fields:
            if field == "product_type":
                assert device.product_type == DeviceType.UNKNOWN
            else:
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

    def test_it_has_as_dict_and_info_with_modified_values(self, device):
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
            "firmware_version": sb.NotSpecified,
            "product_id": 22,
            "product_name": "LIFX A19",
            "product_type": "light",
            "cap": pytest.helpers.has_caps_list("color"),
        }

        info = {"serial": values["serial"], "product_type": "unknown"}
        expected = {key: sb.NotSpecified for key in values}
        expected["serial"] = values["serial"]
        expected["product_type"] = "unknown"

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

        device.product_id = 32
        info["product_name"] = values["product_name"] = "LIFX Z"
        info["product_type"] = "light"
        info["product_id"] = values["product_id"] = 32
        info["cap"] = values["cap"] = pytest.helpers.has_caps_list(
            "color", "multizone", "variable_color_temp"
        )
        assert device.info == info
        assert device.as_dict() == values

        device.firmware = hp.Firmware(2, 80)
        values["firmware_version"] = "2.80"
        values["cap"] = pytest.helpers.has_caps_list(
            "color", "extended_multizone", "multizone", "variable_color_temp"
        )
        assert device.info == values
        assert device.as_dict() == values

    class TestMatchesFltr:
        def test_it_says_yes_if_the_filter_matches_all(self, device):
            device.label = "kitchen"
            device.power = "on"
            filtr = Filter.empty()
            assert filtr.matches_all
            assert device.matches_fltr(filtr)

        def test_it_says_yes_if_the_filter_matches_all_and_device_has_no_fields(self, device):
            filtr = Filter.empty()
            assert filtr.matches_all
            assert device.matches_fltr(filtr)

        def test_it_says_no_if_the_filtr_does_not_match(self, device):
            filtr = Filter.from_kwargs(label="bathroom")
            device.label = "kitchen"
            assert not device.matches_fltr(filtr)

        def test_it_says_no_if_the_device_has_nothing_on_it(self, device):
            filtr = Filter.from_kwargs(label="bathroom")
            assert not device.matches_fltr(filtr)

        def test_it_says_yes_if_the_filtr_matches(self, device):
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
                        mock.call("cap"),
                        mock.call("label"),
                        mock.call("power"),
                        mock.call("product_id"),
                        mock.call("product_name"),
                        mock.call("product_type"),
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
                        mock.call(
                            "cap", pytest.helpers.has_caps_list("color", "variable_color_temp")
                        ),
                        mock.call("label", "kitchen"),
                        mock.call("power", "on"),
                        mock.call("product_id", 22),
                        mock.call("product_name", "LIFX Color 1000"),
                        mock.call("product_type", DeviceType.LIGHT),
                        mock.call("group_id", "uuidg"),
                        mock.call("group_name", "blah"),
                        mock.call("serial", "d073d5000001"),
                    ]
                )
            )

    class TestSetFromPkt:

        @pytest.fixture()
        def collections(self):
            return Collections()

        def test_it_can_take_in_a_LightState(self, device, collections):
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

        def test_it_can_take_in_StateGroup(self, device, collections):
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

        def test_it_can_take_in_StateLocation(self, device, collections):
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

        def test_it_takes_in_StateHostFirmware(self, device, collections):
            pkt = DeviceMessages.StateHostFirmware.create(version_major=1, version_minor=20)
            assert device.set_from_pkt(pkt, collections) is InfoPoints.FIRMWARE
            assert str(device.firmware) == "1.20"

        def test_it_takes_in_StateVersion(self, device, collections):
            pkt = DeviceMessages.StateVersion.create(vendor=1, product=22)

            assert device.set_from_pkt(pkt, collections) is InfoPoints.VERSION

            assert device.product_id == 22
            assert device.abilities == [
                "color",
                "not_buttons",
                "not_chain",
                "not_extended_multizone",
                "not_hev",
                "not_ir",
                "not_matrix",
                "not_multizone",
                "not_relays",
                "not_unhandled",
                "variable_color_temp",
            ]

    class TestPointsFromFltr:

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

        def test_it_returns_all_the_InfoPoints_for_an_empty_fltr(self, device):
            assert list(device.points_from_fltr(Filter.empty())) == list(InfoPoints)

        def test_it_only_yields_points_if_one_of_its_keys_are_on_the_fltr(self, device, Points, Fltr):
            for f in device.point_futures.values():
                f.set_result(True)

            fltr = Fltr("attr1", "attr6")
            assert list(device.points_from_fltr(fltr)) == [Points.ONE, Points.THREE]
            assert all(f.done() for f in device.point_futures.values())

            fltr = Fltr("attr4")
            assert list(device.points_from_fltr(fltr)) == [Points.TWO]
            assert all(f.done() for f in device.point_futures.values())

        def test_it_resets_futures_if_we_have_a_refresh_info_and_a_refresh_amount(self, device, Points, Fltr, RF):
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

        def test_it_does_not_reset_futures_if_we_have_a_refresh_info_but_fltr_doesnt_match(self, device, Points, Fltr, RF):
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

        def test_it_doesnt_fail_resetting_future_if_already_reset(self, device, Points, Fltr, RF):
            assert all(not f.done() for f in device.point_futures.values())

            fltr = Fltr("attr1", "attr6", "attr4", refresh_info=True)
            assert list(device.points_from_fltr(fltr)) == [Points.ONE, Points.TWO, Points.THREE]

            assert device.point_futures == {
                None: RF(False),
                Points.ONE: RF(False),
                Points.TWO: RF(False),
                Points.THREE: RF(False),
            }

    class TestFinalFuture:
        def test_it_has_a_memoized_final_future(self, device):
            ff = device.final_future
            assert isinstance(ff, asyncio.Future)
            assert not ff.done()

            assert device.final_future is ff
            del device.final_future

            assert device.final_future is not ff
