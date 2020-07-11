# coding: spec

from photons_app.special import (
    SpecialReference,
    FoundSerials,
    HardCodedSerials,
    ResolveReferencesFromFile,
)
from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from delfick_project.errors_pytest import assertRaises
from unittest import mock
import binascii
import asyncio
import pytest
import os

describe "SpecialReference":
    async it "gives itself a finding and found future":
        ref = SpecialReference()
        assert isinstance(ref.finding, hp.ResettableFuture)
        assert isinstance(ref.found, hp.ResettableFuture)

    async it "can reset the futures":
        ref = SpecialReference()
        ref.finding.set_result(True)
        ref.found.set_result(True)

        assert ref.finding.done()
        assert ref.found.done()
        ref.reset()

        assert not ref.finding.done()
        assert not ref.found.done()

    describe "find":

        @pytest.fixture()
        def V(self):
            class V:
                sender = mock.Mock(name="sender")
                broadcast = mock.Mock(name="broadcast")
                find_timeout = mock.Mock(name="find_timeout")

            return V()

        async it "transfers cancellation from find_serials", V:

            class Finder(SpecialReference):
                async def find_serials(s, sender, *, timeout, broadcast=True):
                    f = hp.create_future()
                    f.cancel()
                    return await f

            ref = Finder()
            with assertRaises(asyncio.CancelledError):
                await ref.find(V.sender, timeout=V.find_timeout)

        async it "transfers exceptions from find_serials", V:

            class Finder(SpecialReference):
                async def find_serials(s, sender, *, timeout, broadcast=True):
                    f = hp.create_future()
                    f.set_exception(PhotonsAppError("FIND SERIALS BAD"))
                    return await f

            ref = Finder()
            with assertRaises(PhotonsAppError, "FIND SERIALS BAD"):
                await ref.find(V.sender, timeout=V.find_timeout)

        async it "transfers result from find_serials", V:
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

        async it "only calls find_serials once", V:
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

describe "FoundSerials":
    async it "calls sender.find_devices with broadcast":
        found = mock.Mock(name="found")

        sender = mock.Mock(name="sender")
        sender.find_devices = pytest.helpers.AsyncMock(name="find_devices", return_value=found)

        broadcast = mock.Mock(name="broadcast")
        find_timeout = mock.Mock(name="find_timeout")

        ref = FoundSerials()
        res = await ref.find_serials(sender, broadcast=broadcast, timeout=find_timeout)

        assert res == found
        sender.find_devices.assert_called_once_with(
            broadcast=broadcast, raise_on_none=True, timeout=find_timeout
        )

describe "HardCodedSerials":

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

    async it "takes in a list of serials":
        serials = "d073d5000001,d073d500000200"
        wanted = [binascii.unhexlify(ref)[:6] for ref in serials.split(",")]

        for s in (serials, serials.split(",")):
            ref = HardCodedSerials(s)
            assert ref.targets == wanted
            assert ref.serials == ["d073d5000001", "d073d5000002"]

    async it "can take in list of unhexlified serials":
        serials = [binascii.unhexlify("d073d500000100"), binascii.unhexlify("d073d5000002")]
        wanted = [binascii.unhexlify(ref)[:6] for ref in ["d073d5000001", "d073d5000002"]]

        ref = HardCodedSerials(serials)
        assert ref.targets == wanted
        assert ref.serials == ["d073d5000001", "d073d5000002"]

    describe "find_serials":

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

            sender.find_specific_serials.assert_called_once_with(
                serials, broadcast=broadcast, raise_on_none=False, timeout=find_timeout
            )

            assert ref.missing(f) == missing

        async it "uses find_specific_serials", V:
            found = {V.target1: V.info1, V.target2: V.info2}
            serials = [V.serial1, V.serial2]
            expected = {V.target1: V.info1, V.target2: V.info2}
            missing = []
            await self.assertFindSerials(found, serials, expected, missing)

        async it "only returns from the serials it cares about", V:
            found = {V.target1: V.info1, V.target2: V.info2}
            serials = [V.serial1]
            expected = {V.target1: V.info1}
            missing = []
            await self.assertFindSerials(found, serials, expected, missing)

        async it "doesn't call to find_specific_serials if the serials are already on the sender", V:
            broadcast = mock.Mock(name="broadcast")
            find_timeout = mock.Mock(name="find_timeout")

            sender = mock.Mock(name="sender")
            sender.found = {V.target1: V.info1, V.target2: V.info2}
            sender.find_specific_serials = pytest.helpers.AsyncMock(
                name="find_specific_serials", side_effect=AssertionError("Shouldn't be called")
            )

            ref = HardCodedSerials([V.serial1])
            f = await ref.find_serials(sender, broadcast=broadcast, timeout=find_timeout)

            assert f == {V.target1: V.info1}
            assert ref.missing(f) == []

        async it "doesn't care if no found", V:
            found = {}
            serials = [V.serial1, V.serial2]
            expected = {}
            missing = [V.serial1, V.serial2]
            await self.assertFindSerials(found, serials, expected, missing)

        async it "can see partial missing", V:
            found = {V.target2: V.info2}
            serials = [V.serial1, V.serial2]
            expected = {V.target2: V.info2}
            missing = [V.serial1]
            await self.assertFindSerials(found, serials, expected, missing)

describe "ResolveReferencesFromFile":
    async it "complains if filename can't be read or is empty":
        with hp.a_temp_file() as fle:
            fle.close()
            os.remove(fle.name)

            with assertRaises(PhotonsAppError, "Failed to read serials from a file"):
                ResolveReferencesFromFile(fle.name)

        with hp.a_temp_file() as fle:
            fle.close()
            with assertRaises(PhotonsAppError, "Found no serials in file"):
                ResolveReferencesFromFile(fle.name)

    async it "creates and uses a HardCodedSerials":
        serial1 = "d073d5000001"
        serial2 = "d073d5000002"

        resolver = mock.Mock(name="resolver")
        resolver.find = pytest.helpers.AsyncMock(name="find")
        FakeHardCodedSerials = mock.Mock(name="HardCodedSerials", return_value=resolver)

        with hp.a_temp_file() as fle:
            fle.write("{}\n{}".format(serial1, serial2).encode())
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
