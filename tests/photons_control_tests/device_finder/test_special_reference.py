# coding: spec

from photons_control.device_finder import DeviceFinder, Filter, Finder
from photons_control import test_helpers as chp

from photons_app.special import SpecialReference
from photons_app import helpers as hp

from photons_messages import DeviceMessages, LightMessages
from photons_transport.fake import FakeDevice
from photons_products import Products

from unittest import mock
import binascii
import pytest

describe "DeviceFinder":
    it "takes in filter":
        fltr = Filter.empty()
        reference = DeviceFinder(fltr)
        assert reference.fltr is fltr
        assert reference.finder is None
        assert isinstance(reference, SpecialReference)

    it "can take in a finder":
        fltr = Filter.empty()
        finder = mock.Mock(name="finder")
        reference = DeviceFinder(fltr, finder=finder)
        assert reference.fltr is fltr
        assert reference.finder is finder
        assert isinstance(reference, SpecialReference)

    describe "usage":

        @pytest.fixture()
        def V(self):
            class V:
                fltr = mock.NonCallableMock(name="fltr", spec=[])
                sender = mock.NonCallableMock(name="sender", spec=[])

                @hp.memoized_property
                def finder(s):
                    finder = mock.Mock(name="finder", spec=["finish"])
                    finder.finish = pytest.helpers.AsyncMock(name="finish")
                    return finder

            return V()

        describe "a_finder context manager":
            async it "uses the finder on the reference if it exists", V:
                reference = DeviceFinder(V.fltr, finder=V.finder)

                async with reference.a_finder(V.sender) as f:
                    assert f is V.finder
                    V.finder.finish.assert_not_called()
                V.finder.finish.assert_not_called()

            async it "creates it's own finder if one isn't on the reference", V:
                FakeFinder = mock.Mock(name="Finder", return_value=V.finder, spec=[])
                reference = DeviceFinder(V.fltr)

                with mock.patch("photons_control.device_finder.Finder", FakeFinder):
                    async with reference.a_finder(V.sender) as f:
                        assert reference.finder is None
                        assert f is V.finder
                        V.finder.finish.assert_not_called()

                V.finder.finish.assert_called_once_with()
                FakeFinder.assert_called_once_with(V.sender)

        describe "finish":
            async it "does nothing", V:
                await DeviceFinder(V.fltr).finish()
                await DeviceFinder(V.fltr, finder=V.finder).finish()
                V.finder.finish.assert_not_called()

        describe "info":
            async it "yields devices from the finder", V:
                called = []

                class a_finder:
                    def __init__(s, sender):
                        called.append("got_sender")
                        assert sender is V.sender

                    async def __aenter__(s):
                        called.append("making_finder")
                        return V.finder

                    async def __aexit__(s, exc_typ, exc, tb):
                        pass

                reference = DeviceFinder(V.fltr)

                d1 = mock.Mock(name="d1")
                d2 = mock.Mock(name="d2")

                async def info(f):
                    called.append("info_start")
                    assert f is V.fltr
                    called.append("send_d1")
                    yield d1
                    called.append("send_d2")
                    yield d2
                    called.append("info_done")

                V.finder.info = pytest.helpers.MagicAsyncMock(name="info", side_effect=info)

                found = []
                with mock.patch.object(reference, "a_finder", a_finder):
                    async for device in reference.info(V.sender):
                        called.append(("got_device", device))
                        found.append(device)

                assert called == [
                    "got_sender",
                    "making_finder",
                    "info_start",
                    "send_d1",
                    ("got_device", d1),
                    "send_d2",
                    ("got_device", d2),
                    "info_done",
                ]
                assert found == [d1, d2]

        describe "serials":
            async it "yields devices from the finder", V:
                called = []

                class a_finder:
                    def __init__(s, sender):
                        called.append("got_sender")
                        assert sender is V.sender

                    async def __aenter__(s):
                        called.append("making_finder")
                        return V.finder

                    async def __aexit__(s, exc_typ, exc, tb):
                        pass

                reference = DeviceFinder(V.fltr)

                d1 = mock.Mock(name="d1")
                d2 = mock.Mock(name="d2")

                async def find(f):
                    called.append("find_start")
                    assert f is V.fltr
                    called.append("send_d1")
                    yield d1
                    called.append("send_d2")
                    yield d2
                    called.append("find_done")

                V.finder.find = pytest.helpers.MagicAsyncMock(name="find", side_effect=find)

                found = []
                with mock.patch.object(reference, "a_finder", a_finder):
                    async for device in reference.serials(V.sender):
                        called.append(("got_device", device))
                        found.append(device)

                assert called == [
                    "got_sender",
                    "making_finder",
                    "find_start",
                    "send_d1",
                    ("got_device", d1),
                    "send_d2",
                    ("got_device", d2),
                    "find_done",
                ]
                assert found == [d1, d2]

        describe "Proxying Filter classmethods":

            @pytest.fixture()
            def fltr(self):
                return Filter.from_kwargs(label="kitchen", cap=["matrix", "chain"])

            it "supports from_json_str", V, fltr:
                reference = DeviceFinder.from_json_str(
                    '{"label": "kitchen", "cap": ["matrix", "chain"]}'
                )
                assert reference.fltr == fltr
                assert reference.finder is None

                reference = DeviceFinder.from_json_str(
                    '{"label": "kitchen", "cap": ["matrix", "chain"]}', finder=V.finder
                )
                assert reference.fltr == fltr
                assert reference.finder is V.finder

            it "supports from_key_value_str", V, fltr:
                reference = DeviceFinder.from_key_value_str("label=kitchen cap=matrix,chain")
                assert reference.fltr == fltr
                assert reference.finder is None

                reference = DeviceFinder.from_key_value_str(
                    "label=kitchen cap=matrix,chain", finder=V.finder
                )
                assert reference.fltr == fltr
                assert reference.finder is V.finder

            it "supports from_url_str", V, fltr:
                reference = DeviceFinder.from_url_str("label=kitchen&cap=matrix&cap=chain")
                assert reference.fltr == fltr
                assert reference.finder is None

                reference = DeviceFinder.from_url_str(
                    "label=kitchen&cap=matrix&cap=chain", finder=V.finder
                )
                assert reference.fltr == fltr
                assert reference.finder is V.finder

            it "supports from_kwargs", V, fltr:
                reference = DeviceFinder.from_kwargs(label="kitchen", cap=["matrix", "chain"])
                assert reference.fltr == fltr
                assert reference.finder is None

                reference = DeviceFinder.from_kwargs(
                    label="kitchen", cap=["matrix", "chain"], finder=V.finder
                )
                assert reference.fltr == fltr
                assert reference.finder is V.finder

            it "supports empty", V, fltr:
                for ri, rd in ((False, False), (True, True), (True, False), (False, True)):
                    expected = Filter.empty(refresh_info=ri, refresh_discovery=rd)
                    reference = DeviceFinder.empty(refresh_info=ri, refresh_discovery=rd)
                    assert reference.fltr == expected
                    assert reference.finder is None

                    reference = DeviceFinder.empty(
                        refresh_info=ri, refresh_discovery=rd, finder=V.finder
                    )
                    assert reference.fltr == expected
                    assert reference.finder is V.finder

                reference = DeviceFinder.empty()
                assert reference.fltr == Filter.empty(refresh_info=False, refresh_discovery=False)
                assert reference.finder is None

                reference = DeviceFinder.empty(finder=V.finder)
                assert reference.fltr == Filter.empty(refresh_info=False, refresh_discovery=False)
                assert reference.finder is V.finder

            it "supports from_options", V, fltr:
                reference = DeviceFinder.from_options(
                    {"label": "kitchen", "cap": ["matrix", "chain"]}
                )
                assert reference.fltr == fltr
                assert reference.finder is None

                reference = DeviceFinder.from_options(
                    {"label": "kitchen", "cap": ["matrix", "chain"]}, finder=V.finder
                )
                assert reference.fltr == fltr
                assert reference.finder is V.finder

describe "finding devices":

    @pytest.fixture()
    def V(self):
        class V:
            serials = ["d073d5000001", "d073d5000002", "d073d5000003"]

            d1 = FakeDevice(serials[0], chp.default_responders(Products.LCM3_TILE))
            d2 = FakeDevice(serials[1], chp.default_responders(Products.LCM2_Z, zones=[]))
            d3 = FakeDevice(
                serials[2],
                chp.default_responders(
                    Products.LCM2_A19,
                    firmware=chp.Firmware(2, 80, 1337),
                    group_uuid="aa",
                    group_label="g1",
                    group_updated_at=42,
                    location_uuid="bb",
                    location_label="l1",
                    location_updated_at=56,
                ),
            )

            @hp.memoized_property
            def devices(s):
                return [s.d1, s.d2, s.d3]

        return V()

    async it "can get serials and info", memory_devices_runner, V:
        async with memory_devices_runner(V.devices) as runner:
            reference = DeviceFinder.empty()
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == sorted(V.serials)
            for device in V.devices:
                device.compare_received([])
                device.reset_received()

            reference = DeviceFinder.from_kwargs(label="kitchen")
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == []

            for device in V.devices:
                device.compare_received([LightMessages.GetColor()])
                device.reset_received()

            V.d3.attrs.label = "kitchen"
            reference = DeviceFinder.from_kwargs(label="kitchen")
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == [V.d3.serial]

            for device in V.devices:
                device.compare_received([LightMessages.GetColor()])
                device.reset_received()

            reference = DeviceFinder.from_kwargs(cap="matrix")
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == [V.d1.serial]

            for device in V.devices:
                device.compare_received([DeviceMessages.GetVersion()])
                device.reset_received()

            reference = DeviceFinder.from_kwargs(cap=["matrix", "multizone"])
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == [V.d1.serial, V.d2.serial]

            for device in V.devices:
                device.compare_received([DeviceMessages.GetVersion()])
                device.reset_received()

            reference = DeviceFinder.from_kwargs(cap=["not_matrix"], label="kitchen")
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == [V.d3.serial]

            for device in V.devices:
                device.compare_received([LightMessages.GetColor(), DeviceMessages.GetVersion()])
                device.reset_received()

            found = []
            reference = DeviceFinder.from_kwargs(label="kitchen")
            async for device in reference.serials(runner.sender):
                found.append(device)
            assert [f.serial for f in found] == [V.d3.serial]
            assert found[0].info == {
                "hue": V.d3.attrs.color.hue,
                "label": "kitchen",
                "power": "off",
                "serial": V.d3.serial,
                "kelvin": V.d3.attrs.color.kelvin,
                "saturation": V.d3.attrs.color.saturation,
                "brightness": V.d3.attrs.color.brightness,
            }

            for device in V.devices:
                device.compare_received([LightMessages.GetColor()])
                device.reset_received()

            found = []
            reference = DeviceFinder.from_kwargs(label="kitchen")
            async for device in reference.info(runner.sender):
                found.append(device)
            assert [f.serial for f in found] == [V.d3.serial]
            assert found[0].info == {
                "cap": [
                    "color",
                    "not_chain",
                    "not_ir",
                    "not_matrix",
                    "not_multizone",
                    "variable_color_temp",
                ],
                "firmware_version": "2.80",
                "hue": V.d3.attrs.color.hue,
                "label": "kitchen",
                "power": "off",
                "serial": V.d3.serial,
                "kelvin": V.d3.attrs.color.kelvin,
                "saturation": V.d3.attrs.color.saturation,
                "brightness": V.d3.attrs.color.brightness,
                "group_id": "aa000000000000000000000000000000",
                "product_id": 27,
                "group_name": "g1",
                "location_id": "bb000000000000000000000000000000",
                "location_name": "l1",
                "product_identifier": "lifx_a19",
            }

            for device in V.devices:
                if device is V.d3:
                    device.compare_received(
                        [
                            LightMessages.GetColor(),
                            DeviceMessages.GetVersion(),
                            DeviceMessages.GetHostFirmware(),
                            DeviceMessages.GetGroup(),
                            DeviceMessages.GetLocation(),
                        ]
                    )
                else:
                    device.compare_received([LightMessages.GetColor()])
                device.reset_received()

    async it "can reuse a finder", memory_devices_runner, V:

        async with memory_devices_runner(V.devices) as runner:
            finder = Finder(runner.sender)

            reference = DeviceFinder.empty(finder=finder)
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == sorted(V.serials)
            for device in V.devices:
                device.compare_received([])
                device.reset_received()

            reference = DeviceFinder.from_kwargs(label="kitchen", finder=finder)
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == []

            for device in V.devices:
                device.compare_received([LightMessages.GetColor()])
                device.reset_received()

            V.d3.attrs.label = "kitchen"
            reference = DeviceFinder.from_kwargs(label="kitchen", finder=finder)
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            # It can't find it because the finder has the label cached
            assert ss == []

            for device in V.devices:
                device.compare_received([])
                device.reset_received()

            V.d3.attrs.label = "kitchen"
            reference = DeviceFinder.from_kwargs(label="kitchen", refresh_info=True, finder=finder)
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            # But now it can because refresh_info is True
            assert ss == [V.d3.serial]

            for device in V.devices:
                device.compare_received([LightMessages.GetColor()])
                device.reset_received()

            reference = DeviceFinder.from_kwargs(cap="matrix", finder=finder)
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == [V.d1.serial]

            for device in V.devices:
                device.compare_received([DeviceMessages.GetVersion()])
                device.reset_received()

            reference = DeviceFinder.from_kwargs(cap=["matrix", "multizone"], finder=finder)
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == [V.d1.serial, V.d2.serial]

            for device in V.devices:
                device.compare_received([])
                device.reset_received()

            reference = DeviceFinder.from_kwargs(cap=["not_matrix"], label="kitchen", finder=finder)
            found, ss = await reference.find(runner.sender, timeout=5)
            reference.raise_on_missing(found)
            assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
            assert ss == [V.d3.serial]

            for device in V.devices:
                device.compare_received([])
                device.reset_received()

            found = []
            reference = DeviceFinder.from_kwargs(label="kitchen", finder=finder)
            async for device in reference.serials(runner.sender):
                found.append(device)
            assert [f.serial for f in found] == [V.d3.serial]
            assert found[0].info == {
                "cap": [
                    "color",
                    "not_chain",
                    "not_ir",
                    "not_matrix",
                    "not_multizone",
                    "variable_color_temp",
                ],
                "hue": V.d3.attrs.color.hue,
                "label": "kitchen",
                "power": "off",
                "serial": V.d3.serial,
                "kelvin": V.d3.attrs.color.kelvin,
                "saturation": V.d3.attrs.color.saturation,
                "brightness": V.d3.attrs.color.brightness,
                "product_id": 27,
                "product_identifier": "lifx_a19",
            }

            for device in V.devices:
                device.compare_received([])
                device.reset_received()

            found = []
            reference = DeviceFinder.from_kwargs(label="kitchen", finder=finder)
            async for device in reference.info(runner.sender):
                found.append(device)
            assert [f.serial for f in found] == [V.d3.serial]
            assert found[0].info == {
                "cap": [
                    "color",
                    "not_chain",
                    "not_ir",
                    "not_matrix",
                    "not_multizone",
                    "variable_color_temp",
                ],
                "firmware_version": "2.80",
                "hue": V.d3.attrs.color.hue,
                "label": "kitchen",
                "power": "off",
                "serial": V.d3.serial,
                "kelvin": V.d3.attrs.color.kelvin,
                "saturation": V.d3.attrs.color.saturation,
                "brightness": V.d3.attrs.color.brightness,
                "group_id": "aa000000000000000000000000000000",
                "product_id": 27,
                "group_name": "g1",
                "location_id": "bb000000000000000000000000000000",
                "location_name": "l1",
                "product_identifier": "lifx_a19",
            }

            for device in V.devices:
                if device is V.d3:
                    device.compare_received(
                        [
                            DeviceMessages.GetHostFirmware(),
                            DeviceMessages.GetGroup(),
                            DeviceMessages.GetLocation(),
                        ]
                    )
                else:
                    device.compare_received([])
                device.reset_received()
