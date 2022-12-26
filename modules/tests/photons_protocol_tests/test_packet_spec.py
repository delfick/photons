# coding: spec

import uuid
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from photons_app import helpers as hp
from photons_app.errors import ProgrammerError
from photons_protocol.packets import Initial, PacketSpecMetaKls, dictobj
from photons_protocol.types import Type as T

describe "PacketSpecMetaKls":
    it "complains if we have fields that are already attributes":
        with assertRaises(
            ProgrammerError,
            r"Can't override attributes with fields\talready_attributes=\['items', 'values'\]",
        ):

            class Together(dictobj.PacketSpec):
                fields = [("items", T.Bool), ("values", T.Bool), ("one", T.Bool)]

        with assertRaises(
            ProgrammerError, r"Can't override attributes with fields\talready_attributes=\['one'\]"
        ):

            class Together2(dictobj.PacketSpec):
                fields = [("one", T.Bool)]

                def one(self):
                    pass

    it "complains if we have duplicate names":

        class Group1(metaclass=PacketSpecMetaKls):
            fields = [("one", T.Bool), ("two", T.Bool)]

        class Group2(metaclass=PacketSpecMetaKls):
            fields = [("two", T.Bool), ("three", T.Bool)]

        with assertRaises(ProgrammerError, r"Duplicated names!\t\['two', 'two'\]"):

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", Group1), ("g2", Group2)]

        with assertRaises(ProgrammerError, r"Duplicated names!\t\['one', 'one'\]"):

            class Together2(metaclass=PacketSpecMetaKls):
                fields = [("g1", Group1), ("one", T.Bool)]

    it "complains if we have fields as a dictionary":
        msg = "PacketSpecMixin expect fields to be a list of tuples, not a dictionary"
        with assertRaises(ProgrammerError, f"{msg}\tcreating=Child"):

            class Child(metaclass=PacketSpecMetaKls):
                fields = {}

    it "complains if it can't find field":

        class Parent:
            fields = {}

        msg = "PacketSpecMixin expects a fields attribute on the class or a PacketSpec parent"
        with assertRaises(ProgrammerError, f"{msg}\tcreating=Child"):

            class Child(Parent, metaclass=PacketSpecMetaKls):
                pass

        with assertRaises(ProgrammerError, f"{msg}\tcreating=Child"):

            class Child2(metaclass=PacketSpecMetaKls):
                pass

    it "sets the defaults for groups to Initial and sb.NotSpecified for normal fields":

        class Group1(metaclass=PacketSpecMetaKls):
            fields = [("one", T.Bool), ("two", T.Bool)]

        class Group2(metaclass=PacketSpecMetaKls):
            fields = [("three", T.Bool), ("four", T.Bool)]

        class Together(metaclass=PacketSpecMetaKls):
            fields = [("g1", Group1), ("g2", Group2)]

        initiald = 0
        normald = 0
        for name, dflt in Together.fields:
            if name in ("g1", "g2"):
                initiald += 1
                assert dflt() is Initial
            else:
                normald += 1
                assert dflt() is sb.NotSpecified

        assert initiald == 2
        assert normald == 4

        for g in (Group1, Group2):
            for name, dflt in g.fields:
                assert dflt() is sb.NotSpecified

    it "allows mixins":
        yeap = str(uuid.uuid1())

        class Mixin:
            @property
            def yeap(self):
                return yeap

        class Wat(Mixin, metaclass=PacketSpecMetaKls):
            fields = []

        assert Wat().yeap == yeap

        class Wat2(Wat):
            fields = []

        assert Wat2().yeap == yeap

    describe "Meta":

        @pytest.fixture()
        def V(self):
            class V:
                one_typ = mock.Mock(name="one_typ", spec=[])
                two_typ = mock.Mock(name="two_typ", spec=[])
                three_typ = mock.Mock(name="three_typ", spec=[])
                four_typ = mock.Mock(name="four_typ", spec=[])

                @hp.memoized_property
                def Group1(s):
                    class Group1(metaclass=PacketSpecMetaKls):
                        fields = [("one", s.one_typ), ("two", s.two_typ)]

                    return Group1

                @hp.memoized_property
                def Group2(s):
                    class Group2(metaclass=PacketSpecMetaKls):
                        fields = [("three", s.three_typ), ("four", s.four_typ)]

                    return Group2

            return V()

        it "has a nice repr":

            class Thing(metaclass=PacketSpecMetaKls):
                fields = []

            assert repr(Thing.Meta) == "<type Thing.Meta>"

        it "has multi":

            class Thing(metaclass=PacketSpecMetaKls):
                fields = []

            assert Thing.Meta.multi is None

        it "has groups", V:

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert Together.Meta.groups == {"g1": ["one", "two"], "g2": ["three", "four"]}

            assert V.Group1.Meta.groups == {}

        it "has name_to_group", V:

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert Together.Meta.name_to_group == {
                "one": "g1",
                "two": "g1",
                "three": "g2",
                "four": "g2",
            }

            assert V.Group1.Meta.name_to_group == {}

        it "has all_names", V:

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert Together.Meta.all_names == ["one", "two", "three", "four", "another"]
            assert V.Group1.Meta.all_names == ["one", "two"]

        it "has all_field_types", V:

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert Together.Meta.all_field_types == [
                ("one", V.one_typ),
                ("two", V.two_typ),
                ("three", V.three_typ),
                ("four", V.four_typ),
                ("another", T.Bool),
            ]
            assert Together.Meta.all_field_types_dict == dict(Together.Meta.all_field_types)

            assert V.Group1.Meta.all_field_types == [
                ("one", V.one_typ),
                ("two", V.two_typ),
            ]
            assert V.Group1.Meta.all_field_types_dict == dict(V.Group1.Meta.all_field_types)

        it "has field_types", V:

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert Together.Meta.field_types == [
                ("g1", V.Group1),
                ("g2", V.Group2),
                ("another", T.Bool),
            ]
            assert Together.Meta.field_types_dict == dict(Together.Meta.field_types)

            assert V.Group1.Meta.field_types == [("one", V.one_typ), ("two", V.two_typ)]
            assert V.Group1.Meta.field_types_dict == dict(V.Group1.Meta.field_types)

        it "has format_types", V:

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert Together.Meta.format_types == [V.Group1, V.Group2, T.Bool]

            assert V.Group1.Meta.format_types == [V.one_typ, V.two_typ]

            assert V.Group2.Meta.format_types == [V.three_typ, V.four_typ]

        it "has original_fields", V:

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert V.Group1.Meta.original_fields == [
                ("one", V.one_typ),
                ("two", V.two_typ),
            ]
            assert V.Group2.Meta.original_fields == [
                ("three", V.three_typ),
                ("four", V.four_typ),
            ]
            assert Together.Meta.original_fields == [
                ("g1", V.Group1),
                ("g2", V.Group2),
                ("another", T.Bool),
            ]

        it "can get type from a string", V:

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", "Another")]

                class Another(metaclass=PacketSpecMetaKls):
                    fields = []

            class Child(Together):
                class Another(metaclass=PacketSpecMetaKls):
                    fields = [("five", T.String), ("six", T.JSON)]

            assert repr(Together.Meta) == "<type Together.Meta>"
            assert repr(Child.Meta) == "<type Child.Meta>"

            assert Together.Meta.groups == {
                "g1": ["one", "two"],
                "g2": ["three", "four"],
                "another": [],
            }
            assert Together.Meta.name_to_group == {
                "one": "g1",
                "two": "g1",
                "three": "g2",
                "four": "g2",
            }
            assert Child.Meta.groups == {
                "g1": ["one", "two"],
                "g2": ["three", "four"],
                "another": ["five", "six"],
            }
            assert Child.Meta.name_to_group == {
                "one": "g1",
                "two": "g1",
                "three": "g2",
                "four": "g2",
                "five": "another",
                "six": "another",
            }

            assert Together.Meta.all_names == ["one", "two", "three", "four"]
            assert Child.Meta.all_names == ["one", "two", "three", "four", "five", "six"]

            assert Together.Meta.all_field_types == [
                ("one", V.one_typ),
                ("two", V.two_typ),
                ("three", V.three_typ),
                ("four", V.four_typ),
            ]
            assert Together.Meta.all_field_types_dict == dict(Together.Meta.all_field_types)
            assert Child.Meta.all_field_types == [
                ("one", V.one_typ),
                ("two", V.two_typ),
                ("three", V.three_typ),
                ("four", V.four_typ),
                ("five", T.String),
                ("six", T.JSON),
            ]
            assert Child.Meta.all_field_types_dict == dict(Child.Meta.all_field_types)

            assert Together.Meta.field_types == [
                ("g1", V.Group1),
                ("g2", V.Group2),
                ("another", Together.Another),
            ]
            assert Together.Meta.field_types_dict == dict(Together.Meta.field_types)
            assert Child.Meta.field_types == [
                ("g1", V.Group1),
                ("g2", V.Group2),
                ("another", Child.Another),
            ]
            assert Child.Meta.field_types_dict == dict(Child.Meta.field_types)

            assert Together.Meta.format_types == [V.Group1, V.Group2, Together.Another]
            assert Child.Meta.format_types == [V.Group1, V.Group2, Child.Another]

            assert Together.Meta.original_fields == [
                ("g1", V.Group1),
                ("g2", V.Group2),
                ("another", "Another"),
            ]
            assert Child.Meta.original_fields == [
                ("g1", V.Group1),
                ("g2", V.Group2),
                ("another", "Another"),
            ]
