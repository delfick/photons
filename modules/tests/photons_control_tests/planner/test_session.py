# coding: spec

import uuid
from unittest import mock

import pytest
from photons_app import helpers as hp
from photons_control.planner.gatherer import Planner, Session


@pytest.fixture()
def session():
    return Session()


def Information(key):
    class Information:
        remote_addr = None
        sender_message = mock.Mock(name="sender_message", Key=key)

    return Information


describe "Session":
    it "has received and filled", session:
        assert hasattr(session, "received")
        assert hasattr(session, "filled")

        key = str(uuid.uuid4())
        d = session.received[key]
        assert isinstance(d, dict)

        key2 = str(uuid.uuid4())
        l = d[key2]
        assert isinstance(l, list)

        key3 = str(uuid.uuid4())
        d = session.filled[key3]
        assert isinstance(d, dict)

    it "can make a planner", session:
        plans = mock.Mock(name="plans")
        serial = mock.Mock(name="serial")
        depinfo = mock.Mock(name="depinfo")
        error_catcher = mock.Mock(name="error_catcher")
        planner = session.planner(plans, depinfo, serial, error_catcher)

        assert isinstance(planner, Planner)
        assert planner.session is session
        assert planner.plans is plans
        assert planner.depinfo is depinfo
        assert planner.serial is serial
        assert planner.error_catcher is error_catcher

    it "can add received packets", session:
        t1 = mock.Mock(name="t1")
        t2 = mock.Mock(name="t2")
        t3 = mock.Mock(name="t3")
        t4 = mock.Mock(name="t4")
        ts = [t1, t2, t3, t4]

        def time():
            return ts.pop(0)

        t = mock.Mock(name="time", side_effect=time)

        key = str(uuid.uuid4())
        serial = "d073d5000001"
        pkt1 = mock.Mock(name="pkt1", serial=serial, Information=Information(key))
        pkt2 = mock.Mock(name="pkt2", serial=serial, Information=Information(key))

        assert session.received == {}

        with mock.patch("time.time", t):
            session.receive(pkt1)
            assert session.received[serial][key] == [(t1, pkt1)]

            session.receive(pkt2)
            assert session.received[serial][key] == [(t1, pkt1), (t2, pkt2)]

        serial2 = "d073d5000002"
        pkt3 = mock.Mock(name="pkt3", serial=serial2, Information=Information(key))

        with mock.patch("time.time", t):
            assert session.received[serial][key] == [(t1, pkt1), (t2, pkt2)]

            session.receive(pkt3)
            assert session.received[serial][key] == [(t1, pkt1), (t2, pkt2)]
            assert session.received[serial2][key] == [(t3, pkt3)]

        key2 = str(uuid.uuid4())
        pkt4 = mock.Mock(name="pkt4", serial=serial, Information=Information(key2))

        with mock.patch("time.time", t):
            session.receive(pkt4)
            assert session.received[serial][key2] == [(t4, pkt4)]

        assert session.received == {
            serial: {key: [(t1, pkt1), (t2, pkt2)], key2: [(t4, pkt4)]},
            serial2: {key: [(t3, pkt3)]},
        }

    it "can fill results", session:
        t1 = mock.Mock(name="t1")
        t2 = mock.Mock(name="t2")
        t3 = mock.Mock(name="t3")
        t4 = mock.Mock(name="t4")
        ts = [t1, t2, t3, t4]

        def time():
            return ts.pop(0)

        t = mock.Mock(name="time", side_effect=time)

        plankey = str(uuid.uuid4())
        serial = "d073d5000001"
        result = mock.Mock(name="result")
        result2 = mock.Mock(name="result2")

        assert session.filled == {}

        with mock.patch("time.time", t):
            session.fill(plankey, serial, result)
            assert session.filled == {plankey: {serial: (t1, result)}}

            session.fill(plankey, serial, result2)
            assert session.filled == {plankey: {serial: (t2, result2)}}

        serial2 = "d073d5000002"
        with mock.patch("time.time", t):
            session.fill(plankey, serial2, result)
            assert session.filled == {plankey: {serial: (t2, result2), serial2: (t3, result)}}

        plankey2 = str(uuid.uuid4())
        serial3 = "d073d5000003"
        result3 = mock.Mock(name="result3")

        with mock.patch("time.time", t):
            session.fill(plankey2, serial3, result3)
            assert session.filled == {
                plankey: {serial: (t2, result2), serial2: (t3, result)},
                plankey2: {serial3: (t4, result3)},
            }

    describe "completed":
        it "returns result if we have one", session:
            plankey = str(uuid.uuid4())
            serial = "d073d5000001"
            serial2 = "d073d5000002"
            result = mock.Mock(name="result")

            assert session.completed(plankey, serial) is None
            assert session.completed(plankey, serial2) is None

            session.fill(plankey, serial, result)
            assert session.completed(plankey, serial) is result

            assert session.completed(plankey, serial2) is None

    describe "has_received":
        it "says whether we have results for that serial and key", session:
            key = str(uuid.uuid4())
            key2 = str(uuid.uuid4())
            serial = "d073d5000001"
            serial2 = "d073d5000002"
            pkt1 = mock.Mock(name="pkt1", serial=serial, Information=Information(key))

            assert not session.has_received(key, serial)
            assert not session.has_received(key, serial2)
            assert not session.has_received(key2, serial2)

            session.receive(pkt1)

            assert session.has_received(key, serial)
            assert not session.has_received(key, serial2)
            assert not session.has_received(key2, serial2)

    describe "known_packets":
        it "yields known packets for this serial", session:
            key = str(uuid.uuid4())
            key2 = str(uuid.uuid4())

            serial = "d073d5000001"
            serial2 = "d073d5000002"

            pkt1 = mock.Mock(name="pkt1", serial=serial, Information=Information(key))
            pkt2 = mock.Mock(name="pkt2", serial=serial, Information=Information(key))
            pkt3 = mock.Mock(name="pkt3", serial=serial2, Information=Information(key2))
            pkt4 = mock.Mock(name="pkt4", serial=serial, Information=Information(key2))
            pkt5 = mock.Mock(name="pkt5", serial=serial2, Information=Information(key2))

            assert list(session.known_packets(serial)) == []
            assert list(session.known_packets(serial2)) == []

            session.receive(pkt1)
            session.receive(pkt2)
            session.receive(pkt3)
            session.receive(pkt4)
            session.receive(pkt5)

            ls = list(session.known_packets(serial))
            assert ls == [pkt1, pkt2, pkt4]

            ls = list(session.known_packets(serial2))
            assert ls == [pkt3, pkt5]

    describe "refresh_received":

        @pytest.fixture()
        def V(self, fake_time, session):
            class V:
                key1 = str(uuid.uuid4())
                key2 = str(uuid.uuid4())

                serial1 = "d073d5000001"
                serial2 = "d073d5000002"

                def add(s, n, l, *, t, k):
                    key = getattr(s, f"key{k}")

                    pkt = mock.Mock(
                        name=f"pkt{n}{l}{k}",
                        serial=getattr(s, f"serial{n}"),
                        Information=Information(key),
                    )
                    setattr(s, f"pkt{n}{l}{k}", pkt)

                    fake_time.set(t)
                    session.receive(pkt)

                @hp.memoized_property
                def starting_received(s):
                    return {
                        s.serial1: {
                            s.key1: [(1, s.pkt1a1), (10, s.pkt1b1), (15, s.pkt1c1)],
                            s.key2: [(1, s.pkt1a2), (5, s.pkt1b2), (20, s.pkt1c2)],
                        },
                        s.serial2: {
                            s.key1: [(10, s.pkt2a1), (12, s.pkt2b1), (13, s.pkt2c1)],
                            s.key2: [(5, s.pkt2a2), (5, s.pkt2b2), (5, s.pkt2c2)],
                        },
                    }

                def __init__(s):
                    s.add(1, "a", t=1, k=1)
                    s.add(1, "b", t=10, k=1)
                    s.add(1, "c", t=15, k=1)

                    s.add(1, "a", t=1, k=2)
                    s.add(1, "b", t=5, k=2)
                    s.add(1, "c", t=20, k=2)

                    s.add(2, "a", t=10, k=1)
                    s.add(2, "b", t=12, k=1)
                    s.add(2, "c", t=13, k=1)

                    s.add(2, "a", t=5, k=2)
                    s.add(2, "b", t=5, k=2)
                    s.add(2, "c", t=5, k=2)

                    assert session.received == s.starting_received

            return V()

        it "does nothing if refresh is False", session, V:
            session.refresh_received(V.key1, V.serial1, False)
            assert session.received == V.starting_received

        it "does nothing if serial not in received", session, V:
            session.refresh_received(V.key1, "not here", 1)
            assert session.received == V.starting_received

        it "does nothing if key not in received", session, V:
            session.refresh_received("not here", V.serial1, 1)
            assert session.received == V.starting_received

        it "removes everything if refresh is 0", session, V:
            session.refresh_received(V.key1, V.serial1, 0)
            assert session.received == {
                V.serial1: {V.key2: [(1, V.pkt1a2), (5, V.pkt1b2), (20, V.pkt1c2)]},
                V.serial2: {
                    V.key1: [(10, V.pkt2a1), (12, V.pkt2b1), (13, V.pkt2c1)],
                    V.key2: [(5, V.pkt2a2), (5, V.pkt2b2), (5, V.pkt2c2)],
                },
            }

            session.refresh_received(V.key2, V.serial2, 0)
            assert session.received == {
                V.serial1: {V.key2: [(1, V.pkt1a2), (5, V.pkt1b2), (20, V.pkt1c2)]},
                V.serial2: {V.key1: [(10, V.pkt2a1), (12, V.pkt2b1), (13, V.pkt2c1)]},
            }

        it "removes everything if refresh is True", session, V:
            session.refresh_received(V.key1, V.serial1, True)
            assert session.received == {
                V.serial1: {V.key2: [(1, V.pkt1a2), (5, V.pkt1b2), (20, V.pkt1c2)]},
                V.serial2: {
                    V.key1: [(10, V.pkt2a1), (12, V.pkt2b1), (13, V.pkt2c1)],
                    V.key2: [(5, V.pkt2a2), (5, V.pkt2b2), (5, V.pkt2c2)],
                },
            }

            session.refresh_received(V.key2, V.serial2, True)
            assert session.received == {
                V.serial1: {V.key2: [(1, V.pkt1a2), (5, V.pkt1b2), (20, V.pkt1c2)]},
                V.serial2: {V.key1: [(10, V.pkt2a1), (12, V.pkt2b1), (13, V.pkt2c1)]},
            }

        it "removes anything older than refresh seconds", session, fake_time, V:
            fake_time.set(16)
            session.refresh_received(V.key1, V.serial1, 6)
            assert session.received == {
                V.serial1: {
                    V.key1: [(10, V.pkt1b1), (15, V.pkt1c1)],
                    V.key2: V.starting_received[V.serial1][V.key2],
                },
                V.serial2: V.starting_received[V.serial2],
            }

            fake_time.set(21)
            session.refresh_received(V.key1, V.serial1, 6)

            assert session.received == {
                V.serial1: {
                    V.key1: [(15, V.pkt1c1)],
                    V.key2: V.starting_received[V.serial1][V.key2],
                },
                V.serial2: V.starting_received[V.serial2],
            }

            session.refresh_received(V.key1, V.serial1, 5)

            assert session.received == {
                V.serial1: {V.key2: V.starting_received[V.serial1][V.key2]},
                V.serial2: V.starting_received[V.serial2],
            }

            session.refresh_received(V.key1, V.serial1, 4)

            assert session.received == {
                V.serial1: {V.key2: V.starting_received[V.serial1][V.key2]},
                V.serial2: V.starting_received[V.serial2],
            }

            session.refresh_received(V.key2, V.serial2, 10)

            assert session.received == {
                V.serial1: {V.key2: V.starting_received[V.serial1][V.key2]},
                V.serial2: {V.key1: V.starting_received[V.serial2][V.key1]},
            }

    describe "refresh_filled":

        @pytest.fixture()
        def V(self, session, fake_time):
            class V:
                plankeya = str(uuid.uuid4())
                plankeyb = str(uuid.uuid4())

                serial1 = "d073d5000001"
                serial2 = "d073d5000002"

                result1a = mock.Mock(name="result1a")
                result1b = mock.Mock(name="result1b")
                result2a = mock.Mock(name="result2a")
                result2b = mock.Mock(name="result2b")

                @hp.memoized_property
                def starting_filled(s):
                    return {
                        s.plankeya: {s.serial1: (1, s.result1a), s.serial2: (2, s.result2a)},
                        s.plankeyb: {s.serial1: (5, s.result1b), s.serial2: (10, s.result2b)},
                    }

                def __init__(s):
                    fake_time.set(1)
                    session.fill(s.plankeya, s.serial1, s.result1a)

                    fake_time.set(2)
                    session.fill(s.plankeya, s.serial2, s.result2a)

                    fake_time.set(5)
                    session.fill(s.plankeyb, s.serial1, s.result1b)

                    fake_time.set(10)
                    session.fill(s.plankeyb, s.serial2, s.result2b)

                    assert session.filled == s.starting_filled

            return V()

        it "does nothing if refresh is False", session, V:
            session.refresh_filled(V.plankeya, V.serial1, False)
            assert session.filled == V.starting_filled

        it "does nothing if plankey not there", session, V:
            session.refresh_filled("not there", V.serial1, 1)
            assert session.filled == V.starting_filled

        it "does nothing if serial not there", session, V:
            session.refresh_filled(V.plankeya, "not there", 1)
            assert session.filled == V.starting_filled

        it "removes result if refresh is True or 0", session, V:
            session.refresh_filled(V.plankeya, V.serial1, True)
            assert session.filled == {
                V.plankeya: {V.serial2: session.filled[V.plankeya][V.serial2]},
                V.plankeyb: session.filled[V.plankeyb],
            }

            session.refresh_filled(V.plankeya, V.serial2, 0)
            assert session.filled == {V.plankeyb: session.filled[V.plankeyb]}

        it "removes result if been refresh seconds", session, fake_time, V:
            fake_time.set(6)
            session.refresh_filled(V.plankeyb, V.serial1, 2)
            assert session.filled == V.starting_filled

            session.refresh_filled(V.plankeyb, V.serial1, 1)

            assert session.filled == {
                V.plankeya: session.filled[V.plankeya],
                V.plankeyb: {V.serial2: session.filled[V.plankeyb][V.serial2]},
            }

            fake_time.set(20)
            session.refresh_filled(V.plankeyb, V.serial2, 5)

            assert session.filled == {V.plankeya: session.filled[V.plankeya]}
