# coding: spec

from photons_app.mimic.event import ConsoleFormat, Event, Events, EventsHolder
from photons_app.mimic.operator import Operator
from photons_app.errors import PhotonsAppError
from photons_app.mimic.attrs import ChangeAttr
from photons_app.mimic.device import Device
from photons_app import helpers as hp
from photons_app.mimic import event

from photons_messages import CoreMessages, DeviceMessages, LightMessages, MultiZoneMessages
from photons_products import Products

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from itertools import zip_longest
from unittest import mock
import dateutil.tz
import logging
import pytest


def assertLines(func, original, *lines):
    if original is sb.NotSpecified:
        got = list(func())
    else:
        got = list(func(original))

    different = False
    for i, (g, w) in enumerate(zip_longest(got, lines)):
        if g != w:
            print(f"line {i}:\n  Got : {g}\n  Want: {w}")
            different = True

    if different:
        print("=" * 10, "GOT")
        for line in got:
            print(line)

        print()
        print("=" * 10, "WANT")
        for line in lines:
            print(line)

    assert got == list(lines)


@pytest.fixture()
def device():
    return Device("d073d5001337", Products.LCM2_A19, hp.Firmware(2, 80))


@pytest.fixture()
def device2():
    return Device("d073d5001338", Products.LCM3_TILE, hp.Firmware(3, 50))


@pytest.fixture()
def io(device):
    io = Operator(device)
    io.io_source = "TEST_IO"
    return io


def assertConsoleOutput(event, *lines):
    event.created = 1621126801.65
    with mock.patch.object(Event, "LOCAL_TZ", dateutil.tz.gettz("Australia/Melbourne")):
        assertLines(event.for_console, sb.NotSpecified, *lines)


describe "ConsoleFormat":
    describe "lines_from_error":

        def assertLines(self, err, *lines):
            assertLines(ConsoleFormat.lines_from_error, err, *lines)

        it "can format a string":
            self.assertLines("stuff", "stuff")

        it "can format a dictionary":
            self.assertLines(
                {"message": "yeap", "one": "two", "three": ["four"]},
                "yeap",
                "one = two",
                "three = ['four']",
            )

        it "can format a DelfickError":

            class MyError(PhotonsAppError):
                desc = "oh noes"

            self.assertLines(
                MyError("the horror", explosion=True, help_us="please"),
                "<MyError> oh noes. the horror",
                "explosion = True",
                "help_us = please",
            )

        it "can see an expand function":

            class MyError(PhotonsAppError):
                desc = "oh noes"

                def expand(self):
                    yield "line1"
                    yield "line2"

            self.assertLines(
                MyError("the horror", explosion=True, help_us="please"),
                "line1",
                "line2",
                "explosion = True",
                "help_us = please",
            )

    describe "lines_from_a_packet":

        def assertLines(self, pkt, *lines):
            assertLines(ConsoleFormat.lines_from_packet, pkt, *lines)

        it "can format acknowledgements":
            ack = CoreMessages.Acknowledgement(source=20, sequence=2, target="d073d5001111")
            self.assertLines(ack, f"Ack(source={ack.source},sequence=2,target=d073d5001111)(empty)")

        it "can format simple messages":
            pkt = DeviceMessages.GetPower(source=21, sequence=3, target="d073d5002222")
            self.assertLines(
                pkt,
                f"GetPower(ack=True,res=True,source={pkt.source},sequence=3,target=d073d5002222)(empty)",
            )

        it "can format messages with fields":
            pkt = LightMessages.SetColor(
                res_required=False,
                source=22,
                sequence=4,
                target="d073d5003333",
                hue=200,
                saturation=1,
                brightness=0.5,
                kelvin=9000,
            )
            self.assertLines(
                pkt,
                f"SetColor(ack=True,res=False,source={pkt.source},sequence=4,target=d073d5003333)",
                mock.ANY,
                "  hue: 200.0",
                "  saturation: 1.0",
                "  brightness: 0.5",
                "  kelvin: 9000",
                "  duration: 0.0",
            )

        it "can format messages with lists":
            pkt = MultiZoneMessages.SetExtendedColorZones(
                ack_required=False,
                res_required=False,
                sequence=5,
                target="d073d5004444",
                colors_count=3,
                colors=[
                    {"hue": 3, "brightness": 1, "saturation": 1, "kelvin": 9000},
                    {"hue": 20, "saturation": 1},
                    {"hue": 30, "saturation": 1, "brightness": 0.2},
                ],
            )
            self.assertLines(
                pkt,
                "SetExtendedColorZones(ack=False,res=False,source=<NOT_SPECIFIED>,sequence=5,target=d073d5004444)",
                "  duration: 0.0",
                "  apply: <MultiZoneExtendedApplicationRequest.APPLY: 1>",
                "  zone_index: <NOT_SPECIFIED>",
                "  colors_count: 3",
                "  colors:",
                "  {'brightness': 1.0, 'hue': 3.0, 'kelvin': 9000, 'saturation': 1.0}",
                "  {'brightness': '<NOT_SPECIFIED>', 'hue': 20.0, 'kelvin': 3500, 'saturation': 1.0}",
                "  {'brightness': 0.2, 'hue': 30.0, 'kelvin': 3500, 'saturation': 1.0}",
            )

describe "Event":
    it "has a repr on the class":
        assert repr(event.IncomingEvent) == "<Events.INCOMING>"

        class MyEvent:
            pass

        expected = repr(MyEvent)

        class MyEvent(Event):
            pass

        assert repr(MyEvent) == expected

    it "has or comparison":
        assert event.IncomingEvent | event.IncomingEvent
        assert not event.IncomingEvent | event.ResetEvent

    it "has a name", device:

        class MyEvent(Event):
            pass

        e = MyEvent(device)
        assert e.name == "d073d5001337(LCM2_A19:2,80) MyEvent"

    it "has a repr", device:

        class MyEvent(Event):
            pass

        e = MyEvent(device)
        assert repr(e) == "<Event:d073d5001337:MyEvent>"

    it "has equality", device, device2:

        class MyEvent(Event):
            pass

        MyEvent(device) == MyEvent(device)
        MyEvent(device) == MyEvent
        MyEvent(device) == (MyEvent, device)

        MyEvent(device) != MyEvent(device2)
        MyEvent(device) != (MyEvent, device2)

        class MyEvent2(Event):
            pass

        MyEvent(device) == MyEvent2(device)
        MyEvent(device) == MyEvent2
        MyEvent(device) == (MyEvent2, device)
        MyEvent(device) == (MyEvent2, device2)

    it "has equality by default only on log_args and log_kwargs", device:

        class MyEvent3(Event):
            def setup(self, *, one, two, three):
                self.one = one
                self.two = two
                self.three = three
                self.log_args = (one,)
                self.log_kwargs = {"three": three}

        MyEvent3(device, one=1, two=2, three=3) == MyEvent3(device, one=1, two=2, three=3)
        MyEvent3(device, one=1, two=4, three=3) == MyEvent3(device, one=1, two=4, three=3)
        MyEvent3(device, one=2, two=4, three=3) != MyEvent3(device, one=1, two=4, three=3)
        MyEvent3(device, one=1, two=4, three=5) != MyEvent3(device, one=1, two=4, three=3)

        class MyEvent4(MyEvent3):
            def has_same_args(self, other):
                return self.one == other.one and self.two == other.two and self.three == other.three

        MyEvent4(device, one=1, two=2, three=3) == MyEvent4(device, one=1, two=2, three=3)
        MyEvent4(device, one=1, two=4, three=3) != MyEvent4(device, one=1, two=4, three=3)
        MyEvent4(device, one=2, two=4, three=3) != MyEvent4(device, one=1, two=4, three=3)
        MyEvent4(device, one=1, two=4, three=5) != MyEvent4(device, one=1, two=4, three=3)

    it "has setup", device, FakeTime:

        got = []

        with FakeTime() as t:
            t.set(56789)

            class MyEvent(Event):
                def setup(s, *a, **kw):
                    assert s.device is device
                    assert s.created == 56789
                    got.append((a, kw))

            e = MyEvent(device, 1, 2, one=3, four=9)
            ga = (1, 2)
            gkw = {"one": 3, "four": 9}
            assert e.created == 56789
            assert e.device is device
            assert e.log_args == ga
            assert e.log_kwargs == gkw
            assert got == [(ga, gkw)]

    it "can do comparisons with events", device:
        e = Events.POWER_OFF(device)
        assert e | Events.POWER_OFF
        assert not e | Events.OUTGOING

        e = Events.RESET(device, old_attrs={})
        assert e | Events.RESET
        assert not e | Events.POWER_OFF

    describe "formatting for the console":

        it "can format a simple event", device:
            assertConsoleOutput(
                Events.POWER_OFF(device),
                "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) POWER_OFF",
            )

        it "can format an event with arguments", device:

            class Simple(Event):
                def setup(self):
                    self.log_args = ("hello", "there")
                    self.log_kwargs = {"tree": "forest"}

            assertConsoleOutput(
                Simple(device),
                "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) Simple",
                "  -- hello",
                "  -- there",
                "  :: tree = 'forest'",
            )

            class Complex(Event):
                def setup(self):
                    self.log_args = (PhotonsAppError("stuff happens", one=1),)
                    self.log_kwargs = {
                        "pkt": DeviceMessages.SetPower(level=65535),
                        "other": [1, 2],
                        "more": True,
                    }

            assertConsoleOutput(
                Complex(device),
                "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) Complex",
                "  --> <PhotonsAppError> stuff happens",
                "  --> one = 1",
                "  || pkt = SetPower(ack=True,res=True,source=<NOT_SPECIFIED>,sequence=<NOT_SPECIFIED>,target=None)",
                "  ^^   level: 65535",
                "  :: other = [1, 2]",
                "  :: more = True",
            )

describe "Events":
    it "is a EventsHolder":
        assert isinstance(Events, EventsHolder)

    it "can register events":
        events = EventsHolder()
        assert events.events == {}

        with assertRaises(AttributeError):
            events.AMAZE_EVENT

        @events.register("AMAZE_EVENT")
        class Amaze:
            pass

        assert events.AMAZE_EVENT is Amaze

    it "can get a name for an event":
        events = EventsHolder()

        @events.register("AMAZE_EVENT")
        class Amaze:
            pass

        assert events.name(Amaze) == "AMAZE_EVENT"

        class Other:
            pass

        assert events.name(Other) == "Other"

describe "IncomingEvent":

    @pytest.fixture()
    def EKLS(self):
        return Events.INCOMING

    it "is under INCOMING", EKLS, device, io:
        assert Events.INCOMING is event.IncomingEvent
        assert EKLS is event.IncomingEvent

    it "has a repr", EKLS, io, device:
        e = EKLS(device, io, pkt=DeviceMessages.GetPower())
        assert repr(e) == "<Event:d073d5001337:INCOMING:io=TEST_IO:pkt=GetPower>"

    it "can do comparisons with packets and events", EKLS, io, device:
        e = EKLS(device, io, pkt=DeviceMessages.GetPower())
        assert e | DeviceMessages.GetPower
        assert not e | DeviceMessages.SetPower
        assert e | DeviceMessages.GetPower
        assert not e | DeviceMessages.SetPower

        assert e | Events.INCOMING
        assert not e | Events.OUTGOING

        # Show doesn't apply to a different event
        e = Events.OUTGOING(
            device, io, pkt=DeviceMessages.GetPower(), addr="somewhere", replying_to="the test"
        )
        assert not e | DeviceMessages.GetPower
        assert not e | DeviceMessages.SetPower
        assert not e | Events.INCOMING
        assert e | Events.OUTGOING

    it "can do comparisons on the io", EKLS, device:

        class MyIO(Operator):
            io_source = "HIGHWAY_TO_INFO"

        e = EKLS(
            device,
            MyIO(device),
            pkt=DeviceMessages.GetPower(),
        )

        assert e | MyIO.io_source
        assert not e | "other"

    it "can create bytes", EKLS, device, io:
        pkt = DeviceMessages.GetPower(source=2, sequence=1, target=None)
        e = EKLS(device, io, pkt=pkt)
        assert e.bts == pkt.pack()

    it "ignores errors when creating bytes", EKLS, device, io:
        pkt = DeviceMessages.GetPower()
        with assertRaises(Exception):
            pkt.pack()
        e = EKLS(device, io, pkt=pkt)
        assert e.bts is None

        pkt.source = 2
        pkt.sequence = 1
        pkt.target = None
        assert e.bts == pkt.pack()

    it "can set replies", EKLS, device, io:
        e = EKLS(device, io, pkt=DeviceMessages.GetPower())
        assert not e.handled
        assert e.replies is None

        replies = [DeviceMessages.StatePower(level=0), DeviceMessages.StatePower(level=65535)]
        e.set_replies(*replies)

        assert e.handled
        assert e.replies == replies

        other = [DeviceMessages.StateLabel()]
        e.set_replies(*other)
        assert e.handled
        assert e.replies == other

    it "can add replies", EKLS, device, io:
        reply1 = DeviceMessages.StatePower()
        reply2 = DeviceMessages.StateLabel()
        reply3 = DeviceMessages.StateGroup()
        reply4 = DeviceMessages.StateLocation()
        reply5 = DeviceMessages.StateInfo()

        e = EKLS(device, io, pkt=DeviceMessages.GetPower())
        assert not e.handled
        assert e.replies is None

        e.add_replies(reply1, reply2)
        assert not e.handled
        assert e.replies == [reply1, reply2]

        e.add_replies([reply3, reply4])
        assert not e.handled
        assert e.replies == [reply1, reply2, reply3, reply4]

        e.add_replies(reply5)
        assert not e.handled
        assert e.replies == [reply1, reply2, reply3, reply4, reply5]

    it "modifies args and kwargs for console output", EKLS, device, io:
        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.SetPower(source=2, sequence=1, target=None, level=65535),
            bts="aa",
            addr=("somewhere", "nice"),
        )
        assertConsoleOutput(
            e,
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) INCOMING",
            f"  || packet = SetPower(ack=True,res=True,source={e.pkt.source},sequence=1,target=000000000000)",
            "  ^^   level: 65535",
            "  :: bts = 'aa'",
            "  :: io = 'TEST_IO'",
            "  :: addr = ('somewhere', 'nice')",
        )

        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.SetPower(source=2, sequence=1, target=None, level=65535),
        )
        assertConsoleOutput(
            e,
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) INCOMING",
            f"  || packet = SetPower(ack=True,res=True,source={e.pkt.source},sequence=1,target=000000000000)",
            "  ^^   level: 65535",
            "  :: bts = 260000340200000000000000000000000000000000000301000000000000000015000000ffff",
            "  :: io = 'TEST_IO'",
            "  :: addr = None",
        )

describe "OutgoingEvent":

    @pytest.fixture()
    def EKLS(self):
        return Events.OUTGOING

    it "is under OUTGOING", EKLS, device, io:
        assert Events.OUTGOING is event.OutgoingEvent
        assert EKLS is event.OutgoingEvent

    it "has a repr", EKLS, io, device:
        pkt = DeviceMessages.StatePower(source=2, sequence=1, target=None, level=0)
        e = EKLS(device, io, pkt=pkt, replying_to=DeviceMessages.GetPower(), addr=None)
        assert repr(e) == "<Event:d073d5001337:OUTGOING:io=TEST_IO,pkt=StatePower>"

    it "can create bytes", EKLS, device, io:
        pkt = DeviceMessages.StatePower(source=2, sequence=1, target=None, level=0)
        e = EKLS(device, io, pkt=pkt, replying_to=DeviceMessages.GetPower(), addr=None)
        assert e.bts == pkt.pack()

    it "ignores errors when creating bytes", EKLS, device, io:
        pkt = DeviceMessages.GetPower()
        with assertRaises(Exception):
            pkt.pack()
        e = EKLS(device, io, pkt=pkt, replying_to=DeviceMessages.GetPower(), addr=None)
        assert e.bts is None

        pkt.source = 2
        pkt.sequence = 1
        pkt.target = None
        assert e.bts == pkt.pack()

    it "modifies args and kwargs for console output", EKLS, device, io:
        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.StatePower(source=2, sequence=1, target=None, level=65535),
            bts="aa",
            addr="earth",
            replying_to=DeviceMessages.GetPower(),
        )
        assertConsoleOutput(
            e,
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) OUTGOING",
            f"  || packet = StatePower(ack=True,res=True,source={e.pkt.source},sequence=1,target=000000000000)",
            "  ^^   level: 65535",
            "  :: bts = 'aa'",
            "  :: io = 'TEST_IO'",
            "  :: addr = 'earth'",
            "  :: replying_to = 'GetPower'",
        )

        e = EKLS(
            device,
            io,
            addr="venus",
            pkt=DeviceMessages.StateLabel(source=2, sequence=1, target=None, label="yeap"),
            replying_to=DeviceMessages.SetPower(),
        )
        assertConsoleOutput(
            e,
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) OUTGOING",
            f"  || packet = StateLabel(ack=True,res=True,source={e.pkt.source},sequence=1,target=000000000000)",
            "  ^^   label: yeap",
            "  :: bts = 4400003402000000000000000000000000000000000003010000000000000000190000007965617000000000000000000000000000000000000000000000000000000000",
            "  :: io = 'TEST_IO'",
            "  :: addr = 'venus'",
            "  :: replying_to = 'SetPower'",
        )

describe "UnhandledEvent":

    @pytest.fixture()
    def EKLS(self):
        return Events.UNHANDLED

    it "is under UNHANDLED", EKLS, device, io:
        assert Events.UNHANDLED is event.UnhandledEvent
        assert EKLS is event.UnhandledEvent

    it "has a repr", EKLS, io, device:
        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.StatePower(source=2, sequence=1, target=None, level=65535),
            bts="aa",
            addr="earth",
        )
        assert repr(e) == "<Event:d073d5001337:UNHANDLED:pkt=StatePower>"

    it "modifies args and kwargs for console output", EKLS, device, io:
        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.StatePower(source=2, sequence=1, target=None, level=65535),
            bts="aa",
            addr="earth",
        )
        assertConsoleOutput(
            e,
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) UNHANDLED",
            f"  || packet = StatePower(ack=True,res=True,source={e.pkt.source},sequence=1,target=000000000000)",
            "  ^^   level: 65535",
            "  :: bts = 'aa'",
            "  :: io = 'TEST_IO'",
            "  :: addr = 'earth'",
        )

        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.StateLabel(source=2, sequence=1, target=None, label="yeap"),
        )
        assertConsoleOutput(
            e,
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) UNHANDLED",
            f"  || packet = StateLabel(ack=True,res=True,source={e.pkt.source},sequence=1,target=000000000000)",
            "  ^^   label: yeap",
            "  :: bts = 4400003402000000000000000000000000000000000003010000000000000000190000007965617000000000000000000000000000000000000000000000000000000000",
            "  :: io = 'TEST_IO'",
            "  :: addr = None",
        )

describe "IgnoredEvent":

    @pytest.fixture()
    def EKLS(self):
        return Events.IGNORED

    it "is under IGNORED", EKLS, device, io:
        assert Events.IGNORED is event.IgnoredEvent
        assert EKLS is event.IgnoredEvent

    it "has a repr", EKLS, io, device:
        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.StatePower(source=2, sequence=1, target=None, level=65535),
            bts="aa",
            addr="earth",
        )
        assert repr(e) == "<Event:d073d5001337:IGNORED:pkt=StatePower>"

    it "modifies args and kwargs for console output", EKLS, device, io:
        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.StatePower(source=2, sequence=1, target=None, level=65535),
            bts="aa",
            addr="earth",
        )
        assertConsoleOutput(
            e,
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) IGNORED",
            f"  || packet = StatePower(ack=True,res=True,source={e.pkt.source},sequence=1,target=000000000000)",
            "  ^^   level: 65535",
            "  :: bts = 'aa'",
            "  :: io = 'TEST_IO'",
            "  :: addr = 'earth'",
        )

        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.StateLabel(source=2, sequence=1, target=None, label="yeap"),
        )
        assertConsoleOutput(
            e,
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) IGNORED",
            f"  || packet = StateLabel(ack=True,res=True,source={e.pkt.source},sequence=1,target=000000000000)",
            "  ^^   label: yeap",
            "  :: bts = 4400003402000000000000000000000000000000000003010000000000000000190000007965617000000000000000000000000000000000000000000000000000000000",
            "  :: io = 'TEST_IO'",
            "  :: addr = None",
        )

describe "LostEvent":

    @pytest.fixture()
    def EKLS(self):
        return Events.LOST

    it "is under LOST", EKLS, device, io:
        assert Events.LOST is event.LostEvent
        assert EKLS is event.LostEvent

    it "has a repr", EKLS, io, device:
        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.StatePower(source=2, sequence=1, target=None, level=65535),
            bts="aa",
            addr="earth",
        )
        assert repr(e) == "<Event:d073d5001337:LOST:pkt=StatePower>"

    it "modifies args and kwargs for console output", EKLS, device, io:
        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.StatePower(source=2, sequence=1, target=None, level=65535),
            bts="aa",
            addr="earth",
        )
        assertConsoleOutput(
            e,
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) LOST",
            f"  || packet = StatePower(ack=True,res=True,source={e.pkt.source},sequence=1,target=000000000000)",
            "  ^^   level: 65535",
            "  :: bts = 'aa'",
            "  :: io = 'TEST_IO'",
            "  :: addr = 'earth'",
        )

        e = EKLS(
            device,
            io,
            pkt=DeviceMessages.StateLabel(source=2, sequence=1, target=None, label="yeap"),
        )
        assertConsoleOutput(
            e,
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) LOST",
            f"  || packet = StateLabel(ack=True,res=True,source={e.pkt.source},sequence=1,target=000000000000)",
            "  ^^   label: yeap",
            "  :: bts = 4400003402000000000000000000000000000000000003010000000000000000190000007965617000000000000000000000000000000000000000000000000000000000",
            "  :: io = 'TEST_IO'",
            "  :: addr = None",
        )


@pytest.mark.focus
describe "AttributeChangeEvent":

    @pytest.fixture()
    def EKLS(self):
        return Events.ATTRIBUTE_CHANGE

    it "is under ATTRIBUTE_CHANGE", EKLS, device, io:
        assert Events.ATTRIBUTE_CHANGE is event.AttributeChangeEvent
        assert EKLS is event.AttributeChangeEvent

    it "has a repr", EKLS, io, device:
        e = EKLS(
            device,
            [ChangeAttr.test("one", 1), ChangeAttr.test("two", 2)],
            False,
            Events.RESET(device, old_attrs={}),
        )
        assert (
            repr(e)
            == "<Event:d073d5001337:ATTRIBUTE_CHANGE:changes=[<Changed one to 1>, <Changed two to 2>]:attrs_started=False:because=<Event:d073d5001337:RESET:zerod=False>>"
        )

    it "has changes", EKLS, device:
        e = EKLS(device, {"one": 1, "two": 2}, False, Events.RESET(device, old_attrs={}))
        assert e.changes == {"one": 1, "two": 2}
        assert not e.attrs_started

    it "has nicer console output", EKLS, device:
        assertConsoleOutput(
            EKLS(
                device,
                [ChangeAttr.test("one", 1), ChangeAttr.test("two", 2)],
                True,
                Events.RESET(device, old_attrs={}),
            ),
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) ATTRIBUTE_CHANGE",
            "  -- Attributes changed (started)",
            "  :: because = <Event:d073d5001337:RESET:zerod=False>",
            "  ~ <Changed one to 1>",
            "  ~ <Changed two to 2>",
        )

describe "AnnotationEvent":

    @pytest.fixture()
    def EKLS(self):
        return Events.ANNOTATION

    it "is under ANNOTATION", EKLS, device, io:
        assert Events.ANNOTATION is event.AnnotationEvent
        assert EKLS is event.AnnotationEvent

    it "has a repr", EKLS, io, device:
        e = EKLS(device, logging.INFO, "hello there", stuff=20, things="blah")
        assert repr(e) == "<Event:d073d5001337:ANNOTATION>"

    it "has nicer console output", EKLS, device:
        assertConsoleOutput(
            EKLS(device, logging.INFO, "hello there", stuff=20, things="blah"),
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) ANNOTATION(INFO)",
            "  -- hello there",
            "  :: stuff = 20",
            "  :: things = 'blah'",
        )

        class AnError(PhotonsAppError):
            desc = "sad"

        assertConsoleOutput(
            EKLS(
                device,
                logging.ERROR,
                "nopety nope nope",
                error=AnError("NOOO", bad=True),
                future="now",
            ),
            "2021-05-16 11:00:01.650000+1000 -> d073d5001337(LCM2_A19:2,80) ANNOTATION(ERROR)",
            "  -- nopety nope nope",
            "  >> <AnError> sad. NOOO",
            "  >> bad = True",
            "  :: future = 'now'",
        )

describe "DiscoverableEvent":

    @pytest.fixture()
    def EKLS(self):
        return Events.DISCOVERABLE

    it "is under DISCOVERABLE", EKLS, device, io:
        assert Events.DISCOVERABLE is event.DiscoverableEvent
        assert EKLS is event.DiscoverableEvent

    it "has a repr", EKLS, io, device:
        e = EKLS(device, service="MEMORY", address="computer")
        assert repr(e) == "<Event:d073d5001337:DISCOVERABLE:address=computer,service=MEMORY>"

    it "has service and address", EKLS, device:
        e = EKLS(device, service="MEMORY", address="computer")
        assert e.service == "MEMORY"
        assert e.address == "computer"
