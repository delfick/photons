import itertools
import logging
from contextlib import contextmanager
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import dictobj, sb
from photons_app.mimic.attrs import Attrs, ChangeAttr
from photons_app.mimic.device import Device, DeviceSession, ExpectedOneMessage
from photons_app.mimic.event import Events
from photons_app.mimic.operator import IO, Operator, Viewer
from photons_app.mimic.operators.listener import Listener
from photons_messages import DeviceMessages, Services, protocol_register
from photons_products import Products


@pytest.fixture()
def device():
    return Device("d073d5001337", Products.LCM2_A19, Device.Firmware(2, 80, 1610929753000000000))


class TestDeviceSession:
    def test_it_is_returned_from_the_sesion_on_the_device(self, device, final_future):
        session = device.session(final_future)
        assert isinstance(session, DeviceSession)
        assert session.final_future is final_future
        assert session.device is device

    async def test_it_follows_a_prepare_reset_delete_protocol_with_io_operators_started(self, final_future, device):
        called = []
        async with pytest.helpers.FutureDominoes(expected=9) as futs:

            async def prepare():
                await futs[1]
                called.append("prepare")

            async def reset():
                await futs[5]
                called.append("reset")

            async def delete():
                await futs[9]
                called.append("delete")

            class IO1(IO):
                io_source = "io1"

                async def start_session(s, final_future, parent_ts):
                    await futs[2]
                    called.append("io1 start")

                async def finish_session(s):
                    await futs[8]
                    called.append("io1 finish")

            class IO2(IO):
                io_source = "io2"

                async def start_session(s, final_future, parent_ts):
                    await futs[4]
                    called.append("io2 start")

                async def finish_session(s):
                    await futs[6]
                    called.append("io2 finish")

            class IO3(IO):
                io_source = "io3"

                async def start_session(s, final_future, parent_ts):
                    await futs[3]
                    called.append("io3 start")

                async def finish_session(s):
                    await futs[7]
                    called.append("io3 finish")

            device.io = {}
            for io in (IO1(device), IO2(device), IO3(device)):
                device.io[io.__class__.__name__] = io

            with mock.patch.multiple(device, prepare=prepare, reset=reset, delete=delete):
                assert called == []

                async with DeviceSession(final_future, device):
                    assert called == ["prepare", "io1 start", "io3 start", "io2 start", "reset"]

                assert called == [
                    "prepare",
                    "io1 start",
                    "io3 start",
                    "io2 start",
                    "reset",
                    "io2 finish",
                    "io3 finish",
                    "io1 finish",
                    "delete",
                ]

    async def test_it_follows_a_prepare_reset_delete_protocol_even_if_io_operators_fail(self, final_future, device):
        called = []
        async with pytest.helpers.FutureDominoes(expected=8) as futs:
            error1 = KeyError("nope")
            error2 = KeyError("nup")

            async def prepare():
                await futs[1]
                called.append("prepare")

            async def reset():
                called.append("reset")

            async def delete():
                await futs[8]
                called.append("delete")

            class IO1(IO):
                io_source = "io1"

                async def start_session(s, final_future, parent_ts):
                    await futs[2]
                    called.append("io1 start")
                    raise error1

                async def finish_session(s):
                    await futs[7]
                    called.append("io1 finish")

            class IO2(IO):
                io_source = "io2"

                async def start_session(s, final_future, parent_ts):
                    await futs[4]
                    called.append("io2 start")

                async def finish_session(s):
                    called.append("io2 finish")
                    await futs[5]
                    raise error2

            class IO3(IO):
                io_source = "io3"

                async def start_session(s, final_future, parent_ts):
                    await futs[3]
                    called.append("io3 start")

                async def finish_session(s):
                    called.append("io3 finish")
                    await futs[6]

            device.io = {}
            for io in (IO1(device), IO2(device), IO3(device)):
                device.io[io.__class__.__name__] = io

            with mock.patch.multiple(device, prepare=prepare, reset=reset, delete=delete):
                assert called == []

                try:
                    async with DeviceSession(final_future, device):
                        pass
                except Exception as err:
                    assert err is error2

                assert called == [
                    "prepare",
                    "io1 start",
                    "io3 start",
                    "io2 start",
                    "io2 finish",
                    "io3 finish",
                    "io1 finish",
                    "delete",
                ]


class TestDevice:
    def test_it_takes_in_default_informations(self):
        serial = "d073d5676767"
        device = Device(serial, Products.LCM2_A19, Device.Firmware(2, 80, 0))
        assert device.serial == serial
        assert device.product is Products.LCM2_A19
        assert device.firmware == Device.Firmware(2, 80, 0)

        assert not device.has_power
        assert device.original_firmware == Device.Firmware(2, 80, 0)
        assert device.search_for_operators
        assert device.protocol_register is protocol_register
        assert device.value_store == {}
        assert not device.applied_options
        assert isinstance(device.attrs, Attrs)
        assert device.attrs._device is device
        assert device.options == []

    def test_it_takes_in_other_informations(self):
        value_store = mock.Mock(name="value_store")
        option1 = mock.Mock(name="option1")
        option2 = mock.Mock(name="option2")

        serial = "d073d5676767"
        device = Device(
            serial,
            Products.LCM2_A19,
            Device.Firmware(2, 80, 0),
            option1,
            option2,
            value_store=value_store,
            search_for_operators=False,
        )
        assert device.serial == serial
        assert device.product is Products.LCM2_A19
        assert device.firmware == Device.Firmware(2, 80, 0)

        assert not device.has_power
        assert device.original_firmware == Device.Firmware(2, 80, 0)
        assert not device.search_for_operators
        assert device.protocol_register is protocol_register
        assert device.value_store is value_store
        assert not device.applied_options
        assert isinstance(device.attrs, Attrs)
        assert device.attrs._device is device
        assert device.options == [option1, option2]

    def test_it_can_get_the_operator_register(self, device):
        reg = __import__("photons_app.mimic.operator").mimic.operator.register
        assert device.operators_register is reg

    def test_it_can_make_a_session(self, final_future):
        device = Device("d073d5001337", Products.LCM2_A19, Device.Firmware(2, 80, 0))

        session = device.session(final_future)
        assert isinstance(session, DeviceSession)
        assert session.final_future is final_future
        assert session.device is device

    def test_it_disallows_changing_the_product_of_a_device_or_its_capability(self):
        device = Device("d073d5001337", Products.LCM2_A19, Device.Firmware(2, 80, 0))

        with assertRaises(AttributeError):
            device.product = Products.LCM3_MINI_COLOR

        assert device.product is Products.LCM2_A19
        assert device.cap.product is Products.LCM2_A19

        cap = Products.LCM3_MINI_COLOR.cap(2, 90)
        with assertRaises(AttributeError):
            device.cap = cap

        assert device.product is Products.LCM2_A19
        assert device.cap.product is Products.LCM2_A19

    async def test_it_can_get_state_from_operators(self, final_future):
        called = []

        state_power = DeviceMessages.StatePower(level=0)

        state_label1 = DeviceMessages.StateLabel(label="hello")
        state_label2 = DeviceMessages.StateLabel(label="hello")

        state_group1 = DeviceMessages.StateGroup(group="aa", label="G", updated_at=0)
        state_group2 = DeviceMessages.StateGroup(group="bb", label="H", updated_at=1)

        class operator1(Operator):
            def make_state_for(self, kls, result):
                called.append(("operator1", kls, id(result)))
                if kls | DeviceMessages.StateGroup:
                    result.append(state_group1)

        class operator2(Operator):
            def make_state_for(self, kls, result):
                called.append(("operator2", kls, id(result)))
                if kls | DeviceMessages.StateGroup:
                    result.clear()
                    result.append(state_group2)

        class operator3(Operator):
            def make_state_for(self, kls, result):
                called.append(("operator3", kls, id(result)))
                if kls | DeviceMessages.StatePower:
                    result.append(state_power)
                if kls | DeviceMessages.StateLabel:
                    result.append(state_label1)

        class viewer(Viewer):
            def make_state_for(self, kls, result):
                assert False, "Should not be called"

        class io1(IO):
            io_source = "IOtest1"

            async def apply(self):
                self.device.io[self.io_source] = self

            def make_state_for(self, kls, result):
                called.append(("io1", kls, id(result)))
                if kls | DeviceMessages.StateLabel:
                    result.append(state_label2)

        class io2(IO):
            io_source = "IOtest2"

            async def apply(self):
                self.device.io[self.io_source] = self

            def make_state_for(self, kls, result):
                called.append(("io2", kls, id(result)))

        device = Device(
            "d073d5001448",
            Products.LCM2_A19,
            Device.Firmware(2, 80, 0),
            lambda d: operator1(d),
            lambda d: operator2(d),
            lambda d: operator3(d),
            lambda d: io1(d),
            lambda d: io2(d),
            lambda d: Listener(d),
            search_for_operators=False,
        )

        async with device.session(final_future):
            assert not called

            # Can get a single
            assert device.state_for(DeviceMessages.StatePower) is state_power
            assert called == [
                ("io1", DeviceMessages.StatePower, mock.ANY),
                ("io2", DeviceMessages.StatePower, mock.ANY),
                ("operator1", DeviceMessages.StatePower, mock.ANY),
                ("operator2", DeviceMessages.StatePower, mock.ANY),
                ("operator3", DeviceMessages.StatePower, mock.ANY),
            ]
            assert list(set([item[-1] for item in called])) == [called[0][-1]]
            called.clear()

            # Can complain on getting nothing
            with assertRaises(ExpectedOneMessage, got=0):
                device.state_for(DeviceMessages.StateLocation)
            assert called == [
                ("io1", DeviceMessages.StateLocation, mock.ANY),
                ("io2", DeviceMessages.StateLocation, mock.ANY),
                ("operator1", DeviceMessages.StateLocation, mock.ANY),
                ("operator2", DeviceMessages.StateLocation, mock.ANY),
                ("operator3", DeviceMessages.StateLocation, mock.ANY),
            ]
            assert list(set([item[-1] for item in called])) == [called[0][-1]]
            called.clear()

            # can be told to not care about getting nothing
            assert device.state_for(DeviceMessages.StateLocation, expect_any=False, expect_one=False) == []
            assert called == [
                ("io1", DeviceMessages.StateLocation, mock.ANY),
                ("io2", DeviceMessages.StateLocation, mock.ANY),
                ("operator1", DeviceMessages.StateLocation, mock.ANY),
                ("operator2", DeviceMessages.StateLocation, mock.ANY),
                ("operator3", DeviceMessages.StateLocation, mock.ANY),
            ]
            assert list(set([item[-1] for item in called])) == [called[0][-1]]
            called.clear()

            # getting multiple is bad by default
            with assertRaises(ExpectedOneMessage, got=2):
                device.state_for(DeviceMessages.StateLabel)
            assert called == [
                ("io1", DeviceMessages.StateLabel, mock.ANY),
                ("io2", DeviceMessages.StateLabel, mock.ANY),
                ("operator1", DeviceMessages.StateLabel, mock.ANY),
                ("operator2", DeviceMessages.StateLabel, mock.ANY),
                ("operator3", DeviceMessages.StateLabel, mock.ANY),
            ]
            assert list(set([item[-1] for item in called])) == [called[0][-1]]
            called.clear()

            # getting multiple can be good though
            assert device.state_for(DeviceMessages.StateLabel, expect_one=False) == [
                state_label1,
                state_label2,
            ]
            assert called == [
                ("io1", DeviceMessages.StateLabel, mock.ANY),
                ("io2", DeviceMessages.StateLabel, mock.ANY),
                ("operator1", DeviceMessages.StateLabel, mock.ANY),
                ("operator2", DeviceMessages.StateLabel, mock.ANY),
                ("operator3", DeviceMessages.StateLabel, mock.ANY),
            ]
            assert list(set([item[-1] for item in called])) == [called[0][-1]]
            called.clear()

            # and it's possible for one operator to cancel another
            assert device.state_for(DeviceMessages.StateGroup) == state_group2
            assert called == [
                ("io1", DeviceMessages.StateGroup, mock.ANY),
                ("io2", DeviceMessages.StateGroup, mock.ANY),
                ("operator1", DeviceMessages.StateGroup, mock.ANY),
                ("operator2", DeviceMessages.StateGroup, mock.ANY),
                ("operator3", DeviceMessages.StateGroup, mock.ANY),
            ]
            assert list(set([item[-1] for item in called])) == [called[0][-1]]
            called.clear()

    class TestPrepare:
        async def test_it_instantiates_operator_collections_and_applies_options(self):
            info = {"device": None}

            @contextmanager
            def these_options():
                op1 = mock.NonCallableMock(name="op1")
                op2 = mock.NonCallableMock(name="op2")
                op3 = mock.NonCallableMock(name="op3")

                called = []

                def func(d):
                    assert info["device"] is not None
                    assert d is info["device"]
                    called.append("func")
                    return op1

                class Selector:
                    @classmethod
                    def select(kls, d):
                        assert info["device"] is not None
                        assert d is info["device"]
                        called.append("select")
                        return op3

                async def apply1():
                    called.append("apply1")

                async def apply2():
                    called.append("apply2")

                async def apply3():
                    called.append("apply3")

                op1.apply = pytest.helpers.AsyncMock(name="apply1", side_effect=apply1)
                op2.apply = pytest.helpers.AsyncMock(name="apply2", side_effect=apply2)
                op3.apply = pytest.helpers.AsyncMock(name="apply3", side_effect=apply3)

                yield func, op2, Selector

                assert called == ["func", "apply1", "apply2", "select", "apply3"]

            with these_options() as (func, op2, Selector):
                device = Device(
                    "d073d5001337",
                    Products.LCM2_A19,
                    Device.Firmware(2, 80, 0),
                    func,
                    op2,
                    Selector,
                    search_for_operators=False,
                )
                info["device"] = device
                assert not hasattr(device, "io")
                assert not hasattr(device, "viewers")
                assert not hasattr(device, "operators")
                assert not device.applied_options

                def not_used(device):
                    assert False, "Should not be used"

                register = [not_used]
                with mock.patch.object(device, "operators_register", register):
                    await device.prepare()

            assert device.io == {}
            assert device.viewers == []
            assert device.operators == []
            assert device.applied_options

            with these_options() as opts1, these_options() as opts2:
                device = Device(
                    "d073d5001337",
                    Products.LCM2_A19,
                    Device.Firmware(2, 80, 0),
                    *opts1,
                    search_for_operators=True,
                )
                info["device"] = device
                assert not hasattr(device, "io")
                assert not hasattr(device, "viewers")
                assert not hasattr(device, "operators")
                assert not device.applied_options

                register = [*opts2]
                with mock.patch.object(device, "operators_register", register):
                    await device.prepare()

            assert device.io == {}
            assert device.viewers == []
            assert device.operators == []
            assert device.applied_options

    class TestEvents:
        @pytest.fixture()
        def record(self):
            class Record:
                def __init__(s):
                    s.record = []
                    s._intercept = None

                def intercept(s, operator, *v):
                    if s._intercept:
                        return s._intercept(operator, *v)
                    else:
                        return (operator, v)

                def clear(s):
                    s.record.clear()

                def __bool__(s):
                    return bool(s.record)

                def __eq__(s, other):
                    recorded = [v for _, v in s.record if v]
                    if recorded == other:
                        return True

                    for i, (r, w) in enumerate(itertools.zip_longest(recorded, other)):
                        if r != w:
                            print(f"Different item: {i}")
                            print(f"    Recorded  : {r}")
                            print(f"    Want      : {w}")
                            print("==")
                        else:
                            print(f"Same item    : {i}")
                            print(f"    Recorded : {r}")
                            print(f"    Want     : {w}")
                            print("==")
                    return recorded == other

                def add(s, operator, *v):
                    s.record.append(s.intercept(operator, *v))

            return Record()

        @pytest.fixture()
        async def device(self, record, final_future):
            class operator(Operator):
                class Options(dictobj.Spec):
                    one = dictobj.Field(sb.string_spec())
                    two = dictobj.Field(sb.string_spec())

                attrs = [
                    Operator.Attr.Lambda(
                        "three",
                        from_zero=lambda event, options: 1,
                        from_options=lambda event, options: options.one,
                    ),
                    Operator.Attr.Lambda(
                        "four",
                        from_zero=lambda event, options: 2,
                        from_options=lambda event, options: options.two,
                    ),
                    Operator.Attr.Lambda(
                        "five",
                        from_zero=lambda event, options: 3,
                    ),
                ]

                async def respond(self, event):
                    record.add(self, "operator", event)

                async def reset(self, event):
                    record.add(self, "reset_operator", event)
                    await super().reset(event)

                async def power_on(self, event):
                    record.add(self, "power_on_operator", event)

                async def shutting_down(self, event):
                    record.add(self, "shutting_down_operator", event)

            class viewer(Viewer):
                async def respond(self, event):
                    record.add(self, "viewer", event)

                async def reset(self, event):
                    record.add(self, "reset_viewer", event)
                    await super().reset(event)

                async def power_on(self, event):
                    record.add(self, "power_on_viewer", event)

                async def shutting_down(self, event):
                    record.add(self, "shutting_down_viewer", event)

            class io(IO):
                io_source = "IOtest"

                async def apply(self):
                    self.device.io[self.io_source] = self

                async def power_on(self, event):
                    record.add(self, "power_on_io", event)
                    await super().power_on(event)

                async def shutting_down(self, event):
                    record.add(self, "shutting_down_io", event)
                    await super().shutting_down(event)

                async def respond(self, event):
                    record.add(self, "io", event)

                async def reset(self, event):
                    record.add(self, "reset_io", event)
                    await super().reset(event)

            class D(Device):
                async def execute_event(s, event, is_finished):
                    record.add(None, "execute_event", event, is_finished)
                    return await super().execute_event(event, is_finished)

            device = D(
                "d073d5001448",
                Products.LCM2_A19,
                Device.Firmware(2, 80, 0),
                lambda d: operator(d, {"one": "blah", "two": "stuff"}),
                lambda d: viewer(d),
                lambda d: io(d),
                lambda d: Listener(d),
                search_for_operators=False,
            )

            attr_change_event = Events.ATTRIBUTE_CHANGE(
                device,
                [
                    ChangeAttr.test("three", "blah"),
                    ChangeAttr.test("four", "stuff"),
                    ChangeAttr.test("five", 3),
                ],
                False,
            )

            async with device.session(final_future):
                reset_event = Events.RESET(device, old_attrs={})
                assert record == [
                    ("execute_event", Events.SHUTTING_DOWN(device), None),
                    ("shutting_down_viewer", Events.SHUTTING_DOWN(device)),
                    ("shutting_down_operator", Events.SHUTTING_DOWN(device)),
                    ("viewer", Events.SHUTTING_DOWN(device)),
                    ("io", Events.SHUTTING_DOWN(device)),
                    ("operator", Events.SHUTTING_DOWN(device)),
                    #
                    ("execute_event", Events.POWER_OFF(device), None),
                    ("viewer", Events.POWER_OFF(device)),
                    ("io", Events.POWER_OFF(device)),
                    ("operator", Events.POWER_OFF(device)),
                    #
                    ("execute_event", reset_event, None),
                    ("reset_viewer", reset_event),
                    ("reset_io", reset_event),
                    ("reset_operator", reset_event),
                    #
                    ("execute_event", attr_change_event, None),
                    # No viewer because this happens before the device has started
                    ("io", attr_change_event),
                    ("operator", attr_change_event),
                    #
                    ("viewer", reset_event),
                    ("io", reset_event),
                    ("operator", reset_event),
                    #
                    ("execute_event", Events.POWER_ON(device), None),
                    ("power_on_viewer", Events.POWER_ON(device)),
                    ("power_on_io", Events.POWER_ON(device)),
                    ("power_on_operator", Events.POWER_ON(device)),
                    ("viewer", Events.POWER_ON(device)),
                    ("io", Events.POWER_ON(device)),
                    ("operator", Events.POWER_ON(device)),
                ]
                record.clear()
                yield device

        class TestFiring:
            async def test_it_has_a_shortcut_to_event_with_options(self):
                arg1 = mock.Mock(name="arg1")
                arg2 = mock.Mock(name="arg2")
                kwarg3 = mock.Mock(name="kwarg3")
                kwarg4 = mock.Mock(name="kwarg4")

                ret = mock.Mock(name="ret")
                event_with_options = pytest.helpers.AsyncMock(name="event_with_options", return_value=ret)

                device = Device("d073d5001337", Products.LCM2_A19, Device.Firmware(2, 80, 0))

                with mock.patch.object(device, "event_with_options", event_with_options):
                    event = await device.event(Events.RESET, arg1, arg2, a=kwarg3, b=kwarg4)

                assert event is ret
                event_with_options.assert_called_once_with(Events.RESET, args=(arg1, arg2), kwargs={"a": kwarg3, "b": kwarg4})

            class TestHelperForCreatingAndExecutingEvents:
                @pytest.fixture()
                def mocked(self):
                    class Mocked:
                        def __init__(s):
                            s.device = Device("d073d5001337", Products.LCM2_A19, Device.Firmware(2, 80, 0))

                            s.ret = mock.Mock(name="ret")

                            async def execute_event(event, is_finished):
                                return (s.ret, event, is_finished)

                            s.execute_event = pytest.helpers.AsyncMock(name="execute_event", side_effect=execute_event)

                    mocked = Mocked()
                    with mock.patch.object(mocked.device, "execute_event", mocked.execute_event):
                        yield mocked

                async def test_it_has_helper_for_creating_and_executing_events(self, mocked):
                    res = await mocked.device.event_with_options(Events.RESET, args=(), kwargs={"old_attrs": {}})
                    assert res == (mocked.ret, Events.RESET(mocked.device, old_attrs={}), None)
                    mocked.execute_event.assert_called_once_with(res[1], res[2])
                    assert res[1]._exclude_viewers is False

                async def test_it_passes_in_args_and_kwargs_when_making_the_event(self, mocked):
                    called = []

                    class E:
                        def __init__(s, device, *args, **kwargs):
                            s.device = device
                            s.a = args
                            s.k = kwargs
                            called.append(("E", device, args, kwargs))

                        def __eq__(s, other):
                            return other.device is s.device and other.a == s.a and other.k == s.k

                    res = await mocked.device.event_with_options(E, args=(1, 2), kwargs={"a": 3})
                    assert res == (mocked.ret, E(mocked.device, 1, 2, a=3), None)
                    mocked.execute_event.assert_called_once_with(res[1], res[2])
                    assert res[1]._exclude_viewers is False

                async def test_it_can_make_the_event_invisible_to_viewers(self, mocked):
                    res = await mocked.device.event_with_options(Events.RESET, visible=False, args=(), kwargs={"old_attrs": {}})
                    assert res == (mocked.ret, Events.RESET(mocked.device, old_attrs={}), None)
                    mocked.execute_event.assert_called_once_with(res[1], res[2])
                    assert res[1]._exclude_viewers is True

                async def test_it_can_not_execute(self, mocked):
                    res = await mocked.device.event_with_options(Events.RESET, execute=False, args=(), kwargs={"old_attrs": {}})
                    assert res == Events.RESET(mocked.device, old_attrs={})
                    mocked.execute_event.assert_not_called()

            class TestExecutingEvents:
                async def test_it_does_nothing_if_the_device_hasnt_applied_options(self):
                    called = []

                    class Op(Operator):
                        async def respond(s, event):
                            called.append(event)

                    device = Device(
                        "d073d5001337",
                        Products.LCM2_A19,
                        Device.Firmware(2, 80, 0),
                        lambda d: Op(d),
                    )

                    assert not device.applied_options
                    event = Events.RESET(device, old_attrs={})
                    assert await device.execute_event(event, None) is event
                    assert called == []

                async def test_it_passes_on_event_to_everything(self, device, record):
                    event = await device.event_with_options(
                        Events.ANNOTATION,
                        execute=False,
                        args=(logging.INFO, "stuff"),
                        kwargs={},
                    )
                    assert record == []
                    assert await device.execute_event(event, None) is event
                    assert record == [
                        ("execute_event", event, None),
                        ("viewer", event),
                        ("io", event),
                        ("operator", event),
                    ]

                async def test_it_doesnt_pass_on_to_viewers_if_invisible(self, device, record):
                    event = await device.event_with_options(
                        Events.ANNOTATION,
                        execute=False,
                        visible=False,
                        args=(logging.INFO, "stuff"),
                        kwargs={},
                    )
                    assert record == []
                    assert await device.execute_event(event, None) is event
                    assert record == [
                        ("execute_event", event, None),
                        ("io", event),
                        ("operator", event),
                    ]

                async def test_it_can_pass_only_to_viewers(self, device, record):
                    event = await device.event_with_options(
                        Events.ANNOTATION,
                        execute=False,
                        args=(logging.INFO, "stuff"),
                        kwargs={},
                    )
                    event._viewers_only = True

                    assert record == []
                    assert await device.execute_event(event, None) is event
                    assert record == [
                        ("execute_event", event, None),
                        ("viewer", event),
                    ]

                async def test_it_passes_reset_event_into_reset_functions_too(self, device, record):
                    attr_change_event = Events.ATTRIBUTE_CHANGE(
                        device,
                        [
                            ChangeAttr.test("three", "blah"),
                            ChangeAttr.test("four", "stuff"),
                            ChangeAttr.test("five", 3),
                        ],
                        True,
                    )
                    event = await device.event_with_options(
                        Events.RESET,
                        execute=False,
                        args=(),
                        kwargs={"old_attrs": {}},
                    )
                    assert record == []
                    assert await device.execute_event(event, None) is event
                    assert record == [
                        ("execute_event", event, None),
                        ("reset_viewer", event),
                        ("reset_io", event),
                        ("reset_operator", event),
                        #
                        ("execute_event", attr_change_event, None),
                        ("viewer", attr_change_event),
                        ("io", attr_change_event),
                        ("operator", attr_change_event),
                        #
                        ("viewer", event),
                        ("io", event),
                        ("operator", event),
                    ]

                async def test_it_passes_on_invisible_reset_event_into_reset_functions_too(self, device, record):
                    attr_change_event = Events.ATTRIBUTE_CHANGE(
                        device,
                        [
                            ChangeAttr.test("three", "blah"),
                            ChangeAttr.test("four", "stuff"),
                            ChangeAttr.test("five", 3),
                        ],
                        True,
                    )
                    event = await device.event_with_options(
                        Events.RESET,
                        execute=False,
                        visible=False,
                        args=(),
                        kwargs={"old_attrs": {}},
                    )
                    assert record == []
                    assert await device.execute_event(event, None) is event
                    assert record == [
                        ("execute_event", event, None),
                        ("reset_viewer", event),
                        ("reset_io", event),
                        ("reset_operator", event),
                        #
                        ("execute_event", attr_change_event, None),
                        ("viewer", attr_change_event),
                        ("io", attr_change_event),
                        ("operator", attr_change_event),
                        #
                        ("io", event),
                        ("operator", event),
                    ]

                async def test_it_can_stop_going_through_operators_based_on_is_finished(self, record, final_future):
                    class OO(Operator):
                        def setup(s, i):
                            s.i = i

                        async def respond(s, event):
                            record.add(s, "operator", s.i, event)

                    class VV(Viewer):
                        def setup(s, i):
                            s.i = i

                        async def respond(s, event):
                            record.add(s, "viewer", s.i, event)

                    class II(IO):
                        def setup(s, source):
                            s.io_source = source
                            super().setup()

                        async def apply(s):
                            s.device.io[s.io_source] = s

                        async def respond(s, event):
                            record.add(s, "io", s.io_source, event)

                    device = Device(
                        "d073d5001337",
                        Products.LCM2_A19,
                        Device.Firmware(2, 80, 0),
                        lambda d: OO(d, {}, 1),
                        lambda d: OO(d, {}, 2),
                        lambda d: OO(d, {}, 3),
                        lambda d: VV(d, {}, 1),
                        lambda d: VV(d, {}, 2),
                        lambda d: VV(d, {}, 3),
                        lambda d: II(d, {}, "io1"),
                        lambda d: II(d, {}, "io2"),
                        lambda d: II(d, {}, "io3"),
                    )

                    async with device.session(final_future):
                        record.clear()
                        event = await device.event_with_options(
                            Events.ANNOTATION,
                            execute=False,
                            args=(logging.INFO, "stuff"),
                            kwargs={},
                        )
                        assert record == []
                        assert await device.execute_event(event, None) is event
                        assert record == [
                            ("viewer", 1, event),
                            ("viewer", 2, event),
                            ("viewer", 3, event),
                            ("io", "io1", event),
                            ("io", "io2", event),
                            ("io", "io3", event),
                            ("operator", 1, event),
                            ("operator", 2, event),
                            ("operator", 3, event),
                        ]

                        skips = [
                            False,
                            False,
                            False,
                            False,
                            False,
                            True,
                        ]

                        def is_finished(e):
                            assert e is event
                            res = skips.pop(0)
                            record.add(None, "is_finished?", res)
                            return res

                        record.clear()
                        assert await device.execute_event(event, is_finished) is event
                        assert record == [
                            ("is_finished?", False),
                            ("viewer", 1, event),
                            ("is_finished?", False),
                            ("viewer", 2, event),
                            ("is_finished?", False),
                            ("viewer", 3, event),
                            ("is_finished?", False),
                            # The record to console viewer runs
                            ("is_finished?", False),
                            ("io", "io1", event),
                            ("is_finished?", True),
                        ]
                        assert skips == []

        class TestShortcuts:
            async def test_it_can_power_on(self, device, record):
                device.has_power = False
                assert not record

                await device.power_on()
                assert device.has_power
                assert record == [
                    ("execute_event", Events.POWER_ON(device), None),
                    ("power_on_viewer", Events.POWER_ON(device)),
                    ("power_on_io", Events.POWER_ON(device)),
                    ("power_on_operator", Events.POWER_ON(device)),
                    ("viewer", Events.POWER_ON(device)),
                    ("io", Events.POWER_ON(device)),
                    ("operator", Events.POWER_ON(device)),
                ]

            async def test_it_can_power_off(self, device, record):
                assert device.has_power
                assert not record

                def intercept(operator, *v):
                    if operator is not None:
                        return (operator, (*v, operator.device.has_power))
                    return (operator, v)

                record._intercept = intercept

                await device.power_off()
                assert not device.has_power

                assert record == [
                    ("execute_event", Events.SHUTTING_DOWN(device), None),
                    #
                    ("shutting_down_viewer", Events.SHUTTING_DOWN(device), True),
                    ("shutting_down_io", Events.SHUTTING_DOWN(device), True),
                    ("shutting_down_operator", Events.SHUTTING_DOWN(device), True),
                    #
                    ("viewer", Events.SHUTTING_DOWN(device), True),
                    ("io", Events.SHUTTING_DOWN(device), True),
                    ("operator", Events.SHUTTING_DOWN(device), True),
                    #
                    ("execute_event", Events.POWER_OFF(device), None),
                    #
                    ("viewer", Events.POWER_OFF(device), False),
                    ("io", Events.POWER_OFF(device), False),
                    ("operator", Events.POWER_OFF(device), False),
                ]

            async def test_it_can_temporarily_be_off(self, device, record):
                def intercept(operator, *v):
                    if operator is not None:
                        return (operator, (*v, operator.device.has_power))
                    return (operator, v)

                record._intercept = intercept

                assert device.has_power
                async with device.offline():
                    assert not device.has_power
                    assert record == [
                        ("execute_event", Events.SHUTTING_DOWN(device), None),
                        #
                        ("shutting_down_viewer", Events.SHUTTING_DOWN(device), True),
                        ("shutting_down_io", Events.SHUTTING_DOWN(device), True),
                        ("shutting_down_operator", Events.SHUTTING_DOWN(device), True),
                        #
                        ("viewer", Events.SHUTTING_DOWN(device), True),
                        ("io", Events.SHUTTING_DOWN(device), True),
                        ("operator", Events.SHUTTING_DOWN(device), True),
                        #
                        ("execute_event", Events.POWER_OFF(device), None),
                        #
                        ("viewer", Events.POWER_OFF(device), False),
                        ("io", Events.POWER_OFF(device), False),
                        ("operator", Events.POWER_OFF(device), False),
                    ]
                    record.clear()

                assert device.has_power
                assert record == [
                    ("execute_event", Events.POWER_ON(device), None),
                    #
                    ("power_on_viewer", Events.POWER_ON(device), True),
                    ("power_on_io", Events.POWER_ON(device), True),
                    ("power_on_operator", Events.POWER_ON(device), True),
                    #
                    ("viewer", Events.POWER_ON(device), True),
                    ("io", Events.POWER_ON(device), True),
                    ("operator", Events.POWER_ON(device), True),
                ]

            async def test_it_can_reset(self, device, record):
                attr_change_event = Events.ATTRIBUTE_CHANGE(
                    device,
                    [
                        ChangeAttr.test("three", "blah"),
                        ChangeAttr.test("four", "stuff"),
                        ChangeAttr.test("five", 3),
                    ],
                    False,
                )

                assert device.attrs.three == "blah"
                assert device.attrs.four == "stuff"
                assert device.attrs.five == 3
                assert device.has_power
                device.firmware = Device.Firmware(2, 90, 0)
                current_firmware = device.firmware
                assert device.original_firmware == Device.Firmware(2, 80, 0)
                original = Device.Firmware(2, 80, 0)

                assert device.attrs.as_dict() == {"three": "blah", "four": "stuff", "five": 3}
                await device.attrs.attrs_apply(
                    device.attrs.attrs_path("three").changer_to("twenty"),
                    device.attrs.attrs_path("five").changer_to("forty"),
                    event=None,
                )
                assert device.attrs.as_dict() == {
                    "three": "twenty",
                    "four": "stuff",
                    "five": "forty",
                }
                record.clear()

                def intercept(operator, *v):
                    if operator is not None:
                        return (
                            operator,
                            (
                                *v,
                                operator.device.has_power,
                                operator.device.firmware,
                                operator.device.attrs._started,
                            ),
                        )
                    return (operator, v)

                record._intercept = intercept
                reset_event = Events.RESET(device, old_attrs={})
                shutdown_event = Events.SHUTTING_DOWN(device)
                power_off_event = Events.POWER_OFF(device)
                power_on_event = Events.POWER_ON(device)

                await device.reset()
                assert record == [
                    ("execute_event", shutdown_event, None),
                    #
                    ("shutting_down_viewer", shutdown_event, True, current_firmware, True),
                    ("shutting_down_io", shutdown_event, True, current_firmware, True),
                    ("shutting_down_operator", shutdown_event, True, current_firmware, True),
                    #
                    ("viewer", shutdown_event, True, current_firmware, True),
                    ("io", shutdown_event, True, current_firmware, True),
                    ("operator", shutdown_event, True, current_firmware, True),
                    #
                    ("execute_event", power_off_event, None),
                    #
                    ("viewer", power_off_event, False, current_firmware, True),
                    ("io", power_off_event, False, current_firmware, True),
                    ("operator", power_off_event, False, current_firmware, True),
                    #
                    ("execute_event", reset_event, None),
                    ("reset_viewer", reset_event, False, original, False),
                    ("reset_io", reset_event, False, original, False),
                    ("reset_operator", reset_event, False, original, False),
                    #
                    ("execute_event", attr_change_event, None),
                    # No viewer because this happens before the device has started
                    ("io", attr_change_event, False, original, False),
                    ("operator", attr_change_event, False, original, False),
                    #
                    ("viewer", reset_event, False, original, False),
                    ("io", reset_event, False, original, False),
                    ("operator", reset_event, False, original, False),
                    #
                    ("execute_event", power_on_event, None),
                    #
                    ("power_on_viewer", power_on_event, True, original, True),
                    ("power_on_io", power_on_event, True, original, True),
                    ("power_on_operator", power_on_event, True, original, True),
                    #
                    ("viewer", power_on_event, True, original, True),
                    ("io", power_on_event, True, original, True),
                    ("operator", power_on_event, True, original, True),
                ]
                record.clear()

                assert device.attrs._started
                assert device.firmware == Device.Firmware(2, 80, 0)
                assert device.has_power
                assert device.attrs.as_dict() == {"three": "blah", "four": "stuff", "five": 3}

                device.firmware = Device.Firmware(2, 100, 0)
                current_firmware = device.firmware
                await device.reset(zerod=True)
                reset_event = Events.RESET(device, zerod=True, old_attrs={})
                attr_change_event = Events.ATTRIBUTE_CHANGE(
                    device,
                    [
                        ChangeAttr.test("three", 1),
                        ChangeAttr.test("four", 2),
                        ChangeAttr.test("five", 3),
                    ],
                    False,
                )
                assert record == [
                    ("execute_event", shutdown_event, None),
                    #
                    ("shutting_down_viewer", shutdown_event, True, current_firmware, True),
                    ("shutting_down_io", shutdown_event, True, current_firmware, True),
                    ("shutting_down_operator", shutdown_event, True, current_firmware, True),
                    #
                    ("viewer", shutdown_event, True, current_firmware, True),
                    ("io", shutdown_event, True, current_firmware, True),
                    ("operator", shutdown_event, True, current_firmware, True),
                    #
                    ("execute_event", power_off_event, None),
                    #
                    ("viewer", power_off_event, False, current_firmware, True),
                    ("io", power_off_event, False, current_firmware, True),
                    ("operator", power_off_event, False, current_firmware, True),
                    #
                    ("execute_event", reset_event, None),
                    ("reset_viewer", reset_event, False, original, False),
                    ("reset_io", reset_event, False, original, False),
                    ("reset_operator", reset_event, False, original, False),
                    #
                    ("execute_event", attr_change_event, None),
                    # No viewer because this happens before the device has started
                    ("io", attr_change_event, False, original, False),
                    ("operator", attr_change_event, False, original, False),
                    #
                    ("viewer", reset_event, False, original, False),
                    ("io", reset_event, False, original, False),
                    ("operator", reset_event, False, original, False),
                    #
                    ("execute_event", power_on_event, None),
                    #
                    ("power_on_viewer", power_on_event, True, original, True),
                    ("power_on_io", power_on_event, True, original, True),
                    ("power_on_operator", power_on_event, True, original, True),
                    #
                    ("viewer", power_on_event, True, original, True),
                    ("io", power_on_event, True, original, True),
                    ("operator", power_on_event, True, original, True),
                ]
                record.clear()

                assert device.attrs._started
                assert device.firmware == Device.Firmware(2, 80, 0)
                assert device.has_power
                assert device.attrs.as_dict() == {"three": 1, "four": 2, "five": 3}

            async def test_it_can_delete(self, device, record):
                await device.delete()
                delete_event = Events.DELETE(device)
                assert record == [
                    ("execute_event", delete_event, None),
                    ("viewer", delete_event),
                    ("io", delete_event),
                    ("operator", delete_event),
                ]
                record.clear()

                assert not hasattr(device, "io")
                assert not hasattr(device, "viewers")
                assert not hasattr(device, "operators")
                assert not device.applied_options

                # can be done again
                await device.delete()
                delete_event = Events.DELETE(device)
                assert record == [
                    ("execute_event", delete_event, None),
                ]

                assert not hasattr(device, "io")
                assert not hasattr(device, "viewers")
                assert not hasattr(device, "operators")
                assert not device.applied_options

            async def test_it_can_annotate(self, device, record):
                await device.annotate("INFO", "hello there", one=1, two=2)
                annotate_event = Events.ANNOTATION(device, logging.INFO, "hello there", one=1, two=2)
                assert record == [
                    ("execute_event", annotate_event, None),
                    ("viewer", annotate_event),
                    ("io", annotate_event),
                    ("operator", annotate_event),
                ]
                record.clear()

                await device.annotate(logging.ERROR, "hello there", one=1, two=2)
                annotate_event = Events.ANNOTATION(device, logging.ERROR, "hello there", one=1, two=2)
                assert record == [
                    ("execute_event", annotate_event, None),
                    ("viewer", annotate_event),
                    ("io", annotate_event),
                    ("operator", annotate_event),
                ]
                record.clear()

                with assertRaises(AttributeError, "NUP"):
                    Events.ANNOTATION(device, logging.NUP, "hello there", one=1)

            async def test_it_can_determine_if_the_device_is_discoverable(self, device, record):
                async with device.offline():
                    record.clear()
                    assert not await device.discoverable(Services.UDP, "255.255.255.255")
                    assert record == []
                record.clear()

                assert await device.discoverable(Services.UDP, "255.255.255.255")
                discoverable_event = Events.DISCOVERABLE(device, service=Services.UDP, address="255.255.255.255")
                assert record == [
                    ("execute_event", discoverable_event, None),
                    ("viewer", discoverable_event),
                    ("io", discoverable_event),
                    ("operator", discoverable_event),
                ]
                record.clear()

                def intercept(operator, *v):
                    if isinstance(operator, IO) and isinstance(v[1], Events.DISCOVERABLE):
                        record.record.append((operator, v))
                        raise v[1].raise_stop()
                    return (operator, v)

                record._intercept = intercept
                assert not await device.discoverable(Services.UDP, "255.255.0.255")
                discoverable_event = Events.DISCOVERABLE(device, service=Services.UDP, address="255.255.0.255")
                assert record == [
                    ("execute_event", discoverable_event, None),
                    ("viewer", discoverable_event),
                    ("io", discoverable_event),
                ]
