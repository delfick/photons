# coding: spec

import io
from textwrap import dedent
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import dictobj, sb
from delfick_project.option_merge import MergedOptions
from photons_app import helpers as hp
from photons_app.mimic.attrs import Attrs, ChangeAttr, Path, ReduceLength
from photons_app.mimic.device import Device
from photons_products import Products


@pytest.fixture()
def device():
    return Device(
        "d073d5001337",
        Products.LCM2_A19,
        hp.Firmware(2, 80),
        value_store={"only_io_and_viewer_operators": True},
    )


describe "Path":

    @pytest.fixture()
    def attrs(self, device):
        attrs = Attrs(device)

        class Two(dictobj.Spec):
            blah = dictobj.Field(sb.boolean)

        class One(dictobj.Spec):
            list1 = dictobj.Field(sb.listof(Two.FieldSpec()))
            list2 = dictobj.Field(sb.listof(sb.integer_spec()))
            thing3 = dictobj.Field(sb.string_spec())

        # Bypass the change system cause the tests is testing that system!
        attrs._attrs["one"] = One.FieldSpec().empty_normalise(
            list1=[{"blah": True}, {"blah": False}], list2=[1, 2, 3], thing3="yeap"
        )
        attrs._attrs["stuff"] = "things"
        attrs._attrs["many"] = ["yes", "yah", "yarp"]

        attrs.attrs_start()
        return attrs

    it "takes attrs and parts", attrs:
        parts = ["one", "two", "three"]
        path = Path(attrs, parts)
        assert path.attrs is attrs
        assert path.parts == parts

    it "can match against a glob and only if the value exists in attrs", attrs:
        path = Path(attrs, ["not", "there", 1])
        assert not path.matches("not*")
        assert not path.matches("not.there[1]")
        assert not path.matches("not.there[*]")
        assert not path.matches("not.there[2]")
        assert not path.matches("there[1]")

        class Not(dictobj.Spec):
            there = dictobj.Field(sb.listof(sb.integer_spec()))

        attrs._attrs["not"] = Not.FieldSpec().empty_normalise(there=[1, 2])
        assert path.matches("not*")
        assert path.matches("not.there[1]")
        assert path.matches("not.there[*]")
        assert not path.matches("not.there[2]")
        assert not path.matches("there[1]")

    it "can create an object to represent a change", attrs:
        path = Path(attrs, ["one", "two"])
        ch = path.changer_to("three")
        assert isinstance(ch, ChangeAttr)
        assert ch.value == "three"
        assert ch.path is path

    it "can create an object to represent a length reduction", attrs:
        path = Path(attrs, ["one", "two"])
        ch = path.reduce_length_to(3)
        assert isinstance(ch, ReduceLength)
        assert ch.value == 3
        assert ch.path is path

    describe "follow":
        it "no parts is for nothing", attrs:
            assert Path(attrs, []).follow() == ("<>", attrs, sb.NotSpecified)

        it "can find an item", attrs:
            assert Path(attrs, ["many"]).follow() == ("many", attrs, "many")
            assert Path(attrs, ["many", 0]).follow() == ("many[0]", attrs["many"], 0)
            assert Path(attrs, ["one", "list1", 1, "blah"]).follow() == (
                "one.list1[1].blah",
                attrs["one"]["list1"][1],
                "blah",
            )

        it "can know when it can't find an item", attrs:
            assert Path(attrs, ["many", 5]).follow() == ("many<5>", attrs["many"], sb.NotSpecified)
            assert Path(attrs, ["one", "list1", 3, "meh"]).follow() == (
                "one.list1<3><meh>",
                attrs["one"]["list1"],
                sb.NotSpecified,
            )

    describe "ChangeAttr":
        it "has repr before we attempt to apply", attrs:
            path = Path(attrs, ["one", "list2", 2])
            changer = ChangeAttr(path, 23)
            assert repr(changer) == "<Will change <Path one.list2[2]> to 23>"
            assert changer == ChangeAttr.test("one.list2[2]", 23, attempted=False)

            path = Path(attrs, ["one", "list24", 2])
            changer = ChangeAttr(path, 23)
            assert repr(changer) == "<Will change <Path one<list24><2>> to 23>"
            assert changer == ChangeAttr.test("one<list24><2>", 23, attempted=False)

        async it "has a repr if we applied to a path that doesn't exist", attrs:
            path = Path(attrs, ["one", "list24", 2])
            changer = ChangeAttr(path, 23)
            assert repr(changer) == "<Will change <Path one<list24><2>> to 23>"
            assert changer == ChangeAttr.test("one<list24><2>", 23, attempted=False)

            await changer()
            assert repr(changer) == "<Couldn't Change one<list24><2>>"
            assert changer == ChangeAttr.test("one<list24><2>", 23, attempted=True, success=False)

        async it "can call attr_change on parent if it has one", attrs:
            called = []

            class Holder:
                def __init__(self):
                    self.my_property = 4

                async def attr_change(self, part, value, event):
                    called.append(("attr_change", part, value, event))
                    setattr(self, part, value)

            event = mock.Mock(name="event")

            path = Path(attrs, ["holder"])
            holder = Holder()
            changer = ChangeAttr(path, holder)
            await changer(event=event)
            assert called == []
            assert attrs.holder.my_property == 4

            path = Path(attrs, ["holder", "my_property"])
            await (ChangeAttr(path, 5))(event=event)
            assert called == [("attr_change", "my_property", 5, event)]
            called.clear()
            assert attrs.holder.my_property == 5

        async it "has a repr if we applied to a path but the value didn't change", attrs:

            class Sticky(dictobj.Spec):
                @property
                def one(s):
                    return getattr(s, "_one", 2)

                @one.setter
                def one(s, value):
                    if value < 10:
                        s._one = value

            attrs._attrs["sticky"] = Sticky.FieldSpec().empty_normalise()

            path = Path(attrs, ["sticky", "one"])
            changer = ChangeAttr(path, 23)
            assert repr(changer) == "<Will change <Path sticky.one> to 23>"
            assert changer == ChangeAttr.test("sticky.one", 23, attempted=False)

            await changer()
            assert repr(changer) == "<Changed sticky.one to 23 but became 2>"
            assert changer == ChangeAttr.test("sticky.one", 23, value_after=2)

        async it "has a repr if we applied to a path", attrs:
            changer = attrs.attrs_path("one", "list1", 0, "blah").changer_to(False)
            assert repr(changer) == "<Will change <Path one.list1[0].blah> to False>"
            await changer()
            assert repr(changer) == "<Changed one.list1[0].blah to False>"
            assert changer == ChangeAttr.test("one.list1[0].blah", False)

            changer = attrs.attrs_path("one", "thing3").changer_to(56)
            assert repr(changer) == "<Will change <Path one.thing3> to 56>"
            assert changer == ChangeAttr.test("one.thing3", 56, attempted=False)
            await changer()
            assert repr(changer) == "<Changed one.thing3 to 56>"
            assert changer == ChangeAttr.test("one.thing3", 56)

            changer = attrs.attrs_path("many", 2).changer_to("nope")
            assert repr(changer) == "<Will change <Path many[2]> to nope>"
            assert changer == ChangeAttr.test("many[2]", "nope", attempted=False)
            await changer()
            assert repr(changer) == "<Changed many[2] to nope>"
            assert changer == ChangeAttr.test("many[2]", "nope")

            changer = attrs.attrs_path("stuff").changer_to("better")
            assert repr(changer) == "<Will change <Path stuff> to better>"
            assert changer == ChangeAttr.test("stuff", "better", attempted=False)
            await changer()
            assert repr(changer) == "<Changed stuff to better>"
            assert changer == ChangeAttr.test("stuff", "better")

            assert MergedOptions.using(attrs._attrs).as_dict() == {
                "one": {
                    "list1": [{"blah": False}, {"blah": False}],
                    "list2": [1, 2, 3],
                    "thing3": 56,
                },
                "stuff": "better",
                "many": ["yes", "yah", "nope"],
            }

        async it "can add attributes that don't already exist to the base of attrs", attrs:
            changer = attrs.attrs_path("new").changer_to("newer")
            assert repr(changer) == "<Will change <Path new> to newer>"
            await changer()
            assert repr(changer) == "<Changed new to newer>"

        async it "can not add attributes that don't already exist to after base of attrs", attrs:
            changer = attrs.attrs_path("one", "list1", 0, "nope").changer_to("never")
            assert repr(changer) == "<Will change <Path one.list1[0]<nope>> to never>"
            await changer()
            assert repr(changer) == "<Couldn't Change one.list1[0]<nope>>"

    describe "ReduceLength":
        it "has repr before we attempt to apply", attrs:
            path = Path(attrs, ["one", "list2"])
            changer = ReduceLength(path, 3)
            assert repr(changer) == "<Will change <Path one.list2> length to 3>"
            assert changer == ReduceLength.test("one.list2", 3, attempted=False)

            path = Path(attrs, ["one", "list24"])
            changer = ReduceLength(path, 4)
            assert repr(changer) == "<Will change <Path one<list24>> length to 4>"
            assert changer == ReduceLength.test("one<list24>", 4, attempted=False)

        async it "has a repr if we applied to a path that doesn't exist", attrs:
            path = Path(attrs, ["one", "list24"])
            changer = ReduceLength(path, 23)
            assert repr(changer) == "<Will change <Path one<list24>> length to 23>"
            assert changer == ReduceLength.test("one<list24>", 23, attempted=False)

            await changer()
            assert repr(changer) == "<Couldn't Change length for one<list24>>"
            assert changer == ReduceLength.test("one<list24>", 23, attempted=True, success=False)

        async it "can call attr_change if property tuple is on has one", attrs:
            called = []

            class Holder:
                def __init__(self):
                    self.a_list = ()

                async def attr_change(self, part, value, event):
                    called.append(("attr_change", part, value, event))
                    setattr(self, part, value)

            event = mock.Mock(name="event")

            path = Path(attrs, ["holder"])
            holder = Holder()
            changer = ChangeAttr(path, holder)
            await changer(event=event)
            assert called == []

            path = Path(attrs, ["holder", "a_list"])
            await (ChangeAttr(path, (1, 2, 3, 4)))(event=event)
            assert called == [("attr_change", "a_list", (1, 2, 3, 4), event)]
            called.clear()
            assert attrs.holder.a_list == (1, 2, 3, 4)

            path = Path(attrs, ["holder", "a_list"])
            changer = ReduceLength(path, 2)
            assert repr(changer) == "<Will change <Path holder.a_list> length to 2>"
            assert changer == ReduceLength.test("holder.a_list", 2, attempted=False)

            await changer()
            assert repr(changer) == "<Changed holder.a_list length to 2>"
            assert changer == ReduceLength.test("holder.a_list", 2)

            assert attrs.holder.a_list == (1, 2)
            assert called == [("attr_change", "a_list", (1, 2), None)]

        async it "has a repr if we applied to a path but the value didn't change", attrs:

            class Unpoppable(list):
                def __init__(self):
                    super().__init__()
                    self.extend([1, 2, 3, 4])

                def pop(self):
                    pass

            class Sticky(dictobj.Spec):
                one = Unpoppable()

            attrs._attrs["sticky"] = Sticky.FieldSpec().empty_normalise()

            path = Path(attrs, ["sticky", "one"])
            changer = ReduceLength(path, 2)
            assert repr(changer) == "<Will change <Path sticky.one> length to 2>"
            assert changer == ReduceLength.test("sticky.one", 2, attempted=False)

            await changer()
            assert repr(changer) == "<Changed sticky.one length to 2 but became 4>"
            assert changer == ReduceLength.test("sticky.one", 2, length_after=4)

        async it "has a repr if we applied to a path", attrs:
            changer = attrs.attrs_path("thing4").changer_to((1, 2, 3, 4))
            await changer()
            assert repr(changer) == "<Changed thing4 to (1, 2, 3, 4)>"

            changer = attrs.attrs_path("thing4").reduce_length_to(3)
            assert repr(changer) == "<Will change <Path thing4> length to 3>"
            await changer()
            assert repr(changer) == "<Changed thing4 length to 3>"
            assert changer == ReduceLength.test("thing4", 3)

            changer = attrs.attrs_path("one", "list1").reduce_length_to(1)
            assert repr(changer) == "<Will change <Path one.list1> length to 1>"
            await changer()
            assert repr(changer) == "<Changed one.list1 length to 1>"
            assert changer == ReduceLength.test("one.list1", 1)

            changer = attrs.attrs_path("one", "list2").reduce_length_to(0)
            assert repr(changer) == "<Will change <Path one.list2> length to 0>"
            await changer()
            assert repr(changer) == "<Changed one.list2 length to 0>"
            assert changer == ReduceLength.test("one.list2", 0)

            assert MergedOptions.using(attrs._attrs).as_dict() == {
                "one": {
                    "list1": [{"blah": True}],
                    "list2": [],
                    "thing3": "yeap",
                },
                "thing4": (1, 2, 3),
                "stuff": "things",
                "many": ["yes", "yah", "yarp"],
            }


describe "Attrs":

    @pytest.fixture()
    def final_future(self):
        fut = hp.create_future()
        try:
            yield fut
        finally:
            fut.cancel()

    @pytest.fixture()
    def record(self):
        return io.StringIO()

    @pytest.fixture()
    def attrs(self, device, record):
        assert isinstance(device.attrs, Attrs)
        assert device.attrs._device is device
        return device.attrs

    it "takes a device and can be told when it's started", device:
        attrs = Attrs(device)
        assert attrs._device is device
        assert attrs._attrs == {}
        assert not attrs._started

        attrs.attrs_start()
        assert attrs._started

        attrs._attrs[2] = 3
        assert attrs._attrs == {2: 3}

        attrs.attrs_reset()
        assert not attrs._started
        assert attrs._attrs == {}

    it "can get a path object", attrs:
        path = attrs.attrs_path("one", "two", 3, "four")
        assert isinstance(path, Path)
        assert path.attrs is attrs
        assert path.parts == ["one", "two", 3, "four"]

    async it "says if something is inside _attrs", attrs:
        assert "one" not in attrs
        await attrs.attrs_apply(attrs.attrs_path("one").changer_to(3), event=None)
        assert "one" in attrs
        assert attrs.one == 3
        assert attrs["one"] == 3

    it "complains if you try to set things on the attrs with item or attr syntax", attrs:
        assert "nup" not in attrs
        with assertRaises(TypeError, "'Attrs' object does not support item assignment"):
            attrs["nup"] = 3
        assert "nup" not in attrs

        with assertRaises(AttributeError):
            attrs.nup = 3
        assert "nup" not in attrs

    async it "can get attributes with item and attr syntax", attrs:
        with assertRaises(AttributeError, "No such attribute thing"):
            attrs.thing
        with assertRaises(KeyError, "thing"):
            attrs["thing"]

        await attrs.attrs_apply(
            attrs.attrs_path("thing").changer_to(3),
            attrs.attrs_path("stuff").changer_to({"one": 1}),
            event=None,
        )

        assert attrs.thing == 3
        assert attrs["stuff"]["one"] == 1

    async it "puts items in _attrs into dir output", attrs:
        without = dir(attrs)

        assert "thing" not in without
        assert "stuff" not in without

        await attrs.attrs_apply(
            attrs.attrs_path("thing").changer_to(3),
            attrs.attrs_path("stuff").changer_to({"one": 1}),
            event=None,
        )

        assert set(dir(attrs)) == set(without + ["thing", "stuff"])

    async it "makes a copy of attrs for as_dict", attrs:
        dct = attrs.as_dict()
        assert dct == {}
        assert dct == attrs._attrs
        assert dct is not attrs._attrs

        await attrs.attrs_apply(attrs.attrs_path("one").changer_to(2), event=None)
        dct = attrs.as_dict()
        assert dct == {"one": 2}
        assert dct == attrs._attrs
        assert dct is not attrs._attrs

        attrs._attrs["two"] = 3
        assert dct == {"one": 2}

        dct["four"] = 4
        assert dct == {"one": 2, "four": 4}
        assert attrs._attrs == {"two": 3, "one": 2}

    async it "records what is changed", device, attrs, record, final_future:
        device.value_store["has_io"] = False
        device.value_store["test_console_record"] = record

        async with device.session(final_future):
            assert attrs._started
            await attrs.attrs_apply(
                attrs.attrs_path("one").changer_to(5),
                attrs.attrs_path("two").changer_to({"one": 1}),
                attrs.attrs_path("three").changer_to("blah"),
                event=None,
            )

        record.seek(0)
        assert (
            record.read()
            == dedent(
                """
        TIME -> d073d5001337(LCM2_A19:2,80) SHUTTING_DOWN

        TIME -> d073d5001337(LCM2_A19:2,80) POWER_OFF

        TIME -> d073d5001337(LCM2_A19:2,80) RESET
          :: zerod = False

        TIME -> d073d5001337(LCM2_A19:2,80) POWER_ON

        TIME -> d073d5001337(LCM2_A19:2,80) ATTRIBUTE_CHANGE
          -- Attributes changed (started)
          ~ <Changed one to 5>
          ~ <Changed two to {'one': 1}>
          ~ <Changed three to blah>

        TIME -> d073d5001337(LCM2_A19:2,80) DELETE

        """
            ).lstrip()
        )

        assert MergedOptions.using(attrs._attrs).as_dict() == {
            "one": 5,
            "two": {"one": 1},
            "three": "blah",
        }

    async it "hides changes if the attrs haven't started yet", device, attrs, record, final_future:
        device.value_store["has_io"] = False
        device.value_store["test_console_record"] = record

        async with device.session(final_future):
            device.attrs.attrs_reset()
            assert not attrs._started

            await attrs.attrs_apply(
                attrs.attrs_path("one").changer_to(5),
                attrs.attrs_path("two").changer_to({"one": 1}),
                attrs.attrs_path("three").changer_to("blah"),
                event=None,
            )

            device.attrs.attrs_start()
            assert attrs._started

            await attrs.attrs_apply(attrs.attrs_path("one").changer_to(10), event=None)

        record.seek(0)
        assert (
            record.read()
            == dedent(
                """
        TIME -> d073d5001337(LCM2_A19:2,80) SHUTTING_DOWN

        TIME -> d073d5001337(LCM2_A19:2,80) POWER_OFF

        TIME -> d073d5001337(LCM2_A19:2,80) RESET
          :: zerod = False

        TIME -> d073d5001337(LCM2_A19:2,80) POWER_ON

        TIME -> d073d5001337(LCM2_A19:2,80) ATTRIBUTE_CHANGE
          -- Attributes changed (started)
          ~ <Changed one to 10>

        TIME -> d073d5001337(LCM2_A19:2,80) DELETE

        """
            ).lstrip()
        )

        assert MergedOptions.using(attrs._attrs).as_dict() == {
            "one": 10,
            "two": {"one": 1},
            "three": "blah",
        }
