import itertools
from contextlib import contextmanager
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises, assertSameError
from photons_app import helpers as hp
from photons_app.errors import BadRunWithResults, TimedOut
from photons_control.planner import Gatherer, NoMessages, Plan, Skip, make_plans
from photons_messages import DeviceMessages, DiscoveryMessages, LightMessages
from photons_products import Products

devices = pytest.helpers.mimic()

light1 = devices.add("light1")(
    "d073d5000001",
    Products.LCM2_A19_PLUS,
    hp.Firmware(2, 77),
    value_store=dict(
        power=0,
        label="bob",
        infrared=100,
        color=hp.Color(100, 0.5, 0.5, 4500),
    ),
)

light2 = devices.add("light2")(
    "d073d5000002",
    Products.LMB_MESH_A21,
    hp.Firmware(2, 2),
    value_store=dict(
        power=65535,
        label="sam",
        color=hp.Color(200, 0.3, 1, 9000),
    ),
)

light3 = devices.add("light3")(
    "d073d5000003",
    Products.LCM1_Z,
    hp.Firmware(1, 22),
    value_store=dict(
        power=0,
        label="strip",
        zones=[hp.Color(0, 1, 1, 3500)],
    ),
)

two_lights = [light1.serial, light2.serial]


@pytest.fixture(scope="module")
def final_future():
    fut = hp.create_future()
    try:
        yield fut
    finally:
        fut.cancel()


@pytest.fixture(scope="module")
async def sender(final_future):
    async with devices.for_test(final_future) as sender:
        yield sender


@pytest.fixture(autouse=True)
async def reset_devices(sender):
    for device in devices:
        await device.reset()
        devices.store(device).clear()
    sender.gatherer.clear_cache()


def compare_called(got, want):
    for i, (g, w) in enumerate(itertools.zip_longest(got, want)):
        if g != w:
            print(f"Different {i}")
            print(f"  Got : {g}")
            print(f"  Want: {w}")
        else:
            print(f"Same {i}")
            print(f"  Got : {g}")
            print(f"  Want: {w}")
    assert want == got


def compare_received(by_light):
    for light, msgs in by_light.items():
        assert light in devices
        devices.store(light).assertIncoming(*msgs, ignore=[DiscoveryMessages.GetService])
        devices.store(light).clear()


@contextmanager
def modified_time():
    class T:
        def __init__(s):
            s.time = 0

        def __call__(s):
            return s.time

        def forward(s, amount):
            s.time += amount

    t = T()
    with mock.patch("time.time", t):
        yield t


class TestGatherer:

    class TestAPlanSayingNoMessages:

        async def test_it_processes_without_needing_messages(self, sender):
            called = []

            i1 = mock.Mock(name="i1")
            i2 = mock.Mock(name="i2")
            i = {light1.serial: i1, light2.serial: i2}

            class NoMessagesPlan(Plan):
                messages = NoMessages

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append("process")

                    async def info(s):
                        called.append(("info", s.serial))
                        return i[s.serial]

            gatherer = Gatherer(sender)
            plans = make_plans(p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {light1.serial: (True, {"p": i1}), light2.serial: (True, {"p": i2})}

            compare_called(called, [("info", light1.serial), ("info", light2.serial)])

        async def test_it_does_not_process_other_messages(self, sender):
            called = []

            i1 = mock.Mock(name="i1")
            i2 = mock.Mock(name="i2")
            i = {light1.serial: i1, light2.serial: i2}

            class NoMessagesPlan(Plan):
                messages = NoMessages

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append("process")

                    async def info(s):
                        called.append(("info", s.serial))
                        return i[s.serial]

            gatherer = Gatherer(sender)
            plans = make_plans("power", p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {
                light1.serial: (True, {"p": i1, "power": {"level": 0, "on": False}}),
                light2.serial: (True, {"p": i2, "power": {"level": 65535, "on": True}}),
            }

            compare_called(called, [("info", light1.serial), ("info", light2.serial)])

        async def test_it_can_be_determined_by_logic(self, sender):
            called = []
            i1 = mock.Mock(name="i1")

            class NoMessagesPlan(Plan):
                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.serial == light2.serial:
                            return [DeviceMessages.GetLabel()]
                        else:
                            return NoMessages

                    def process(s, pkt):
                        called.append(("process", s.serial))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info", s.serial))
                        if s.serial == light1.serial:
                            return i1
                        else:
                            return s.label

            gatherer = Gatherer(sender)
            plans = make_plans(p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {light1.serial: (True, {"p": i1}), light2.serial: (True, {"p": "sam"})}

            compare_called(
                called,
                [("info", light1.serial), ("process", light2.serial), ("info", light2.serial)],
            )

            compare_received({light1: [], light2: [DeviceMessages.GetLabel()], light3: []})

    class TestAPlanSayingSkip:

        async def test_it_has_no_processing_or_info(self, sender):
            called = []

            class NoMessagesPlan(Plan):
                messages = Skip

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append("process")

                    async def info(s):
                        called.append(("info", s.serial))
                        return True

            gatherer = Gatherer(sender)
            plans = make_plans(p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {light1.serial: (True, {"p": Skip}), light2.serial: (True, {"p": Skip})}

            compare_called(called, [])

        async def test_it_does_not_process_other_messages(self, sender):
            called = []

            class NoMessagesPlan(Plan):
                messages = Skip

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append("process")

                    async def info(s):
                        called.append(("info", s.serial))
                        return True

            gatherer = Gatherer(sender)
            plans = make_plans("power", p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {
                light1.serial: (True, {"p": Skip, "power": {"level": 0, "on": False}}),
                light2.serial: (True, {"p": Skip, "power": {"level": 65535, "on": True}}),
            }

            compare_called(called, [])

        async def test_it_can_be_determined_by_logic(self, sender):
            called = []

            class NoMessagesPlan(Plan):
                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.serial == light2.serial:
                            return [DeviceMessages.GetLabel()]
                        else:
                            return Skip

                    def process(s, pkt):
                        called.append(("process", s.serial))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info", s.serial))
                        return s.label

            gatherer = Gatherer(sender)
            plans = make_plans(p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {light1.serial: (True, {"p": Skip}), light2.serial: (True, {"p": "sam"})}

            compare_called(called, [("process", light2.serial), ("info", light2.serial)])

            compare_received({light1: [], light2: [DeviceMessages.GetLabel()], light3: []})

    class TestAPlanWithNoMessages:

        async def test_it_it_gets_all_other_messages(self, sender):
            called = []

            class NoMessagesPlan(Plan):
                class Instance(Plan.Instance):
                    finished_after_no_more_messages = True

                    def process(s, pkt):
                        assert pkt.serial == s.serial
                        called.append((pkt.serial, pkt.payload.as_dict()))

                    async def info(s):
                        called.append(("info", s.serial))
                        return True

            gatherer = Gatherer(sender)
            plans = make_plans("label", "power", other=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {
                light1.serial: (
                    True,
                    {"label": "bob", "power": {"level": 0, "on": False}, "other": True},
                ),
                light2.serial: (
                    True,
                    {"label": "sam", "power": {"level": 65535, "on": True}, "other": True},
                ),
            }

            compare_called(
                called,
                [
                    (light1.serial, {"label": "bob"}),
                    (light2.serial, {"label": "sam"}),
                    (light1.serial, {"level": 0}),
                    (light2.serial, {"level": 65535}),
                    ("info", light1.serial),
                    ("info", light2.serial),
                ],
            )

        async def test_it_still_finishes_if_no_messages_processed_but_finished_after_no_more_messages(
            self, sender
        ):
            called = []

            class NoMessagesPlan(Plan):
                class Instance(Plan.Instance):
                    finished_after_no_more_messages = True

                    def process(s, pkt):
                        assert pkt.serial == s.serial
                        called.append((pkt.serial, pkt.payload.as_dict()))

                    async def info(s):
                        called.append(("info", s.serial))
                        return True

            gatherer = Gatherer(sender)
            plans = make_plans(other=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {
                light1.serial: (True, {"other": True}),
                light2.serial: (True, {"other": True}),
            }

            compare_called(called, [("info", light1.serial), ("info", light2.serial)])

    class TestAPlanThatNeverFinishes:

        async def test_it_it_doesnt_get_recorded(self, sender):
            called = []

            class NeverFinishedPlan(Plan):
                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("process", pkt.serial))

                    async def info(s):
                        called.append(("info", s.serial))

            gatherer = Gatherer(sender)
            plans = make_plans("label", "power", other=NeverFinishedPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {
                light1.serial: (False, {"label": "bob", "power": {"level": 0, "on": False}}),
                light2.serial: (False, {"label": "sam", "power": {"level": 65535, "on": True}}),
            }

            compare_called(
                called,
                [
                    ("process", light1.serial),
                    ("process", light2.serial),
                    ("process", light1.serial),
                    ("process", light2.serial),
                ],
            )

    class TestAPlanWithMessages:

        async def test_it_messages_are_processed_until_we_say_plan_is_done(self, sender):
            called = []

            class SimplePlan(Plan):
                messages = [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append((pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info", s.serial))
                        return s.label

            gatherer = Gatherer(sender)
            plans = make_plans(simple=SimplePlan())

            found = []
            async for serial, label, info in gatherer.gather(plans, two_lights):
                found.append((serial, label, info))

            assert found == [(light1.serial, "simple", "bob"), (light2.serial, "simple", "sam")]

            compare_received(
                {
                    light1: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()],
                    light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()],
                    light3: [],
                }
            )

            label_type = DeviceMessages.StateLabel.Payload.message_type

            compare_called(
                called,
                [
                    (light1.serial, label_type),
                    ("info", light1.serial),
                    (light2.serial, label_type),
                    ("info", light2.serial),
                ],
            )

        async def test_it_adds_errors_from_info(self, sender):
            error = ValueError("ERROR")

            class ErrorPlan(Plan):
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        if s.serial == light1.serial:
                            raise error
                        return s.label

            gatherer = Gatherer(sender)
            plans = make_plans(label=ErrorPlan())

            found = []
            with assertRaises(ValueError, "ERROR"):
                async for serial, label, info in gatherer.gather(plans, devices.serials):
                    found.append((serial, label, info))

            assert found == [(light2.serial, "label", "sam"), (light3.serial, "label", "strip")]

            errors = []
            found.clear()
            async for serial, label, info in gatherer.gather(
                plans, devices.serials, error_catcher=errors
            ):
                found.append((serial, label, info))
            assert errors == [error]

            assert found == [(light2.serial, "label", "sam"), (light3.serial, "label", "strip")]

        async def test_it_raises_errors_after_yielding_everything(self, sender):
            called = []

            class LabelPlan(Plan):
                messages = [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.label", s.serial))
                        return s.label

            class PowerPlan(Plan):
                messages = [DeviceMessages.GetPower()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("power", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.power", s.serial))
                        return s.level

            class Looker(Plan):
                class Instance(Plan.Instance):
                    finished_after_no_more_messages = True

                    def process(s, pkt):
                        called.append(("looker", pkt.serial, pkt.pkt_type))

                    async def info(s):
                        called.append(("info.looker", s.serial))
                        return True

            gatherer = Gatherer(sender)
            plans = make_plans(power=PowerPlan(), label=LabelPlan(), looker=Looker())

            found = []
            with assertRaises(TimedOut, "Waiting for reply to a packet", serial=light1.serial):
                lost = light1.io["MEMORY"].packet_filter.lost_replies(DeviceMessages.GetLabel)
                with lost:
                    async for serial, label, info in gatherer.gather(
                        plans, two_lights, message_timeout=0.1
                    ):
                        found.append((serial, label, info))

            assert found == [
                (light2.serial, "label", "sam"),
                (light1.serial, "power", 0),
                (light2.serial, "power", 65535),
                (light2.serial, "looker", True),
                (light1.serial, "looker", True),
            ]

            compare_received(
                {
                    light1: [
                        DeviceMessages.GetLabel(),
                        DeviceMessages.GetPower(),
                    ],
                    light2: [
                        DeviceMessages.GetLabel(),
                        DeviceMessages.GetPower(),
                    ],
                    light3: [],
                }
            )

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            compare_called(
                called,
                [
                    ("label", light2.serial, label_type),
                    ("info.label", light2.serial),
                    ("looker", light2.serial, label_type),
                    ("power", light2.serial, label_type),
                    ("label", light1.serial, power_type),
                    ("looker", light1.serial, power_type),
                    ("power", light1.serial, power_type),
                    ("info.power", light1.serial),
                    ("looker", light2.serial, power_type),
                    ("power", light2.serial, power_type),
                    ("info.power", light2.serial),
                    ("info.looker", light2.serial),
                    ("info.looker", light1.serial),
                ],
            )

            found.clear()
            called.clear()
            with assertRaises(TimedOut, "Waiting for reply to a packet", serial=light1.serial):
                lost = light1.io["MEMORY"].packet_filter.lost_replies(DeviceMessages.GetLabel)
                with lost:
                    async for serial, completed, info in gatherer.gather_per_serial(
                        plans, two_lights, message_timeout=0.1
                    ):
                        found.append((serial, completed, info))

            compare_received({light1: [DeviceMessages.GetLabel()], light2: [], light3: []})

            compare_called(called, [("label", light1.serial, power_type)])

            assert found == [
                (light2.serial, True, {"looker": True, "label": "sam", "power": 65535}),
                (light1.serial, False, {"looker": True, "power": 0}),
            ]

            called.clear()
            try:
                lost = light1.io["MEMORY"].packet_filter.lost_replies(DeviceMessages.GetLabel)
                with lost:
                    await gatherer.gather_all(plans, two_lights, message_timeout=0.1)
            except BadRunWithResults as e:
                assert len(e.errors) == 1
                label_type = DeviceMessages.GetLabel.Payload.message_type
                assertSameError(
                    e.errors[0],
                    TimedOut,
                    "Waiting for reply to a packet",
                    dict(serial=light1.serial, sent_pkt_type=label_type),
                    [],
                )
                found = e.kwargs["results"]

            compare_received({light1: [DeviceMessages.GetLabel()], light2: [], light3: []})

            compare_called(called, [("label", light1.serial, power_type)])

            assert found == {
                light2.serial: (True, {"looker": True, "label": "sam", "power": 65535}),
                light1.serial: (False, {"looker": True, "power": 0}),
            }

        async def test_it_doesnt_raise_errors_if_we_have_an_error_catcher(self, sender):
            called = []

            class LabelPlan(Plan):
                messages = [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))
                        print("-" * 20, called[-1])

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.label", s.serial))
                        print("-" * 20, called[-1])
                        return s.label

            class PowerPlan(Plan):
                messages = [DeviceMessages.GetPower()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("power", pkt.serial, pkt.pkt_type))
                        print("-" * 20, called[-1])

                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.power", s.serial))
                        print("-" * 20, called[-1])
                        return s.level

            class Looker(Plan):
                class Instance(Plan.Instance):
                    finished_after_no_more_messages = True

                    def process(s, pkt):
                        called.append(("looker", pkt.serial, pkt.pkt_type))
                        print("-" * 20, called[-1])

                    async def info(s):
                        called.append(("info.looker", s.serial))
                        print("-" * 20, called[-1])
                        return True

            gatherer = Gatherer(sender)
            plans = make_plans(power=PowerPlan(), label=LabelPlan(), looker=Looker())
            error_catcher = []
            kwargs = {"message_timeout": 0.1, "error_catcher": error_catcher}

            def assertError(errors):
                assert len(errors) == 1
                label_type = DeviceMessages.GetLabel.Payload.message_type
                assertSameError(
                    errors[0],
                    TimedOut,
                    "Waiting for reply to a packet",
                    dict(serial=light1.serial, sent_pkt_type=label_type),
                    [],
                )
                errors.clear()

            found = []
            lost = light1.io["MEMORY"].packet_filter.lost_replies(DeviceMessages.GetLabel)
            with lost:
                async for serial, label, info in gatherer.gather(plans, two_lights, **kwargs):
                    found.append((serial, label, info))

            assertError(error_catcher)
            assert found == [
                (light2.serial, "label", "sam"),
                (light1.serial, "power", 0),
                (light2.serial, "power", 65535),
                (light2.serial, "looker", True),
                (light1.serial, "looker", True),
            ]

            compare_received(
                {
                    light1: [
                        DeviceMessages.GetLabel(),
                        DeviceMessages.GetPower(),
                    ],
                    light2: [
                        DeviceMessages.GetLabel(),
                        DeviceMessages.GetPower(),
                    ],
                    light3: [],
                }
            )

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            compare_called(
                called,
                [
                    ("label", light2.serial, label_type),
                    ("info.label", light2.serial),
                    ("looker", light2.serial, label_type),
                    ("power", light2.serial, label_type),
                    ("label", light1.serial, power_type),
                    ("looker", light1.serial, power_type),
                    ("power", light1.serial, power_type),
                    ("info.power", light1.serial),
                    ("looker", light2.serial, power_type),
                    ("power", light2.serial, power_type),
                    ("info.power", light2.serial),
                    ("info.looker", light2.serial),
                    ("info.looker", light1.serial),
                ],
            )

            found.clear()
            called.clear()
            lost = light1.io["MEMORY"].packet_filter.lost_replies(DeviceMessages.GetLabel)
            with lost:
                async for serial, completed, info in gatherer.gather_per_serial(
                    plans, two_lights, **kwargs
                ):
                    found.append((serial, completed, info))

            assertError(error_catcher)
            compare_received({light1: [DeviceMessages.GetLabel()], light2: [], light3: []})

            compare_called(called, [("label", light1.serial, power_type)])

            assert found == [
                (light2.serial, True, {"looker": True, "label": "sam", "power": 65535}),
                (light1.serial, False, {"looker": True, "power": 0}),
            ]

            called.clear()
            lost = light1.io["MEMORY"].packet_filter.lost_replies(DeviceMessages.GetLabel)
            with lost:
                found = dict(await gatherer.gather_all(plans, two_lights, **kwargs))

            assertError(error_catcher)
            compare_received({light1: [DeviceMessages.GetLabel()], light2: [], light3: []})

            compare_called(called, [("label", light1.serial, power_type)])

            assert found == {
                light2.serial: (True, {"looker": True, "label": "sam", "power": 65535}),
                light1.serial: (False, {"looker": True, "power": 0}),
            }

    class TestRefreshing:

        async def test_it_it_can_refresh_always(self, sender):
            called = []

            class LabelPlan(Plan):
                default_refresh = True
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.label", s.serial))
                        return s.label

            gatherer = Gatherer(sender)
            plans = make_plans(label=LabelPlan())
            got = dict(await gatherer.gather_all(plans, light1.serial))
            assert got == {light1.serial: (True, {"label": "bob"})}

            label_type = DeviceMessages.StateLabel.Payload.message_type

            compare_called(
                called, [("label", light1.serial, label_type), ("info.label", light1.serial)]
            )

            compare_received({light1: [DeviceMessages.GetLabel()], light2: [], light3: []})

            called.clear()

            # Get it again, default refresh means it will be cached
            got = dict(await gatherer.gather_all(plans, light1.serial))
            assert got == {light1.serial: (True, {"label": "bob"})}

            compare_called(
                called, [("label", light1.serial, label_type), ("info.label", light1.serial)]
            )

            compare_received({light1: [DeviceMessages.GetLabel()], light2: [], light3: []})

            called.clear()

            # We can override refresh
            plans = make_plans(label=LabelPlan(refresh=False))
            got = dict(await gatherer.gather_all(plans, light1.serial))
            assert got == {light1.serial: (True, {"label": "bob"})}

            compare_called(called, [])
            compare_received({light1: [], light2: [], light3: []})

        async def test_it_it_can_refresh_on_time(self, sender):
            with modified_time() as t:
                called = []

                class LabelPlan(Plan):
                    default_refresh = 1
                    messages = [DeviceMessages.GetLabel()]

                    class Instance(Plan.Instance):
                        def process(s, pkt):
                            called.append(("label", pkt.serial, pkt.pkt_type))

                            if pkt | DeviceMessages.StateLabel:
                                s.label = pkt.label
                                return True

                        async def info(s):
                            called.append(("info.label", s.serial))
                            return s.label

                gatherer = Gatherer(sender)
                plans = make_plans(label=LabelPlan())
                got = dict(await gatherer.gather_all(plans, light1.serial))
                assert got == {light1.serial: (True, {"label": "bob"})}

                label_type = DeviceMessages.StateLabel.Payload.message_type

                compare_called(
                    called, [("label", light1.serial, label_type), ("info.label", light1.serial)]
                )

                compare_received({light1: [DeviceMessages.GetLabel()], light2: [], light3: []})

                called.clear()

                # Get it again, our refresh means it will be cached
                t.forward(0.6)
                plans = make_plans(label=LabelPlan())
                got = dict(await gatherer.gather_all(plans, light1.serial))
                assert got == {light1.serial: (True, {"label": "bob"})}

                compare_called(called, [])
                compare_received({light1: [], light2: [], light3: []})

                # After a second, we get refreshed
                t.forward(0.5)
                got = dict(await gatherer.gather_all(plans, light1.serial))
                assert got == {light1.serial: (True, {"label": "bob"})}

                compare_called(
                    called, [("label", light1.serial, label_type), ("info.label", light1.serial)]
                )

                compare_received({light1: [DeviceMessages.GetLabel()], light2: [], light3: []})
                called.clear()

                # Get it again, our refresh means it will be cached
                t.forward(0.6)
                plans = make_plans(label=LabelPlan())
                got = dict(await gatherer.gather_all(plans, two_lights))
                assert got == {
                    light1.serial: (True, {"label": "bob"}),
                    light2.serial: (True, {"label": "sam"}),
                }

                compare_called(
                    called, [("label", light2.serial, label_type), ("info.label", light2.serial)]
                )
                compare_received({light1: [], light2: [DeviceMessages.GetLabel()], light3: []})
                called.clear()

                # After a second, we get light1 refreshed
                t.forward(0.5)
                got = dict(await gatherer.gather_all(plans, two_lights))
                assert got == {
                    light1.serial: (True, {"label": "bob"}),
                    light2.serial: (True, {"label": "sam"}),
                }

                compare_called(
                    called, [("label", light1.serial, label_type), ("info.label", light1.serial)]
                )

                compare_received({light1: [DeviceMessages.GetLabel()], light2: [], light3: []})

                called.clear()

                # After two seconds, we get both refreshed
                t.forward(2)
                got = dict(await gatherer.gather_all(plans, two_lights))
                assert got == {
                    light1.serial: (True, {"label": "bob"}),
                    light2.serial: (True, {"label": "sam"}),
                }

                compare_called(
                    called,
                    [
                        ("label", light1.serial, label_type),
                        ("info.label", light1.serial),
                        ("label", light2.serial, label_type),
                        ("info.label", light2.serial),
                    ],
                )

                compare_received(
                    {
                        light1: [DeviceMessages.GetLabel()],
                        light2: [DeviceMessages.GetLabel()],
                        light3: [],
                    }
                )

                called.clear()

        async def test_it_cannot_steal_messages_from_completed_plans_if_we_refresh_messages_those_other_plans_use(
            self, sender
        ):
            called = []

            class ReverseLabelPlan(Plan):
                messages = [DeviceMessages.GetLabel()]
                default_refresh = False

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("reverse", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.reverse", s.serial))
                        return "".join(reversed(s.label))

            class LabelPlan(Plan):
                messages = [DeviceMessages.GetLabel()]
                default_refresh = True

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.label", s.serial))
                        return s.label

            gatherer = Gatherer(sender)
            plans = make_plans(rev=ReverseLabelPlan(), label=LabelPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))
            assert got == {
                light1.serial: (True, {"label": "bob", "rev": "bob"}),
                light2.serial: (True, {"label": "sam", "rev": "mas"}),
            }

            label_type = DeviceMessages.StateLabel.Payload.message_type

            compare_called(
                called,
                [
                    ("label", light1.serial, label_type),
                    ("info.label", light1.serial),
                    ("reverse", light1.serial, label_type),
                    ("info.reverse", light1.serial),
                    ("label", light2.serial, label_type),
                    ("info.label", light2.serial),
                    ("reverse", light2.serial, label_type),
                    ("info.reverse", light2.serial),
                ],
            )

            compare_received(
                {
                    light1: [DeviceMessages.GetLabel()],
                    light2: [DeviceMessages.GetLabel()],
                    light3: [],
                }
            )

            called.clear()

            # Get it again, our refresh means we process LabelPlan again,
            # but using results from ReverseLabelPlan
            got = dict(await gatherer.gather_all(plans, two_lights))
            assert got == {
                light1.serial: (True, {"label": "bob", "rev": "bob"}),
                light2.serial: (True, {"label": "sam", "rev": "mas"}),
            }

            compare_called(
                called,
                [
                    ("label", light1.serial, label_type),
                    ("info.label", light1.serial),
                    ("label", light2.serial, label_type),
                    ("info.label", light2.serial),
                ],
            )

            compare_received(
                {
                    light1: [DeviceMessages.GetLabel()],
                    light2: [DeviceMessages.GetLabel()],
                    light3: [],
                }
            )

        async def test_it_has_no_cached_completed_data_if_instance_has_no_key(self, sender):
            called = []

            class ReverseLabelPlan(Plan):
                messages = [DeviceMessages.GetLabel()]
                default_refresh = False

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("reverse", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.reverse", s.serial))
                        return "".join(reversed(s.label))

            class LabelPlan(Plan):
                messages = [DeviceMessages.GetLabel()]
                default_refresh = False

                class Instance(Plan.Instance):
                    def key(s):
                        return None

                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.label", s.serial))
                        return s.label

            gatherer = Gatherer(sender)
            plans = make_plans(rev=ReverseLabelPlan(), label=LabelPlan())
            got = dict(await gatherer.gather_all(plans, two_lights))
            assert got == {
                light1.serial: (True, {"label": "bob", "rev": "bob"}),
                light2.serial: (True, {"label": "sam", "rev": "mas"}),
            }

            label_type = DeviceMessages.StateLabel.Payload.message_type

            compare_called(
                called,
                [
                    ("label", light1.serial, label_type),
                    ("info.label", light1.serial),
                    ("reverse", light1.serial, label_type),
                    ("info.reverse", light1.serial),
                    ("label", light2.serial, label_type),
                    ("info.label", light2.serial),
                    ("reverse", light2.serial, label_type),
                    ("info.reverse", light2.serial),
                ],
            )

            compare_received(
                {
                    light1: [DeviceMessages.GetLabel()],
                    light2: [DeviceMessages.GetLabel()],
                    light3: [],
                }
            )

            called.clear()

            # Get it again, our refresh means we process LabelPlan again,
            # but using results from ReverseLabelPlan
            got = dict(await gatherer.gather_all(plans, two_lights))
            assert got == {
                light1.serial: (True, {"label": "bob", "rev": "bob"}),
                light2.serial: (True, {"label": "sam", "rev": "mas"}),
            }

            compare_called(
                called,
                [
                    ("label", light1.serial, label_type),
                    ("info.label", light1.serial),
                    ("label", light2.serial, label_type),
                    ("info.label", light2.serial),
                ],
            )

            compare_received({light1: [], light2: [], light3: []})

    class TestDependencies:

        async def test_it_it_can_get_dependencies(self, sender):
            called = []

            class PowerPlan(Plan):
                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.serial == light3.serial:
                            return Skip
                        else:
                            return [DeviceMessages.GetPower()]

                    def process(s, pkt):
                        called.append(("power.process.power", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.power", s.serial))
                        return s.level

            class InfoPlan(Plan):
                messages = [DeviceMessages.GetLabel()]
                dependant_info = {"p": PowerPlan()}

                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.deps["p"] == 0:
                            return [LightMessages.GetInfrared()]
                        else:
                            return [DeviceMessages.GetLabel()]

                    def process(s, pkt):

                        if pkt | DeviceMessages.StateLabel:
                            called.append(("info.process.label", pkt.serial, pkt.pkt_type))
                            s.i = pkt.label
                            return True
                        elif pkt | LightMessages.StateInfrared:
                            called.append(("info.process.infrared", pkt.serial, pkt.pkt_type))
                            s.i = pkt.brightness
                            return True
                        elif pkt | DeviceMessages.StatePower:
                            called.append(("info.process.power", pkt.serial, pkt.pkt_type))

                    async def info(s):
                        called.append(("info.info", s.serial))
                        return {"power": s.deps["p"], "info": s.i}

            gatherer = Gatherer(sender)
            plans = make_plans(info=InfoPlan())
            got = dict(await gatherer.gather_all(plans, devices.serials))

            assert got == {
                light1.serial: (True, {"info": {"power": 0, "info": 100}}),
                light2.serial: (True, {"info": {"power": 65535, "info": "sam"}}),
                light3.serial: (True, {"info": {"power": Skip, "info": "strip"}}),
            }

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type
            infrared_type = LightMessages.StateInfrared.Payload.message_type

            compare_called(
                called,
                [
                    ("power.process.power", light1.serial, power_type),
                    ("info.power", light1.serial),
                    ("power.process.power", light2.serial, power_type),
                    ("info.power", light2.serial),
                    ("info.process.label", light3.serial, label_type),
                    ("info.info", light3.serial),
                    ("info.process.power", light1.serial, power_type),
                    ("info.process.power", light2.serial, power_type),
                    ("info.process.infrared", light1.serial, infrared_type),
                    ("info.info", light1.serial),
                    ("info.process.label", light2.serial, label_type),
                    ("info.info", light2.serial),
                ],
            )

            compare_received(
                {
                    light1: [DeviceMessages.GetPower(), LightMessages.GetInfrared()],
                    light2: [DeviceMessages.GetPower(), DeviceMessages.GetLabel()],
                    light3: [DeviceMessages.GetLabel()],
                }
            )

        async def test_it_it_can_get_dependencies_of_dependencies_and_messages_can_be_shared(
            self, sender
        ):
            called = []

            class Plan1(Plan):
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan1", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.plan1", s.serial))
                        return s.label

            class Plan2(Plan):
                messages = [DeviceMessages.GetLabel()]
                dependant_info = {"l": Plan1()}

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan2", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.plan2", s.serial))
                        return {"label": s.deps["l"], "rev": "".join(reversed(s.label))}

            class Plan3(Plan):
                messages = [DeviceMessages.GetPower()]
                dependant_info = {"p": Plan2()}

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan3", pkt.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.plan3", s.serial))
                        return (s.level, s.deps["p"])

            gatherer = Gatherer(sender)
            plans = make_plans(plan3=Plan3())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {
                light1.serial: (True, {"plan3": (0, {"label": "bob", "rev": "bob"})}),
                light2.serial: (True, {"plan3": (65535, {"label": "sam", "rev": "mas"})}),
            }

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            compare_called(
                called,
                [
                    ("plan1", light1.serial, label_type),
                    ("info.plan1", light1.serial),
                    ("plan1", light2.serial, label_type),
                    ("info.plan1", light2.serial),
                    ("plan2", light1.serial, label_type),
                    ("info.plan2", light1.serial),
                    ("plan2", light2.serial, label_type),
                    ("info.plan2", light2.serial),
                    ("plan3", light1.serial, label_type),
                    ("plan3", light2.serial, label_type),
                    ("plan3", light1.serial, power_type),
                    ("info.plan3", light1.serial),
                    ("plan3", light2.serial, power_type),
                    ("info.plan3", light2.serial),
                ],
            )

            compare_received(
                {
                    light1: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()],
                    light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()],
                    light3: [],
                }
            )

        async def test_it_it_can_skip_based_on_dependency(self, sender):
            called = []

            class Plan1(Plan):
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan1", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.plan1", s.serial))
                        return s.label

            class Plan2(Plan):
                dependant_info = {"l": Plan1()}

                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.deps["l"] == "bob":
                            return Skip
                        else:
                            return [DeviceMessages.GetPower()]

                    def process(s, pkt):
                        called.append(("plan2", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.plan2", s.serial))
                        return {"label": s.deps["l"], "power": s.level}

            gatherer = Gatherer(sender)
            plans = make_plans(plan2=Plan2())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {
                light1.serial: (True, {"plan2": Skip}),
                light2.serial: (True, {"plan2": {"label": "sam", "power": 65535}}),
            }

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            compare_called(
                called,
                [
                    ("plan1", light1.serial, label_type),
                    ("info.plan1", light1.serial),
                    ("plan1", light2.serial, label_type),
                    ("info.plan1", light2.serial),
                    ("plan2", light2.serial, label_type),
                    ("plan2", light2.serial, power_type),
                    ("info.plan2", light2.serial),
                ],
            )

            compare_received(
                {
                    light1: [DeviceMessages.GetLabel()],
                    light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()],
                    light3: [],
                }
            )

        async def test_it_can_get_results_from_deps_as_well(self, sender):
            called = []

            class Plan1(Plan):
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan1", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.plan1", s.serial))
                        return s.label

            class Plan2(Plan):
                dependant_info = {"l": Plan1()}

                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.deps["l"] == "bob":
                            return Skip
                        else:
                            return [DeviceMessages.GetPower()]

                    def process(s, pkt):
                        called.append(("plan2", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.plan2", s.serial))
                        return {"label": s.deps["l"], "power": s.level}

            gatherer = Gatherer(sender)
            plans = make_plans(plan1=Plan1(), plan2=Plan2())
            got = dict(await gatherer.gather_all(plans, two_lights))

            assert got == {
                light1.serial: (True, {"plan1": "bob", "plan2": Skip}),
                light2.serial: (True, {"plan1": "sam", "plan2": {"label": "sam", "power": 65535}}),
            }

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            compare_called(
                called,
                [
                    ("plan1", light1.serial, label_type),
                    ("info.plan1", light1.serial),
                    ("plan1", light2.serial, label_type),
                    ("info.plan1", light2.serial),
                    ("plan2", light2.serial, label_type),
                    ("plan2", light2.serial, power_type),
                    ("info.plan2", light2.serial),
                ],
            )

            compare_received(
                {
                    light1: [DeviceMessages.GetLabel()],
                    light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()],
                    light3: [],
                }
            )

        async def test_it_chain_is_broken_when_dep_cant_get_results(self, sender):
            called = []

            class Plan1(Plan):
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan1", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.plan1", s.serial))
                        return s.label

            class Plan2(Plan):
                dependant_info = {"l": Plan1()}

                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.deps["l"] == "bob":
                            return Skip
                        else:
                            return [DeviceMessages.GetPower()]

                    def process(s, pkt):
                        called.append(("plan2", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.plan2", s.serial))
                        return {"label": s.deps["l"], "power": s.level}

            gatherer = Gatherer(sender)
            plans = make_plans("presence", plan2=Plan2())
            errors = []
            lost = light3.io["MEMORY"].packet_filter.lost_replies(DeviceMessages.GetLabel)
            with lost:
                got = dict(
                    await gatherer.gather_all(
                        plans, devices.serials, error_catcher=errors, message_timeout=0.1
                    )
                )
            assert len(errors) == 1

            assert got == {
                light1.serial: (True, {"presence": True, "plan2": Skip}),
                light2.serial: (
                    True,
                    {"presence": True, "plan2": {"label": "sam", "power": 65535}},
                ),
                light3.serial: (False, {"presence": True}),
            }

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            compare_called(
                called,
                [
                    ("plan1", light1.serial, label_type),
                    ("info.plan1", light1.serial),
                    ("plan1", light2.serial, label_type),
                    ("info.plan1", light2.serial),
                    ("plan2", light2.serial, label_type),
                    ("plan2", light2.serial, power_type),
                    ("info.plan2", light2.serial),
                ],
            )

            compare_received(
                {
                    light1: [DeviceMessages.GetLabel()],
                    light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()],
                    light3: [DeviceMessages.GetLabel()],
                }
            )
