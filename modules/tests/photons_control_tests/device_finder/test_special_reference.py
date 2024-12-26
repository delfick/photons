import binascii
from unittest import mock

import pytest
from photons_app import helpers as hp
from photons_app.special import SpecialReference
from photons_control.device_finder import DeviceFinder, Filter, Finder
from photons_messages import DeviceMessages, DiscoveryMessages, LightMessages
from photons_products import Products


@pytest.fixture
def default_async_timeout() -> float:
    return 10


class TestDeviceFinder:
    def test_it_takes_in_filter(self):
        fltr = Filter.empty()
        reference = DeviceFinder(fltr)
        assert reference.fltr is fltr
        assert reference.finder is None
        assert isinstance(reference, SpecialReference)

    def test_it_can_take_in_a_finder(self):
        fltr = Filter.empty()
        finder = mock.Mock(name="finder")
        reference = DeviceFinder(fltr, finder=finder)
        assert reference.fltr is fltr
        assert reference.finder is finder
        assert isinstance(reference, SpecialReference)

    class TestUsage:
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

        class TestAFinderContextManager:
            async def test_it_uses_the_finder_on_the_reference_if_it_exists(self, V):
                reference = DeviceFinder(V.fltr, finder=V.finder)

                async with reference.a_finder(V.sender) as f:
                    assert f is V.finder
                    V.finder.finish.assert_not_called()
                V.finder.finish.assert_not_called()

            async def test_it_creates_its_own_finder_if_one_isnt_on_the_reference(self, V):
                FakeFinder = mock.Mock(name="Finder", return_value=V.finder, spec=[])
                reference = DeviceFinder(V.fltr)

                with mock.patch("photons_control.device_finder.Finder", FakeFinder):
                    async with reference.a_finder(V.sender) as f:
                        assert reference.finder is None
                        assert f is V.finder
                        V.finder.finish.assert_not_called()

                V.finder.finish.assert_called_once_with(None, None, None)
                FakeFinder.assert_called_once_with(V.sender)

        class TestInfo:
            async def test_it_yields_devices_from_the_finder(self, V):
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

        class TestSerials:
            async def test_it_yields_devices_from_the_finder(self, V):
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

        class TestProxyingFilterClassmethods:
            @pytest.fixture()
            def fltr(self):
                return Filter.from_kwargs(label="kitchen", cap=["matrix", "chain"])

            def test_it_supports_from_json_str(self, V, fltr):
                reference = DeviceFinder.from_json_str('{"label": "kitchen", "cap": ["matrix", "chain"]}')
                assert reference.fltr == fltr
                assert reference.finder is None

                reference = DeviceFinder.from_json_str('{"label": "kitchen", "cap": ["matrix", "chain"]}', finder=V.finder)
                assert reference.fltr == fltr
                assert reference.finder is V.finder

            def test_it_supports_from_key_value_str(self, V, fltr):
                reference = DeviceFinder.from_key_value_str("label=kitchen cap=matrix,chain")
                assert reference.fltr == fltr
                assert reference.finder is None

                reference = DeviceFinder.from_key_value_str("label=kitchen cap=matrix,chain", finder=V.finder)
                assert reference.fltr == fltr
                assert reference.finder is V.finder

            def test_it_supports_from_url_str(self, V, fltr):
                reference = DeviceFinder.from_url_str("label=kitchen&cap=matrix&cap=chain")
                assert reference.fltr == fltr
                assert reference.finder is None

                reference = DeviceFinder.from_url_str("label=kitchen&cap=matrix&cap=chain", finder=V.finder)
                assert reference.fltr == fltr
                assert reference.finder is V.finder

            def test_it_supports_from_kwargs(self, V, fltr):
                reference = DeviceFinder.from_kwargs(label="kitchen", cap=["matrix", "chain"])
                assert reference.fltr == fltr
                assert reference.finder is None

                reference = DeviceFinder.from_kwargs(label="kitchen", cap=["matrix", "chain"], finder=V.finder)
                assert reference.fltr == fltr
                assert reference.finder is V.finder

            def test_it_supports_empty(self, V, fltr):
                for ri, rd in ((False, False), (True, True), (True, False), (False, True)):
                    expected = Filter.empty(refresh_info=ri, refresh_discovery=rd)
                    reference = DeviceFinder.empty(refresh_info=ri, refresh_discovery=rd)
                    assert reference.fltr == expected
                    assert reference.finder is None

                    reference = DeviceFinder.empty(refresh_info=ri, refresh_discovery=rd, finder=V.finder)
                    assert reference.fltr == expected
                    assert reference.finder is V.finder

                reference = DeviceFinder.empty()
                assert reference.fltr == Filter.empty(refresh_info=False, refresh_discovery=False)
                assert reference.finder is None

                reference = DeviceFinder.empty(finder=V.finder)
                assert reference.fltr == Filter.empty(refresh_info=False, refresh_discovery=False)
                assert reference.finder is V.finder

            def test_it_supports_from_options(self, V, fltr):
                reference = DeviceFinder.from_options({"label": "kitchen", "cap": ["matrix", "chain"]})
                assert reference.fltr == fltr
                assert reference.finder is None

                reference = DeviceFinder.from_options({"label": "kitchen", "cap": ["matrix", "chain"]}, finder=V.finder)
                assert reference.fltr == fltr
                assert reference.finder is V.finder


class TestFindingDevices:
    @pytest.fixture()
    async def V(self, final_future):
        class V:
            serials = ["d073d5000001", "d073d5000002", "d073d5000003", "d073d5000004"]
            devices = pytest.helpers.mimic()

            d1 = devices.add("d1")(serials[0], Products.LCM3_TILE, hp.Firmware(3, 50))
            d2 = devices.add("d2")(serials[1], Products.LCM2_Z, hp.Firmware(2, 80), value_store=dict(zones=[]))
            d3 = devices.add("d3")(
                serials[2],
                Products.LCM2_A19,
                hp.Firmware(2, 80),
                value_store=dict(
                    label="deethree",
                    group={"identity": "aa", "label": "g1", "updated_at": 42},
                    location={"identity": "bb", "label": "l1", "updated_at": 56},
                ),
            )
            d4 = devices.add("d4")(
                serials[3],
                Products.LCM3_32_SWITCH_I,
                hp.Firmware(3, 90),
                value_store=dict(
                    label="switchstacle",
                    group={"identity": "aa", "label": "g1", "updated_at": 42},
                    location={"identity": "bb", "label": "l1", "updated_at": 56},
                ),
            )

        v = V()
        async with V.devices.for_test(final_future) as sender:
            v.sender = sender
            yield v

    async def test_it_can_get_serials_and_info(self, V):
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
            expected = [
                DiscoveryMessages.GetService(),
                DeviceMessages.GetVersion(),
                LightMessages.GetColor(),
            ]
            if device is V.devices["d4"]:
                expected.append(DeviceMessages.GetLabel)
            V.devices.store(device).assertIncoming(*expected)
            V.devices.store(device).clear()

        await V.d3.change_one("label", "kitchen", event=None)
        reference = DeviceFinder.from_kwargs(label="kitchen")
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d3.serial]

        for device in V.devices:
            expected = [
                DiscoveryMessages.GetService(),
                DeviceMessages.GetVersion(),
                LightMessages.GetColor(),
            ]
            if device is V.devices["d4"]:
                expected.append(DeviceMessages.GetLabel())
            V.devices.store(device).assertIncoming(*expected)
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(cap="matrix")
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d1.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming(DiscoveryMessages.GetService(), DeviceMessages.GetVersion())
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(cap=["matrix", "multizone"])
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d1.serial, V.d2.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming(DiscoveryMessages.GetService(), DeviceMessages.GetVersion())
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(cap=["not_matrix"], label="kitchen")
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d3.serial]

        for device in V.devices:
            if device is V.devices["d4"]:
                V.devices.store(device).assertIncoming(
                    DiscoveryMessages.GetService(),
                    LightMessages.GetColor(),
                    DeviceMessages.GetVersion(),
                    DeviceMessages.GetLabel(),
                )
            else:
                V.devices.store(device).assertIncoming(
                    DiscoveryMessages.GetService(),
                    LightMessages.GetColor(),
                    DeviceMessages.GetVersion(),
                )
            V.devices.store(device).clear()

        found = []
        reference = DeviceFinder.from_kwargs(label="kitchen")
        async for device in reference.serials(V.sender):
            found.append(device)
        assert [f.serial for f in found] == [V.d3.serial]
        assert found[0].info == {
            "hue": V.d3.attrs.color.hue,
            "label": "kitchen",
            "power": "off",
            "serial": V.d3.serial,
            "product_type": "light",
            "kelvin": V.d3.attrs.color.kelvin,
            "saturation": V.d3.attrs.color.saturation,
            "brightness": V.d3.attrs.color.brightness,
            "product_id": 27,
            "product_name": "LIFX A19",
            "cap": pytest.helpers.has_caps_list("color", "variable_color_temp"),
        }

        for device in V.devices:
            expected = [
                DiscoveryMessages.GetService(),
                DeviceMessages.GetVersion(),
                LightMessages.GetColor(),
            ]
            if device is V.devices["d4"]:
                expected.append(DeviceMessages.GetLabel())
            V.devices.store(device).assertIncoming(*expected)
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
                    LightMessages.GetColor(),
                    DeviceMessages.GetVersion(),
                    DeviceMessages.GetHostFirmware(),
                    DeviceMessages.GetGroup(),
                    DeviceMessages.GetLocation(),
                )
            elif device is V.d4:
                V.devices.store(device).assertIncoming(
                    DiscoveryMessages.GetService(),
                    DeviceMessages.GetVersion(),
                    LightMessages.GetColor(),
                    DeviceMessages.GetLabel(),
                )
            else:
                V.devices.store(device).assertIncoming(
                    DiscoveryMessages.GetService(),
                    DeviceMessages.GetVersion(),
                    LightMessages.GetColor(),
                )
            V.devices.store(device).clear()

    async def test_it_can_reuse_a_finder(self, V):
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
            expected = [DeviceMessages.GetVersion(), LightMessages.GetColor()]
            if device is V.d4:
                expected.append(DeviceMessages.GetLabel())
            V.devices.store(device).assertIncoming(*expected)
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
            if device is V.d4:
                V.devices.store(device).assertIncoming(DeviceMessages.GetLabel())
            else:
                V.devices.store(device).assertIncoming(LightMessages.GetColor())
            V.devices.store(device).clear()

        reference = DeviceFinder.from_kwargs(cap="matrix", finder=finder)
        found, ss = await reference.find(V.sender, timeout=5)
        reference.raise_on_missing(found)
        assert sorted(list(found)) == sorted(binascii.unhexlify(s)[:6] for s in ss)
        assert ss == [V.d1.serial]

        for device in V.devices:
            V.devices.store(device).assertIncoming()
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
            V.devices.store(device).assertIncoming()
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
            assert V.devices.store(device) == []

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
