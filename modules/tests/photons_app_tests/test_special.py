import asyncio
import binascii
import os
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_app import helpers as hp
from photons_app.errors import PhotonsAppError
from photons_app.special import (
    FoundSerials,
    HardCodedSerials,
    ResolveReferencesFromFile,
    SpecialReference,
)


class TestSpecialReference:
    async def test_it_gives_itself_a_finding_and_found_future(self):
        ref = SpecialReference()
        assert isinstance(ref.finding, hp.ResettableFuture)
        assert isinstance(ref.found, hp.ResettableFuture)

    async def test_it_can_reset_the_futures(self):
        ref = SpecialReference()
        ref.finding.set_result(True)
        ref.found.set_result(True)

        assert ref.finding.done()
        assert ref.found.done()
        ref.reset()

        assert not ref.finding.done()
        assert not ref.found.done()

    class TestFind:
        @pytest.fixture()
        def V(self):
            class V:
                sender = mock.Mock(name="sender")
                broadcast = mock.Mock(name="broadcast")
                find_timeout = mock.Mock(name="find_timeout")

            return V()

        async def test_it_transfers_cancellation_from_find_serials(self, V):
            class Finder(SpecialReference):
                async def find_serials(s, sender, *, timeout, broadcast=True):
                    f = hp.create_future()
                    f.cancel()
                    return await f

            ref = Finder()
            with assertRaises(asyncio.CancelledError):
                await ref.find(V.sender, timeout=V.find_timeout)

        async def test_it_transfers_exceptions_from_find_serials(self, V):
            class Finder(SpecialReference):
                async def find_serials(s, sender, *, timeout, broadcast=True):
                    f = hp.create_future()
                    f.set_exception(PhotonsAppError("FIND SERIALS BAD"))
                    return await f

            ref = Finder()
            with assertRaises(PhotonsAppError, "FIND SERIALS BAD"):
                await ref.find(V.sender, timeout=V.find_timeout)

        async def test_it_transfers_result_from_find_serials(self, V):
            serial1 = "d073d5000001"
            serial2 = "d073d5000002"

            target1 = binascii.unhexlify(serial1)
            target2 = binascii.unhexlify(serial2)

            services1 = mock.Mock(name="services1")
            services2 = mock.Mock(name="services2")

            class Finder(SpecialReference):
                async def find_serials(s, sender, *, timeout, broadcast=True):
                    return {target1: services1, target2: services2}

            ref = Finder()
            found, serials = await ref.find(V.sender, timeout=V.find_timeout)
            assert found == {target1: services1, target2: services2}
            assert serials == [serial1, serial2]

        async def test_it_only_calls_find_serials_once(self, V):
            serial = "d073d5000001"
            target = binascii.unhexlify(serial)
            services = mock.Mock(name="services")

            called = []

            class Finder(SpecialReference):
                async def find_serials(s, sender, *, timeout, broadcast=True):
                    await asyncio.sleep(0.2)
                    called.append(1)
                    return {target: services}

            ref = Finder()
            futs = []
            futs.append(hp.async_as_background(ref.find(V.sender, timeout=V.find_timeout)))
            futs.append(hp.async_as_background(ref.find(V.sender, timeout=V.find_timeout)))
            await asyncio.sleep(0.05)
            futs.append(hp.async_as_background(ref.find(V.sender, timeout=V.find_timeout)))
            await asyncio.sleep(0.2)
            futs.append(hp.async_as_background(ref.find(V.sender, timeout=V.find_timeout)))

            for t in futs:
                found, serials = await t
                assert found == {target: services}
                assert serials == [serial]

            assert called == [1]

            ref.reset()
            found, serials = await ref.find(V.sender, timeout=V.find_timeout)
            assert found == {target: services}
            assert serials == [serial]
            assert called == [1, 1]


class TestFoundSerials:
    async def test_it_calls_senderfind_devices_with_broadcast(self):
        found = mock.Mock(name="found")

        sender = mock.Mock(name="sender")
        sender.find_devices = pytest.helpers.AsyncMock(name="find_devices", return_value=found)

        broadcast = mock.Mock(name="broadcast")
        find_timeout = mock.Mock(name="find_timeout")

        ref = FoundSerials()
        res = await ref.find_serials(sender, broadcast=broadcast, timeout=find_timeout)

        assert res == found
        sender.find_devices.assert_called_once_with(broadcast=broadcast, raise_on_none=True, timeout=find_timeout)


class TestHardCodedSerials:
    @pytest.fixture()
    def V(self):
        class V:
            info1 = mock.Mock(name="info1")
            info2 = mock.Mock(name="info2")

            serial1 = "d073d5000001"
            serial2 = "d073d5000002"

            @hp.memoized_property
            def target1(s):
                return binascii.unhexlify(s.serial1)[:6]

            @hp.memoized_property
            def target2(s):
                return binascii.unhexlify(s.serial2)[:6]

        return V()

    async def test_it_takes_in_a_list_of_serials(self):
        serials = "d073d5000001,d073d500000200"
        wanted = [binascii.unhexlify(ref)[:6] for ref in serials.split(",")]

        for s in (serials, serials.split(",")):
            ref = HardCodedSerials(s)
            assert ref.targets == wanted
            assert ref.serials == ["d073d5000001", "d073d5000002"]

    async def test_it_can_take_in_list_of_unhexlified_serials(self):
        serials = [binascii.unhexlify("d073d500000100"), binascii.unhexlify("d073d5000002")]
        wanted = [binascii.unhexlify(ref)[:6] for ref in ["d073d5000001", "d073d5000002"]]

        ref = HardCodedSerials(serials)
        assert ref.targets == wanted
        assert ref.serials == ["d073d5000001", "d073d5000002"]

    class TestFindSerials:
        async def assertFindSerials(self, found, serials, expected, missing):
            broadcast = mock.Mock(name="broadcast")
            find_timeout = mock.Mock(name="find_timeout")

            sender = mock.Mock(name="sender")
            sender.found = {}
            sender.find_specific_serials = pytest.helpers.AsyncMock(name="find_specific_serials")
            sender.find_specific_serials.return_value = (found, missing)

            ref = HardCodedSerials(serials)
            f = await ref.find_serials(sender, broadcast=broadcast, timeout=find_timeout)

            assert f == expected

            sender.find_specific_serials.assert_called_once_with(serials, broadcast=broadcast, raise_on_none=False, timeout=find_timeout)

            assert ref.missing(f) == missing

        async def test_it_uses_find_specific_serials(self, V):
            found = {V.target1: V.info1, V.target2: V.info2}
            serials = [V.serial1, V.serial2]
            expected = {V.target1: V.info1, V.target2: V.info2}
            missing = []
            await self.assertFindSerials(found, serials, expected, missing)

        async def test_it_only_returns_from_the_serials_it_cares_about(self, V):
            found = {V.target1: V.info1, V.target2: V.info2}
            serials = [V.serial1]
            expected = {V.target1: V.info1}
            missing = []
            await self.assertFindSerials(found, serials, expected, missing)

        async def test_it_doesnt_call_to_find_specific_serials_if_the_serials_are_already_on_the_sender(self, V):
            broadcast = mock.Mock(name="broadcast")
            find_timeout = mock.Mock(name="find_timeout")

            sender = mock.Mock(name="sender")
            sender.found = {V.target1: V.info1, V.target2: V.info2}
            sender.find_specific_serials = pytest.helpers.AsyncMock(name="find_specific_serials", side_effect=AssertionError("Shouldn't be called"))

            ref = HardCodedSerials([V.serial1])
            f = await ref.find_serials(sender, broadcast=broadcast, timeout=find_timeout)

            assert f == {V.target1: V.info1}
            assert ref.missing(f) == []

        async def test_it_doesnt_care_if_no_found(self, V):
            found = {}
            serials = [V.serial1, V.serial2]
            expected = {}
            missing = [V.serial1, V.serial2]
            await self.assertFindSerials(found, serials, expected, missing)

        async def test_it_can_see_partial_missing(self, V):
            found = {V.target2: V.info2}
            serials = [V.serial1, V.serial2]
            expected = {V.target2: V.info2}
            missing = [V.serial1]
            await self.assertFindSerials(found, serials, expected, missing)


class TestResolveReferencesFromFile:
    async def test_it_complains_if_filename_cant_be_read_or_is_empty(self):
        with hp.a_temp_file() as fle:
            fle.close()
            os.remove(fle.name)

            with assertRaises(PhotonsAppError, "Failed to read serials from a file"):
                ResolveReferencesFromFile(fle.name)

        with hp.a_temp_file() as fle:
            fle.close()
            with assertRaises(PhotonsAppError, "Found no serials in file"):
                ResolveReferencesFromFile(fle.name)

    async def test_it_creates_and_uses_a_HardCodedSerials(self):
        serial1 = "d073d5000001"
        serial2 = "d073d5000002"

        resolver = mock.Mock(name="resolver")
        resolver.find = pytest.helpers.AsyncMock(name="find")
        FakeHardCodedSerials = mock.Mock(name="HardCodedSerials", return_value=resolver)

        with hp.a_temp_file() as fle:
            fle.write(f"{serial1}\n{serial2}".encode())
            fle.close()

            with mock.patch("photons_app.special.HardCodedSerials", FakeHardCodedSerials):
                r = ResolveReferencesFromFile(fle.name)

        assert r.serials == [serial1, serial2]
        assert r.reference == resolver
        FakeHardCodedSerials.assert_called_once_with([serial1, serial2])

        assert len(resolver.reset.mock_calls) == 0
        r.reset()
        resolver.reset.assert_called_once_with()

        sender = mock.Mock(name="sender")
        find_timeout = mock.Mock(name="find_timeout")
        assert len(resolver.find.mock_calls) == 0

        res = mock.Mock(name="res")
        resolver.find.return_value = res
        assert (await r.find(sender, timeout=find_timeout)) is res
        resolver.find.assert_called_once_with(sender, broadcast=True, timeout=find_timeout)
