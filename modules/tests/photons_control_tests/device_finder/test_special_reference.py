# coding: spec

from photons_control.device_finder import DeviceFinder, Filter, Finder

from photons_app.special import SpecialReference
from photons_app import helpers as hp

from photons_messages import DeviceMessages, LightMessages, DiscoveryMessages
from photons_products import Products

from unittest import mock
import binascii
import pytest


@pytest.fixture(autouse=True)
def set_async_timeout(request):
    request.applymarker(pytest.mark.async_timeout(10))


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

                V.finder.finish.assert_called_once_with(None, None, None)
                FakeFinder.assert_called_once_with(V.sender)

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
    async def V(self, final_future):
        class V:
            serials = ["d073d5000001", "d073d5000002", "d073d5000003"]
            devices = pytest.helpers.mimic()

            d1 = devices.add("d1")(serials[0], Products.LCM3_TILE, hp.Firmware(3, 50))
            d2 = devices.add("d2")(
                serials[1], Products.LCM2_Z, hp.Firmware(2, 80), value_store=dict(zones=[])
            )
            d3 = devices.add("d3")(
                serials[2],
                Products.LCM2_A19,
                hp.Firmware(2, 80),
                value_store=dict(
                    firmware=hp.Firmware(2, 80),
                    group={"identity": "aa", "label": "g1", "updated_at": 42},
                    location={"identity": "bb", "label": "l1", "updated_at": 56},
                ),
            )

        v = V()
        async with V.devices.for_test(final_future) as sender:
            v.sender = sender
            yield v

    async it "can get serials and info", V:
        reference = DeviceFinder.empty()
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == sorted(V.serials)
        for device in V.devices:
            V.devices.store(device).assertIncoming(DiscoveryMessages.GetService())
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(label="kitchen")
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == []

        for device in V.devices:
            V.devices.store(device).assertIncoming(
                DiscoveryMessages.GetService(),
                DeviceMessages.GetLabel(),
            )
            V.devices.store(device).clear()

        await V.d3.change_one("label", "kitchen", event=None)
        reference = DeviceFinder.from_kwargs(label="kitchen")
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d3.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming(
                DiscoveryMessages.GetService(),
                DeviceMessages.GetLabel(),
            )
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(cap="matrix")
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d1.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming(
                DiscoveryMessages.GetService(),
                DeviceMessages.GetVersion()
            )
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(cap=["matrix", "multizone"])
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d1.serial, V.d2.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming(
                DiscoveryMessages.GetService(),
                DeviceMessages.GetVersion()
            )
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(cap=["not_matrix"], label="kitchen")
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d3.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming(
                DiscoveryMessages.GetService(),
                LightMessages.GetColor(),
                DeviceMessages.GetVersion(),
            )
            V.devices.store(device).clear()

        found = []
        reference = DeviceFinder.from_kwargs(label="kitchen")
        async for device in reference.info(V.sender):
            found.append(device)
        assert [f.serial for f in found] == [V.d3.serial]

        assert found[0].info == {
            "cap": pytest.helpers.has_caps_list("color", "variable_color_temp"),
            "hue": V.d3.attrs.color.hue,
            "label": "kitchen",
            "power": "off",
            "serial": V.d3.serial,
            "kelvin": V.d3.attrs.color.kelvin,
            "saturation": V.d3.attrs.color.saturation,
            "brightness": V.d3.attrs.color.brightness,
            "product_id": 27,
            "product_name": "LIFX A19",
            "product_type": "light",
            "firmware_version": "2.80",
            'group_id': 'aa000000000000000000000000000000',
            'group_name': 'g1',
            'location_id': 'bb000000000000000000000000000000',
            'location_name': 'l1',
        }

        for device in V.devices:
            if device is V.d3:
                V.devices.store(device).assertIncoming(
                    DiscoveryMessages.GetService(),
                    DeviceMessages.GetLabel(),
                    DeviceMessages.GetVersion(),
                    LightMessages.GetColor(),
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetGroup(),
                    DeviceMessages.GetLocation(),
                )
            else:
                V.devices.store(device).assertIncoming(
                    DiscoveryMessages.GetService(),
                    DeviceMessages.GetLabel(),
                )
            #V.devices.store(device).assertIncoming(
            #    DiscoveryMessages.GetService(),
            #    DeviceMessages.GetVersion(),
            #    LightMessages.GetColor(),
            #)
            V.devices.store(device).clear()

        found = []
        reference = DeviceFinder.from_kwargs(label="kitchen")
        async for device in reference.info(V.sender):
            found.append(device)
        assert [f.serial for f in found] == [V.d3.serial]
        assert found[0].info == {
            "cap": pytest.helpers.has_caps_list("color", "variable_color_temp"),
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
            "product_name": "LIFX A19",
            "product_type": "light",
            "group_name": "g1",
            "location_id": "bb000000000000000000000000000000",
            "location_name": "l1",
        }

        for device in V.devices:
            if device is V.d3:
                V.devices.store(device).assertIncoming(
                    DiscoveryMessages.GetService(),
                    DeviceMessages.GetLabel(),
                    DeviceMessages.GetVersion(),
                    LightMessages.GetColor(),
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetGroup(),
                    DeviceMessages.GetLocation(),
                )
            else:
                V.devices.store(device).assertIncoming(
                    DiscoveryMessages.GetService(),
                    DeviceMessages.GetLabel(),

                )
            V.devices.store(device).clear()

    async it "can reuse a finder", V:

        finder = Finder(V.sender)

        reference = DeviceFinder.empty(finder=finder)
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == sorted(V.serials)
        for device in V.devices:
            V.devices.store(device).assertIncoming(DiscoveryMessages.GetService)
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(label="kitchen", finder=finder)
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == []

        for device in V.devices:
            V.devices.store(device).assertIncoming(
                DeviceMessages.GetLabel(),
            )
            V.devices.store(device).clear()

        await V.d3.change_one("label", "kitchen", event=None)
        reference = DeviceFinder.from_kwargs(label="kitchen", finder=finder)
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        # It can't find it because the finder has the label cached
        assert ss == []

        for device in V.devices:
            V.devices.store(device).assertIncoming()
            V.devices.store(device).clear()

        await V.d3.change_one("label", "kitchen", event=None)
        reference = DeviceFinder.from_kwargs(label="kitchen", refresh_info=True, finder=finder)
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        # But now it can because refresh_info is True
        assert ss == [V.d3.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming(
                DeviceMessages.GetLabel(),
            )
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(cap="matrix", finder=finder)
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d1.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming(DeviceMessages.GetVersion())
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(cap=["matrix", "multizone"], finder=finder)
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d1.serial, V.d2.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming()
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(cap=["not_matrix"], label="kitchen", finder=finder)
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d3.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming(LightMessages.GetColor())
            V.devices.store(device).clear()

        found = []
        reference = DeviceFinder.from_kwargs(label="kitchen", finder=finder)
        async for device in reference.serials(V.sender):
            found.append(device)
        assert [f.serial for f in found] == [V.d3.serial]
        assert found[0].info == {
            "cap": pytest.helpers.has_caps_list("color", "variable_color_temp"),
            "hue": V.d3.attrs.color.hue,
            "label": "kitchen",
            "power": "off",
            "serial": V.d3.serial,
            "kelvin": V.d3.attrs.color.kelvin,
            "saturation": V.d3.attrs.color.saturation,
            "brightness": V.d3.attrs.color.brightness,
            "product_id": 27,
            "product_name": "LIFX A19",
            "product_type": "light",
        }

        for device in V.devices:
            V.devices.store(device).assertIncoming()
            V.devices.store(device).clear()

        found = []
        reference = DeviceFinder.from_kwargs(label="kitchen", finder=finder)
        async for device in reference.info(V.sender):
            found.append(device)
        assert [f.serial for f in found] == [V.d3.serial]
        assert found[0].info == {
            "cap": pytest.helpers.has_caps_list("color", "variable_color_temp"),
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
            "product_name": "LIFX A19",
            "product_type": "light",
            "group_name": "g1",
            "location_id": "bb000000000000000000000000000000",
            "location_name": "l1",
        }

        for device in V.devices:
            if device is V.d3:
                V.devices.store(device).assertIncoming(
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetGroup(),
                    DeviceMessages.GetLocation(),
                )
            else:
                V.devices.store(device).assertIncoming()
            V.devices.store(device).clear()
