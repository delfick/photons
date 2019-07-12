# coding: spec

from photons_transport.comms.base import Found

from photons_app.test_helpers import TestCase, AsyncTestCase, with_timeout

from noseOfYeti.tokeniser.support import noy_sup_setUp
from unittest import mock
import asynctest
import binascii

describe TestCase, "Found":
    before_each:
        self.found = Found()

    it "starts empty":
        self.assertEqual(self.found.found, {})
        assert not self.found
        self.assertEqual(len(self.found), 0)
        self.assertEqual(self.found.serials, [])
        assert self.found == Found()
        self.assertEqual(list(self.found), [])

    it "can cleanse a serial":
        def assertCleansed(i, o):
            self.assertEqual(self.found.cleanse_serial(i), o)

        assertCleansed("d073d5000001", binascii.unhexlify("d073d5000001")[:6])
        assertCleansed("d073d500000111", binascii.unhexlify("d073d5000001")[:6])
        assertCleansed(binascii.unhexlify("d073d5000001"), binascii.unhexlify("d073d5000001")[:6])
        assertCleansed(binascii.unhexlify("d073d500000111"), binascii.unhexlify("d073d5000001")[:6])

    it "can have serials":
        self.found["d073d5000001"] = 1
        self.found["d073d500000222"] = 2
        self.found[binascii.unhexlify("d073d5000003")] = 3
        self.found[binascii.unhexlify("d073d500000455")] = 4

        self.assertEqual(len(self.found), 4)
        assert self.found

        self.assertEqual(self.found.serials
            , [ "d073d5000001"
              , "d073d5000002"
              , "d073d5000003"
              , "d073d5000004"
              ]
            )

        self.assertEqual(list(self.found)
            , [ binascii.unhexlify("d073d5000001")
              , binascii.unhexlify("d073d5000002")
              , binascii.unhexlify("d073d5000003")
              , binascii.unhexlify("d073d5000004")
              ]
            )

        otherfound = Found()
        self.assertNotEqual(self.found, otherfound)

        otherfound["d073d5000001"] = 1
        otherfound["d073d5000002"] = 2
        otherfound["d073d5000003"] = 3
        otherfound["d073d5000004"] = 4
        self.assertEqual(self.found, otherfound) 

        otherfound["d073d5000004"] = 5
        self.assertNotEqual(self.found, otherfound) 

        self.found["d073d5000005"] = 6
        self.assertEqual(len(self.found), 5)

    it "has getitem":
        with self.fuzzyAssertRaisesError(KeyError):
            self.found["d073d5000001"]

        services = mock.Mock(name="services")
        self.found["d073d5000001"] = services

        self.assertIs(self.found["d073d5000001"], services)
        self.assertIs(self.found["d073d500000111"], services)
        self.assertIs(self.found[binascii.unhexlify("d073d5000001")], services)
        self.assertIs(self.found[binascii.unhexlify("d073d500000122")], services)

    it "has setitem":
        self.found["d073d5000001"] = 1
        self.assertEqual(self.found["d073d5000001"], 1)

        self.found["d073d500000122"] = 2
        self.assertEqual(self.found["d073d5000001"], 2)

        self.found[binascii.unhexlify("d073d500000122")] = 3
        self.assertEqual(self.found["d073d5000001"], 3)

        self.found[binascii.unhexlify("d073d5000001")] = 4
        self.assertEqual(self.found["d073d5000001"], 4)

    it "has delitem":
        ts = [
              "d073d5000001"
            , "d073d500000111"
            , binascii.unhexlify("d073d5000001")
            , binascii.unhexlify("d073d500000133")
            ]

        for t in ts:
            with self.fuzzyAssertRaisesError(KeyError):
                self.found["d073d5000001"]

            self.found["d073d5000001"] = 1
            self.assertEqual(self.found["d073d5000001"], 1)

            del self.found[t]

            with self.fuzzyAssertRaisesError(KeyError):
                self.found["d073d5000001"]

    it "has contains":
        ts = [
              "d073d5000001"
            , "d073d500000111"
            , binascii.unhexlify("d073d5000001")
            , binascii.unhexlify("d073d500000133")
            ]

        for t in ts:
            assert t not in self.found

        self.found["d073d5000001"] = 1

        for t in ts:
            assert t in self.found

    it "has repr":
        self.found["d073d5000001"] = {"UDP": 1, "THI": 2}
        self.found["d073d5000002"] = {"MEMORY": 1}

        self.assertEqual(repr(self.found)
            , """<FOUND: {"d073d5000001": "'UDP','THI'", "d073d5000002": "'MEMORY'"}>"""
            )

    it "can borrow found":
        t1clone = mock.Mock(name="t1clone")
        t1 = mock.Mock(name="t1")
        t1.clone_for.return_value = t1clone

        t2clone = mock.Mock(name="t2clone")
        t2 = mock.Mock(name="t2")
        t2.clone_for.return_value = t2clone

        t3clone = mock.Mock(name="t3clone")
        t3 = mock.Mock(name="t3")
        t3.clone_for.return_value = t3clone

        t4 = mock.Mock(name="t4", spec=[])
        t5 = mock.Mock(name="t5", spec=[])

        self.found["d073d5000001"] = {"UDP": t1, "THI": t2}
        self.found["d073d5000002"] = {"MEM": t3, "OTH": t4}

        otherfound = Found()
        otherfound["d073d5000002"] = {"OTH": t5}

        afr = mock.Mock(name='afr')
        otherfound.borrow(self.found, afr)
        
        self.assertEqual(otherfound.serials, ["d073d5000001", "d073d5000002"])
        self.assertEqual(otherfound["d073d5000001"]
            , {"UDP": t1clone, "THI": t2clone}
            )

        self.assertEqual(otherfound["d073d5000002"]
            , {"MEM": t3clone, "OTH": t5}
            )

        t1.clone_for.assert_called_once_with(afr)
        t2.clone_for.assert_called_once_with(afr)
        t3.clone_for.assert_called_once_with(afr)

describe AsyncTestCase, "Found.remove_lost":
    @with_timeout
    async it "closes and removes transports that are not in found_now":
        ts = [
              "d073d5000002"
            , "d073d500000211"
            , binascii.unhexlify("d073d5000002")
            , binascii.unhexlify("d073d500000233")
            ]

        for t in ts:
            found = Found()

            t1 = mock.Mock(name="t1")
            t1.close = asynctest.mock.CoroutineMock(name="close", side_effect=Exception("NOPE"))

            t2 = mock.Mock(name="t2")
            t2.close = asynctest.mock.CoroutineMock(name="close")

            t3 = mock.Mock(name="t3", spec=[])

            found["d073d5000001"] = {"UDP": t1, "THI": t2}
            found["d073d5000002"] = {"MEM": t3}

            self.assertEqual(found.serials, ["d073d5000001", "d073d5000002"])
            await found.remove_lost(set([t]))
            self.assertEqual(found.serials, ["d073d5000002"])

            t1.close.assert_called_once_with()
            t2.close.assert_called_once_with()
