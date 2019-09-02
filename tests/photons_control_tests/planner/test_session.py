# coding: spec

from photons_control.planner.gatherer import Session, Planner

from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from contextlib import contextmanager
from unittest import mock
import uuid

describe TestCase, "Session":
    before_each:
        self.session = Session()

    it "has received and filled":
        assert hasattr(self.session, "received")
        assert hasattr(self.session, "filled")

        key = str(uuid.uuid4())
        d = self.session.received[key]
        self.assertIsInstance(d, dict)

        key2 = str(uuid.uuid4())
        l = d[key2]
        self.assertIsInstance(l, list)

        key3 = str(uuid.uuid4())
        d = self.session.filled[key3]
        self.assertIsInstance(d, dict)

    it "can make a planner":
        plans = mock.Mock(name="plans")
        serial = mock.Mock(name="serial")
        depinfo = mock.Mock(name="depinfo")
        error_catcher = mock.Mock(name="error_catcher")
        planner = self.session.planner(plans, depinfo, serial, error_catcher)

        self.assertIsInstance(planner, Planner)
        self.assertIs(planner.session, self.session)
        self.assertIs(planner.plans, plans)
        self.assertIs(planner.depinfo, depinfo)
        self.assertIs(planner.serial, serial)
        self.assertIs(planner.error_catcher, error_catcher)

    it "can add received packets":
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
        pkt1 = mock.Mock(name="pkt1", serial=serial)
        pkt2 = mock.Mock(name="pkt2", serial=serial)

        self.assertEqual(self.session.received, {})

        with mock.patch("time.time", t):
            self.session.receive(key, pkt1)
            self.assertEqual(self.session.received[serial][key], [(t1, pkt1)])

            self.session.receive(key, pkt2)
            self.assertEqual(self.session.received[serial][key], [(t1, pkt1), (t2, pkt2)])

        serial2 = "d073d5000002"
        pkt3 = mock.Mock(name="pkt3", serial=serial2)

        with mock.patch("time.time", t):
            self.assertEqual(self.session.received[serial][key], [(t1, pkt1), (t2, pkt2)])

            self.session.receive(key, pkt3)
            self.assertEqual(self.session.received[serial][key], [(t1, pkt1), (t2, pkt2)])
            self.assertEqual(self.session.received[serial2][key], [(t3, pkt3)])

        pkt4 = mock.Mock(name="pkt4", serial=serial)
        key2 = str(uuid.uuid4())

        with mock.patch("time.time", t):
            self.session.receive(key2, pkt4)
            self.assertEqual(self.session.received[serial][key2], [(t4, pkt4)])

        self.assertEqual(
            self.session.received,
            {
                serial: {key: [(t1, pkt1), (t2, pkt2)], key2: [(t4, pkt4)]},
                serial2: {key: [(t3, pkt3)]},
            },
        )

    it "can fill results":
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

        self.assertEqual(self.session.filled, {})

        with mock.patch("time.time", t):
            self.session.fill(plankey, serial, result)
            self.assertEqual(self.session.filled, {plankey: {serial: (t1, result)}})

            self.session.fill(plankey, serial, result2)
            self.assertEqual(self.session.filled, {plankey: {serial: (t2, result2)}})

        serial2 = "d073d5000002"
        with mock.patch("time.time", t):
            self.session.fill(plankey, serial2, result)
            self.assertEqual(
                self.session.filled, {plankey: {serial: (t2, result2), serial2: (t3, result)}}
            )

        plankey2 = str(uuid.uuid4())
        serial3 = "d073d5000003"
        result3 = mock.Mock(name="result3")

        with mock.patch("time.time", t):
            self.session.fill(plankey2, serial3, result3)
            self.assertEqual(
                self.session.filled,
                {
                    plankey: {serial: (t2, result2), serial2: (t3, result)},
                    plankey2: {serial3: (t4, result3)},
                },
            )

    describe "completed":
        it "returns result if we have one":
            plankey = str(uuid.uuid4())
            serial = "d073d5000001"
            serial2 = "d073d5000002"
            result = mock.Mock(name="result")

            self.assertIs(self.session.completed(plankey, serial), None)
            self.assertIs(self.session.completed(plankey, serial2), None)

            self.session.fill(plankey, serial, result)
            self.assertIs(self.session.completed(plankey, serial), result)

            self.assertIs(self.session.completed(plankey, serial2), None)

    describe "has_received":
        it "says whether we have results for that serial and key":
            key = str(uuid.uuid4())
            key2 = str(uuid.uuid4())
            serial = "d073d5000001"
            serial2 = "d073d5000002"
            pkt1 = mock.Mock(name="pkt1", serial=serial)

            assert not self.session.has_received(key, serial)
            assert not self.session.has_received(key, serial2)
            assert not self.session.has_received(key2, serial2)

            self.session.receive(key, pkt1)

            assert self.session.has_received(key, serial)
            assert not self.session.has_received(key, serial2)
            assert not self.session.has_received(key2, serial2)

    describe "known_packets":
        it "yields known packets for this serial":
            key = str(uuid.uuid4())
            key2 = str(uuid.uuid4())

            serial = "d073d5000001"
            serial2 = "d073d5000002"

            pkt1 = mock.Mock(name="pkt1", serial=serial)
            pkt2 = mock.Mock(name="pkt2", serial=serial)
            pkt3 = mock.Mock(name="pkt3", serial=serial2)
            pkt4 = mock.Mock(name="pkt4", serial=serial)
            pkt5 = mock.Mock(name="pkt5", serial=serial2)

            self.assertEqual(list(self.session.known_packets(serial)), [])
            self.assertEqual(list(self.session.known_packets(serial2)), [])

            self.session.receive(key, pkt1)
            self.session.receive(key, pkt2)
            self.session.receive(key2, pkt3)
            self.session.receive(key2, pkt4)
            self.session.receive(key2, pkt5)

            ls = list(self.session.known_packets(serial))
            self.assertEqual(ls, [pkt1, pkt2, pkt4])

            ls = list(self.session.known_packets(serial2))
            self.assertEqual(ls, [pkt3, pkt5])

    describe "refresh_received":
        before_each:
            self.key1 = str(uuid.uuid4())
            self.key2 = str(uuid.uuid4())

            self.serial1 = "d073d5000001"
            self.serial2 = "d073d5000002"

            def add(s, l, *, t, k):
                key = getattr(self, f"key{k}")

                pkt = mock.Mock(name=f"pkt{s}{l}{k}", serial=getattr(self, f"serial{s}"))
                setattr(self, f"pkt{s}{l}{k}", pkt)

                with self.a_time(t):
                    self.session.receive(key, pkt)

            add(1, "a", t=1, k=1)
            add(1, "b", t=10, k=1)
            add(1, "c", t=15, k=1)

            add(1, "a", t=1, k=2)
            add(1, "b", t=5, k=2)
            add(1, "c", t=20, k=2)

            add(2, "a", t=10, k=1)
            add(2, "b", t=12, k=1)
            add(2, "c", t=13, k=1)

            add(2, "a", t=5, k=2)
            add(2, "b", t=5, k=2)
            add(2, "c", t=5, k=2)

            self.starting_received = {
                self.serial1: {
                    self.key1: [(1, self.pkt1a1), (10, self.pkt1b1), (15, self.pkt1c1)],
                    self.key2: [(1, self.pkt1a2), (5, self.pkt1b2), (20, self.pkt1c2)],
                },
                self.serial2: {
                    self.key1: [(10, self.pkt2a1), (12, self.pkt2b1), (13, self.pkt2c1)],
                    self.key2: [(5, self.pkt2a2), (5, self.pkt2b2), (5, self.pkt2c2)],
                },
            }
            self.assertEqual(self.session.received, self.starting_received)

        @contextmanager
        def a_time(self, t):
            time = mock.Mock(name="time", return_value=t)
            with mock.patch("time.time", time):
                yield

        it "does nothing if refresh is False":
            self.session.refresh_received(self.key1, self.serial1, False)
            self.assertEqual(self.session.received, self.starting_received)

        it "does nothing if serial not in received":
            self.session.refresh_received(self.key1, "not here", 1)
            self.assertEqual(self.session.received, self.starting_received)

        it "does nothing if key not in received":
            self.session.refresh_received("not here", self.serial1, 1)
            self.assertEqual(self.session.received, self.starting_received)

        it "removes everything if refresh is 0":
            self.session.refresh_received(self.key1, self.serial1, 0)
            self.assertEqual(
                self.session.received,
                {
                    self.serial1: {
                        self.key2: [(1, self.pkt1a2), (5, self.pkt1b2), (20, self.pkt1c2)]
                    },
                    self.serial2: {
                        self.key1: [(10, self.pkt2a1), (12, self.pkt2b1), (13, self.pkt2c1)],
                        self.key2: [(5, self.pkt2a2), (5, self.pkt2b2), (5, self.pkt2c2)],
                    },
                },
            )

            self.session.refresh_received(self.key2, self.serial2, 0)
            self.assertEqual(
                self.session.received,
                {
                    self.serial1: {
                        self.key2: [(1, self.pkt1a2), (5, self.pkt1b2), (20, self.pkt1c2)]
                    },
                    self.serial2: {
                        self.key1: [(10, self.pkt2a1), (12, self.pkt2b1), (13, self.pkt2c1)]
                    },
                },
            )

        it "removes everything if refresh is True":
            self.session.refresh_received(self.key1, self.serial1, True)
            self.assertEqual(
                self.session.received,
                {
                    self.serial1: {
                        self.key2: [(1, self.pkt1a2), (5, self.pkt1b2), (20, self.pkt1c2)]
                    },
                    self.serial2: {
                        self.key1: [(10, self.pkt2a1), (12, self.pkt2b1), (13, self.pkt2c1)],
                        self.key2: [(5, self.pkt2a2), (5, self.pkt2b2), (5, self.pkt2c2)],
                    },
                },
            )

            self.session.refresh_received(self.key2, self.serial2, True)
            self.assertEqual(
                self.session.received,
                {
                    self.serial1: {
                        self.key2: [(1, self.pkt1a2), (5, self.pkt1b2), (20, self.pkt1c2)]
                    },
                    self.serial2: {
                        self.key1: [(10, self.pkt2a1), (12, self.pkt2b1), (13, self.pkt2c1)]
                    },
                },
            )

        it "removes anything older than refresh seconds":
            with self.a_time(2):
                self.session.refresh_received(self.key1, self.serial1, 1)

            self.assertEqual(
                self.session.received,
                {
                    self.serial1: {
                        self.key1: [(10, self.pkt1b1), (15, self.pkt1c1)],
                        self.key2: self.starting_received[self.serial1][self.key2],
                    },
                    self.serial2: self.starting_received[self.serial2],
                },
            )

            with self.a_time(20):
                self.session.refresh_received(self.key1, self.serial1, 6)

            self.assertEqual(
                self.session.received,
                {
                    self.serial1: {
                        self.key1: [(15, self.pkt1c1)],
                        self.key2: self.starting_received[self.serial1][self.key2],
                    },
                    self.serial2: self.starting_received[self.serial2],
                },
            )

            with self.a_time(20):
                self.session.refresh_received(self.key1, self.serial1, 5)

            self.assertEqual(
                self.session.received,
                {
                    self.serial1: {self.key2: self.starting_received[self.serial1][self.key2]},
                    self.serial2: self.starting_received[self.serial2],
                },
            )

            with self.a_time(20):
                self.session.refresh_received(self.key1, self.serial1, 4)

            self.assertEqual(
                self.session.received,
                {
                    self.serial1: {self.key2: self.starting_received[self.serial1][self.key2]},
                    self.serial2: self.starting_received[self.serial2],
                },
            )

            with self.a_time(20):
                self.session.refresh_received(self.key2, self.serial2, 10)

            self.assertEqual(
                self.session.received,
                {
                    self.serial1: {self.key2: self.starting_received[self.serial1][self.key2]},
                    self.serial2: {self.key1: self.starting_received[self.serial2][self.key1]},
                },
            )

    describe "refresh_filled":
        before_each:
            self.plankeya = str(uuid.uuid4())
            self.plankeyb = str(uuid.uuid4())

            self.serial1 = "d073d5000001"
            self.serial2 = "d073d5000002"

            self.result1a = mock.Mock(name="result1a")
            self.result1b = mock.Mock(name="result1b")
            self.result2a = mock.Mock(name="result2a")
            self.result2b = mock.Mock(name="result2b")

            with self.a_time(1):
                self.session.fill(self.plankeya, self.serial1, self.result1a)

            with self.a_time(2):
                self.session.fill(self.plankeya, self.serial2, self.result2a)

            with self.a_time(5):
                self.session.fill(self.plankeyb, self.serial1, self.result1b)

            with self.a_time(10):
                self.session.fill(self.plankeyb, self.serial2, self.result2b)

            self.starting_filled = {
                self.plankeya: {self.serial1: (1, self.result1a), self.serial2: (2, self.result2a)},
                self.plankeyb: {
                    self.serial1: (5, self.result1b),
                    self.serial2: (10, self.result2b),
                },
            }
            self.assertEqual(self.session.filled, self.starting_filled)

        @contextmanager
        def a_time(self, t):
            time = mock.Mock(name="time", return_value=t)
            with mock.patch("time.time", time):
                yield

        it "does nothing if refresh is False":
            self.session.refresh_filled(self.plankeya, self.serial1, False)
            self.assertEqual(self.session.filled, self.starting_filled)

        it "does nothing if plankey not there":
            self.session.refresh_filled("not there", self.serial1, 1)
            self.assertEqual(self.session.filled, self.starting_filled)

        it "does nothing if serial not there":
            self.session.refresh_filled(self.plankeya, "not there", 1)
            self.assertEqual(self.session.filled, self.starting_filled)

        it "removes result if refresh is True or 0":
            self.session.refresh_filled(self.plankeya, self.serial1, True)
            self.assertEqual(
                self.session.filled,
                {
                    self.plankeya: {self.serial2: self.session.filled[self.plankeya][self.serial2]},
                    self.plankeyb: self.session.filled[self.plankeyb],
                },
            )

            self.session.refresh_filled(self.plankeya, self.serial2, 0)
            self.assertEqual(
                self.session.filled, {self.plankeyb: self.session.filled[self.plankeyb]}
            )

        it "removes result if been refresh seconds":
            with self.a_time(6):
                self.session.refresh_filled(self.plankeyb, self.serial1, 2)
            self.assertEqual(self.session.filled, self.starting_filled)

            with self.a_time(6):
                self.session.refresh_filled(self.plankeyb, self.serial1, 1)

            self.assertEqual(
                self.session.filled,
                {
                    self.plankeya: self.session.filled[self.plankeya],
                    self.plankeyb: {self.serial2: self.session.filled[self.plankeyb][self.serial2]},
                },
            )

            with self.a_time(20):
                self.session.refresh_filled(self.plankeyb, self.serial2, 5)

            self.assertEqual(
                self.session.filled, {self.plankeya: self.session.filled[self.plankeya]}
            )
