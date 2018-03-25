# coding: spec

from photons_app.special import SpecialReference, FoundSerials, HardCodedSerials, ResolveReferencesFromFile
from photons_app.errors import PhotonsAppError, DevicesNotFound
from photons_app.test_helpers import AsyncTestCase
from photons_app import helpers as hp

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
import asynctest
import binascii
import asyncio
import mock
import os

describe AsyncTestCase, "SpecialReference":
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

    describe "broadcast_address":
        async before_each:
            self.ref = SpecialReference()

            self.default_broadcast = mock.Mock(name="default_broadcast")
            self.afr = mock.Mock(name="afr", default_broadcast=self.default_broadcast)

        async it "uses default_broadcast if True":
            self.assertIs(self.ref.broadcast_address(self.afr, True), self.default_broadcast)

        async it "uses default_broadcast if False":
            self.assertIs(self.ref.broadcast_address(self.afr, False), self.default_broadcast)

        async it "uses default_broadcast if empty":
            for b in (None, ""):
                self.assertIs(self.ref.broadcast_address(self.afr, b), self.default_broadcast)

        async it "uses broadcast otherwise":
            b = "255.255.255.255"
            self.assertIs(self.ref.broadcast_address(self.afr, b), b)

    describe "find":
        async before_each:
            self.afr = mock.Mock(name="afr")
            self.broadcast = mock.Mock(name="broadcast")
            self.find_timeout = mock.Mock(name="find_timeout")

        async it "transfers cancellation from find_serials":
            class Finder(SpecialReference):
                async def find_serials(s, afr, broadcast, find_timeout):
                    f = asyncio.Future()
                    f.cancel()
                    return await f

            ref = Finder()
            with self.fuzzyAssertRaisesError(asyncio.CancelledError):
                await ref.find(self.afr, self.broadcast, self.find_timeout)

        async it "transfers exceptions from find_serials":
            class Finder(SpecialReference):
                async def find_serials(s, afr, broadcast, find_timeout):
                    f = asyncio.Future()
                    f.set_exception(PhotonsAppError("FIND SERIALS BAD"))
                    return await f

            ref = Finder()
            with self.fuzzyAssertRaisesError(PhotonsAppError, "FIND SERIALS BAD"):
                await ref.find(self.afr, self.broadcast, self.find_timeout)

        async it "transfers result from find_serials":
            serial1 = "d073d5000001"
            serial2 = "d073d5000002"

            target1 = binascii.unhexlify(serial1)
            target2 = binascii.unhexlify(serial2)

            services1 = mock.Mock(name='services1')
            services2 = mock.Mock(name="services2")

            class Finder(SpecialReference):
                async def find_serials(s, afr, broadcast, find_timeout):
                    return {target1: services1, target2: services2}

            ref = Finder()
            found, serials = await ref.find(self.afr, self.broadcast, self.find_timeout)
            self.assertEqual(found, {target1: services1, target2: services2})
            self.assertEqual(serials, [serial1, serial2])

        async it "only calls find_serials once":
            serial = "d073d5000001"
            target = binascii.unhexlify(serial)
            services = mock.Mock(name='services')

            called = []

            class Finder(SpecialReference):
                async def find_serials(s, afr, broadcast, find_timeout):
                    await asyncio.sleep(0.2)
                    called.append(1)
                    return {target: services}

            ref = Finder()
            futs = []
            futs.append(hp.async_as_background(ref.find(self.afr, self.broadcast, self.find_timeout)))
            futs.append(hp.async_as_background(ref.find(self.afr, self.broadcast, self.find_timeout)))
            await asyncio.sleep(0.05)
            futs.append(hp.async_as_background(ref.find(self.afr, self.broadcast, self.find_timeout)))
            await asyncio.sleep(0.2)
            futs.append(hp.async_as_background(ref.find(self.afr, self.broadcast, self.find_timeout)))

            for t in futs:
                found, serials = await t
                self.assertEqual(found, {target: services})
                self.assertEqual(serials, [serial])

            self.assertEqual(called, [1])

            ref.reset()
            found, serials = await ref.find(self.afr, self.broadcast, self.find_timeout)
            self.assertEqual(found, {target: services})
            self.assertEqual(serials, [serial])
            self.assertEqual(called, [1, 1])

describe AsyncTestCase, "FoundSerials":
    async it "calls afr.find_devices with calculated broadcast_address":
        found = mock.Mock(name="found")
        address = mock.Mock(name="address")

        broadcast_address = mock.Mock(name="broadcast_address", return_value=address)

        afr = mock.Mock(name="afr")
        afr.find_devices = asynctest.mock.CoroutineMock(name="find_devices", return_value=found)

        broadcast = mock.Mock(name="broadcast")
        find_timeout = mock.Mock(name="find_timeout")

        ref = FoundSerials()
        with mock.patch.object(ref, "broadcast_address", broadcast_address):
            res = await self.wait_for(ref.find_serials(afr, broadcast, find_timeout))

        self.assertEqual(res, found)

        broadcast_address.assert_called_once_with(afr, broadcast)
        afr.find_devices.assert_called_once_with(address, raise_on_none=True, timeout=find_timeout)

describe AsyncTestCase, "HardCodedSerials":
    async it "takes in a list of serials":
        serials = "d073d5000001,d073d5000002"
        wanted = [binascii.unhexlify(ref) for ref in serials.split(",")]

        afr = mock.Mock(name="afr")
        broadcast = mock.Mock(name="broadcast")
        find_timeout = mock.Mock(name="find_timeout")

        for s in (serials, serials.split(",")):
            ref = HardCodedSerials(s)
            self.assertEqual(ref.targets, wanted)

    async it "keeps searching until it finds all the devices":
        serials = "d073d5000001,d073d5000002"
        wanted = [binascii.unhexlify(ref) for ref in serials.split(",")]

        service0 = mock.Mock(name="service0")
        service1 = mock.Mock(name="service1")

        address = mock.Mock(name="address")
        broadcast_address = mock.Mock(name="broadcast_address", return_value=address)

        afr = mock.Mock(name="afr")

        founds = [
              {wanted[0]: service0}
            , {wanted[1]: service0}
            , {wanted[0]: service0, wanted[1]: service1}
            ]

        def find_devices(*args, **kwargs):
            return founds.pop(0)
        afr.find_devices = asynctest.mock.CoroutineMock(name="find_devices", side_effect=find_devices)

        broadcast = mock.Mock(name="broadcast")

        ref = HardCodedSerials(serials)
        with mock.patch.object(ref, "broadcast_address", broadcast_address):
            res = await self.wait_for(ref.find_serials(afr, broadcast, 10))

        self.assertEqual(res, {wanted[0]: service0, wanted[1]: service1})

        broadcast_address.assert_called_once_with(afr, broadcast)
        self.assertEqual(afr.find_devices.mock_calls
            , [ mock.call(address, raise_on_none=False, timeout=10)
              , mock.call(address, raise_on_none=False, timeout=10)
              , mock.call(address, raise_on_none=False, timeout=10)
              ]
            )

    async it "stops after timeout":
        serials = "d073d5000001,d073d5000002"
        wanted = [binascii.unhexlify(ref) for ref in serials.split(",")]

        service0 = mock.Mock(name="service0")
        service1 = mock.Mock(name="service1")

        address = mock.Mock(name="address")
        broadcast_address = mock.Mock(name="broadcast_address", return_value=address)

        afr = mock.Mock(name="afr")

        async def find_devices(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {wanted[0]: service0}
        afr.find_devices = asynctest.mock.CoroutineMock(name="find_devices", side_effect=find_devices)

        broadcast = mock.Mock(name="broadcast")

        ref = HardCodedSerials(serials)
        with self.fuzzyAssertRaisesError(DevicesNotFound, missing=["d073d5000002"]):
            with mock.patch.object(ref, "broadcast_address", broadcast_address):
                res = await self.wait_for(ref.find_serials(afr, broadcast, 0.1))

        broadcast_address.assert_called_once_with(afr, broadcast)
        self.assertGreater(len(afr.find_devices.mock_calls), 0)

describe AsyncTestCase, "ResolveReferencesFromFile":
    async it "complains if filename can't be read or is empty":
        with hp.a_temp_file() as fle:
            fle.close()
            os.remove(fle.name)

            with self.fuzzyAssertRaisesError(PhotonsAppError, "Failed to read serials from a file"):
                ResolveReferencesFromFile(fle.name)

        with hp.a_temp_file() as fle:
            fle.close()
            with self.fuzzyAssertRaisesError(PhotonsAppError, "Found no serials in file"):
                ResolveReferencesFromFile(fle.name)

    async it "creates and uses a HardCodedSerials":
        serial1 = "d073d5000001"
        serial2 = "d073d5000002"

        resolver = mock.Mock(name="resolver")
        resolver.find = asynctest.mock.CoroutineMock(name="find")
        FakeHardCodedSerials = mock.Mock(name="HardCodedSerials", return_value=resolver)

        with hp.a_temp_file() as fle:
            fle.write("{}\n{}".format(serial1, serial2).encode())
            fle.close()

            with mock.patch("photons_app.special.HardCodedSerials", FakeHardCodedSerials):
                r = ResolveReferencesFromFile(fle.name)

        self.assertEqual(r.reference, resolver)
        FakeHardCodedSerials.assert_called_once_with([serial1, serial2])

        self.assertEqual(len(resolver.reset.mock_calls), 0)
        r.reset()
        resolver.reset.assert_called_once_with()

        afr = mock.Mock(name="afr")
        broadcast = mock.Mock(name='broadcast')
        find_timeout = mock.Mock(name='find_timeout')
        self.assertEqual(len(resolver.find.mock_calls), 0)

        res = mock.Mock(name="res")
        resolver.find.return_value = res
        self.assertIs(await self.wait_for(r.find(afr, broadcast, find_timeout)), res)
        resolver.find.assert_called_once_with(afr, broadcast, find_timeout)
