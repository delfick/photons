import binascii
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from photons_transport.comms.base import Found


@pytest.fixture()
def found():
    return Found()


class TestFound:
    def test_it_starts_empty(self, found):
        assert found.found == {}
        assert not found
        assert len(found) == 0
        assert found.serials == []
        assert found == Found()
        assert list(found) == []

    def test_it_can_be_cloned(self):
        found = Found()
        found["d073d5000001"] = {"one": 1, "two": 2}
        found["d073d5000002"] = {"three": 3, "four": 4}

        def h(serial):
            return binascii.unhexlify(serial)[:6]

        found2 = found.clone()
        del found2["d073d5000001"]["one"]
        assert found.found == {
            h("d073d5000001"): {"one": 1, "two": 2},
            h("d073d5000002"): {"three": 3, "four": 4},
        }

        assert found2.found == {
            h("d073d5000001"): {"two": 2},
            h("d073d5000002"): {"three": 3, "four": 4},
        }

        del found2["d073d5000002"]
        assert found.found == {
            h("d073d5000001"): {"one": 1, "two": 2},
            h("d073d5000002"): {"three": 3, "four": 4},
        }

        assert found2.found == {h("d073d5000001"): {"two": 2}}

    def test_it_can_cleanse_a_serial(self, found):
        def assertCleansed(i, o):
            assert found.cleanse_serial(i) == o

        assertCleansed("d073d5000001", binascii.unhexlify("d073d5000001")[:6])
        assertCleansed("d073d500000111", binascii.unhexlify("d073d5000001")[:6])
        assertCleansed(binascii.unhexlify("d073d5000001"), binascii.unhexlify("d073d5000001")[:6])
        assertCleansed(binascii.unhexlify("d073d500000111"), binascii.unhexlify("d073d5000001")[:6])

    def test_it_can_have_serials(self, found):
        found["d073d5000001"] = 1
        found["d073d500000222"] = 2
        found[binascii.unhexlify("d073d5000003")] = 3
        found[binascii.unhexlify("d073d500000455")] = 4

        assert len(found) == 4
        assert found

        assert found.serials == [
            "d073d5000001",
            "d073d5000002",
            "d073d5000003",
            "d073d5000004",
        ]

        assert list(found) == [
            binascii.unhexlify("d073d5000001"),
            binascii.unhexlify("d073d5000002"),
            binascii.unhexlify("d073d5000003"),
            binascii.unhexlify("d073d5000004"),
        ]

        otherfound = Found()
        assert found != otherfound

        otherfound["d073d5000001"] = 1
        otherfound["d073d5000002"] = 2
        otherfound["d073d5000003"] = 3
        otherfound["d073d5000004"] = 4
        assert found == otherfound

        otherfound["d073d5000004"] = 5
        assert found != otherfound

        found["d073d5000005"] = 6
        assert len(found) == 5

    def test_it_has_getitem(self, found):
        with assertRaises(KeyError):
            found["d073d5000001"]

        services = mock.Mock(name="services")
        found["d073d5000001"] = services

        assert found["d073d5000001"] is services
        assert found["d073d500000111"] is services
        assert found[binascii.unhexlify("d073d5000001")] is services
        assert found[binascii.unhexlify("d073d500000122")] is services

    def test_it_has_setitem(self, found):
        found["d073d5000001"] = 1
        assert found["d073d5000001"] == 1

        found["d073d500000122"] = 2
        assert found["d073d5000001"] == 2

        found[binascii.unhexlify("d073d500000122")] = 3
        assert found["d073d5000001"] == 3

        found[binascii.unhexlify("d073d5000001")] = 4
        assert found["d073d5000001"] == 4

    def test_it_has_delitem(self, found):
        ts = [
            "d073d5000001",
            "d073d500000111",
            binascii.unhexlify("d073d5000001"),
            binascii.unhexlify("d073d500000133"),
        ]

        for t in ts:
            with assertRaises(KeyError):
                found["d073d5000001"]

            found["d073d5000001"] = 1
            assert found["d073d5000001"] == 1

            del found[t]

            with assertRaises(KeyError):
                found["d073d5000001"]

    def test_it_has_contains(self, found):
        ts = [
            "d073d5000001",
            "d073d500000111",
            binascii.unhexlify("d073d5000001"),
            binascii.unhexlify("d073d500000133"),
        ]

        for t in ts:
            assert t not in found

        found["d073d5000001"] = 1

        for t in ts:
            assert t in found

        # And it's not "in" found if the services are empty
        found["d073d5000001"] = {}

        for t in ts:
            assert t not in found

    def test_it_has_repr(self, found):
        found["d073d5000001"] = {"UDP": 1, "THI": 2}
        found["d073d5000002"] = {"MEMORY": 1}

        assert repr(found) == """<FOUND: {"d073d5000001": "'UDP','THI'", "d073d5000002": "'MEMORY'"}>"""

    def test_it_can_borrow_found(self, found):
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

        found["d073d5000001"] = {"UDP": t1, "THI": t2}
        found["d073d5000002"] = {"MEM": t3, "OTH": t4}

        otherfound = Found()
        otherfound["d073d5000002"] = {"OTH": t5}

        sender = mock.Mock(name="sender")
        otherfound.borrow(found, sender)

        assert otherfound.serials == ["d073d5000001", "d073d5000002"]
        assert otherfound["d073d5000001"] == {"UDP": t1clone, "THI": t2clone}

        assert otherfound["d073d5000002"] == {"MEM": t3clone, "OTH": t5}

        t1.clone_for.assert_called_once_with(sender)
        t2.clone_for.assert_called_once_with(sender)
        t3.clone_for.assert_called_once_with(sender)


class TestFoundremoveLost:
    async def test_it_closes_and_removes_transports_that_are_not_in_found_now(self):
        ts = [
            "d073d5000002",
            "d073d500000211",
            binascii.unhexlify("d073d5000002"),
            binascii.unhexlify("d073d500000233"),
        ]

        for t in ts:
            found = Found()

            t1 = mock.Mock(name="t1")
            t1.close = pytest.helpers.AsyncMock(name="close", side_effect=Exception("NOPE"))

            t2 = mock.Mock(name="t2")
            t2.close = pytest.helpers.AsyncMock(name="close")

            t3 = mock.Mock(name="t3", spec=[])

            found["d073d5000001"] = {"UDP": t1, "THI": t2}
            found["d073d5000002"] = {"MEM": t3}

            assert found.serials == ["d073d5000001", "d073d5000002"]
            await found.remove_lost(set([t]))
            assert found.serials == ["d073d5000002"]

            t1.close.assert_called_once_with()
            t2.close.assert_called_once_with()
