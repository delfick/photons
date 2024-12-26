import sys

import pytest
from delfick_project.errors_pytest import assertSameError
from delfick_project.norms import BadSpecValue, Meta, dictobj, sb
from photons_app import helpers as hp
from photons_app.mimic.device import Device
from photons_app.mimic.event import Events
from photons_app.mimic.operator import LambdaSetter, Operator, StaticSetter, Viewer
from photons_products import Products


@pytest.fixture()
def device():
    return Device("d073d5001337", Products.LCM2_A19, hp.Firmware(2, 80), search_for_operators=False)


def assertEvents(events, *expected, ignore_annotations=True):
    print("== ASSERT EVENTS")
    evs = list(events)
    count = 0

    failed = False
    while evs:
        nxt = evs.pop(0)
        nxtEvt = nxt
        if isinstance(nxt, tuple) and len(nxt) == 2:
            nxtEvt = nxt[1]

        if ignore_annotations and nxtEvt | Events.ANNOTATION:
            continue

        ex = None
        if count >= len(expected):
            failed = True
        else:
            ex = expected[count]
            count += 1

        same = nxt == ex

        if isinstance(ex, tuple) and len(ex) == 2 and isinstance(ex[1], tuple) and isinstance(ex[1][1], Device):
            if nxtEvt.device is ex[1][1]:
                ex = (ex[0], (ex[1][0], "<<Correct Device>>"))
            else:
                ex = (ex[0], (ex[1][0], "<<Incorrect Device>>"))

        if same:
            print(f"  Match\n    {nxt}\n    {ex}")
        else:
            print(f"  Different\n    {nxt}\n    {ex}")
            failed = True

    try:
        if count != len(expected):
            assert False, f"Expected different number of events (expected {count} == {len(expected)})"
        elif failed:
            assert False, "Expected correct events"
    finally:
        print(f"== ASSERTED: {sys.exc_info()[1]}")
        print()


class TestOperator:
    class TestStaticSetter:
        def test_it_can_be_got_from_the_Operator(self):
            assert Operator.Attr.Static is StaticSetter

        async def test_it_can_be_used_to_set_values_in_attrs(self, device, final_future):
            class Op(Operator):
                attrs = [Operator.Attr.Static("three", 0), Operator.Attr.Static("two", "stuff")]

            device.options.append(Op(device))

            async with device.session(final_future):
                assert device.attrs.three == 0
                assert device.attrs.two == "stuff"

                await device.attrs.attrs_apply(
                    device.attrs.attrs_path("three").changer_to(20),
                    device.attrs.attrs_path("two").changer_to(0),
                    event=None,
                )
                assert device.attrs.three == 20
                assert device.attrs.two == 0

                await device.reset(zerod=True)
                assert device.attrs.three == 0
                assert device.attrs.two == "stuff"

    class TestLambdaSetter:
        def test_it_can_be_got_from_the_Operator(self):
            assert Operator.Attr.Lambda is LambdaSetter

        async def test_it_can_be_used_to_set_values_in_attrs(self, device, final_future):
            class Op(Operator):
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

            device.options.append(Op(device, options={"one": "hello", "two": "there"}))

            async with device.session(final_future):
                assert device.attrs.three == "hello"
                assert device.attrs.four == "there"

                await device.reset(zerod=True)
                assert device.attrs.three == 1
                assert device.attrs.four == 2

        async def test_it_can_default_to_use_zero_if_options_dont_determine_value(self, device, final_future):
            class Op(Operator):
                attrs = [
                    Operator.Attr.Lambda(
                        "thing",
                        from_zero=lambda event, options: "stuff",
                    ),
                ]

            device.options.append(Op(device))

            async with device.session(final_future):
                assert device.attrs.thing == "stuff"

                await device.attrs.attrs_apply(device.attrs.attrs_path("thing").changer_to("yeap"), event=None)
                assert device.attrs.thing == "yeap"

                await device.reset(zerod=True)
                assert device.attrs.thing == "stuff"

    class TestAddingOperatorToADevice:
        async def test_it_adds_itself_to_the_operators_list(self, device, final_future):
            class Op(Operator):
                pass

            operator1 = Op(device)
            operator2 = Op(device)
            device.search_for_operators = False
            device.options.append(operator1)
            device.options.append(operator2)

            assert not hasattr(device, "operators")
            async with device.session(final_future):
                assert device.operators == [operator1, operator2]
            assert not hasattr(device, "operators")

        async def test_it_can_be_a_viewer_instead(self, device, final_future):
            class View(Viewer):
                pass

            viewer1 = View(device)
            viewer2 = View(device)
            device.search_for_operators = False
            device.options.append(viewer1)
            device.options.append(viewer2)

            assert not hasattr(device, "viewers")
            async with device.session(final_future):
                assert device.viewers == [viewer1, viewer2]
            assert not hasattr(device, "viewers")

        async def test_it_can_override_application(self, device, final_future):
            would = []

            class Custom(Operator):
                async def apply(self):
                    would.append(self)

            custom1 = Custom(device)
            custom2 = Custom(device)
            device.search_for_operators = False
            device.options.append(custom1)
            device.options.append(custom2)

            assert would == []
            async with device.session(final_future):
                assert device.io == {}
                assert device.viewers == []
                assert device.operators == []
                assert would == [custom1, custom2]

    class TestCanHaveOptions:
        def test_it_complains_if_instantiated_with_bad_options(self, device):
            class Op(Operator):
                class Options(Operator.Options):
                    will_be_wrong = dictobj.Field(sb.integer_spec())
                    will_be_missing = dictobj.Field(sb.boolean, wrapper=sb.required)

            try:
                Op(device, options={"will_be_wrong": "nope"})
            except BadSpecValue as error:
                assert len(error.errors) == 2
                assertSameError(
                    error.errors[0],
                    BadSpecValue,
                    "Expected a value but got none",
                    {"meta": Meta({}, []).at("will_be_missing")},
                    [],
                )
                assertSameError(
                    error.errors[1],
                    BadSpecValue,
                    "Expected an integer",
                    {"meta": Meta({}, []).at("will_be_wrong"), "got": str},
                    [],
                )
            else:
                assert False, "Expected an error"

        def test_it_puts_options_and_device_attrs_on_operator_before_setup(self, device):
            got = []

            class Op(Operator):
                class Options(Operator.Options):
                    an_int = dictobj.Field(sb.integer_spec())
                    a_boolean = dictobj.Field(sb.boolean, wrapper=sb.required)

                def setup(self):
                    got.append((self.options.an_int, self.options.a_boolean))
                    got.append(self.device_attrs)

            operator = Op(device, options={"an_int": 42, "a_boolean": False})
            assert got == [(42, False), device.attrs]
            assert operator.options.as_dict() == {"an_int": 42, "a_boolean": False}
            assert operator.device_attrs is device.attrs

        def test_it_defaults_to_providing_empty_dictionary_to_options(self, device):
            class Op(Operator):
                class Options(Operator.Options):
                    an_int = dictobj.NullableField(sb.integer_spec())
                    a_boolean = dictobj.Field(sb.boolean, default=True)

            operator = Op(device)
            assert operator.options.as_dict() == {"an_int": None, "a_boolean": True}

    class TestHandlesResetEvents:
        async def test_it_does_the_right_thing_with_LambdaSetters(self, device, final_future):
            got = []

            class Op(Operator):
                attrs = [
                    Operator.Attr.Lambda(
                        "three",
                        from_zero=lambda event, options: 1,
                    ),
                    Operator.Attr.Lambda(
                        "four",
                        from_zero=lambda event, options: 2,
                    ),
                ]

                async def reset(self, event):
                    got.append(("reset", event))
                    return await super().reset(event)

                async def respond(self, event):
                    got.append(("respond", event))
                    return await super().respond(event)

            device.options.append(Op(device))

            evtZerod = Events.RESET(device, zerod=True, old_attrs={})
            evtNormal = Events.RESET(device, zerod=False, old_attrs={})

            async with device.session(final_future):
                assertEvents(
                    got,
                    ("respond", (Events.SHUTTING_DOWN, device)),
                    ("respond", (Events.POWER_OFF, device)),
                    ("reset", evtNormal),
                    ("respond", (Events.ATTRIBUTE_CHANGE, device)),
                    ("respond", evtNormal),
                    ("respond", (Events.POWER_ON, device)),
                )
                assert device.attrs.three == 1
                assert device.attrs.four == 2

                await device.attrs.attrs_apply(
                    device.attrs.attrs_path("three").changer_to(20),
                    device.attrs.attrs_path("four").changer_to(40),
                    event=None,
                )
                assert device.attrs.three == 20
                assert device.attrs.four == 40

                await device.event(Events.RESET, zerod=True, old_attrs={})
                assert device.attrs.three == 1
                assert device.attrs.four == 2

                assertEvents(
                    got,
                    ("respond", (Events.SHUTTING_DOWN, device)),
                    ("respond", (Events.POWER_OFF, device)),
                    ("reset", evtNormal),
                    ("respond", (Events.ATTRIBUTE_CHANGE, device)),
                    ("respond", evtNormal),
                    ("respond", (Events.POWER_ON, device)),
                    #
                    ("respond", (Events.ATTRIBUTE_CHANGE, device)),
                    #
                    ("reset", evtZerod),
                    ("respond", (Events.ATTRIBUTE_CHANGE, device)),
                    ("respond", evtZerod),
                )
                got.clear()

            assertEvents(
                got,
                ("respond", (Events.DELETE, device)),
            )
