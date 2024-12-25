import uuid
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from photons_app import helpers as hp
from photons_app.errors import ProgrammerError
from photons_protocol.packets import Initial, PacketSpecMetaKls, dictobj
from photons_protocol.types import Type as T


class TestPacketSpecMetaKls:
    def test_it_complains_if_we_have_fields_that_are_already_attributes(self):
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

    def test_it_complains_if_we_have_duplicate_names(self):

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

    def test_it_complains_if_we_have_fields_as_a_dictionary(self):
        msg = "PacketSpecMixin expect fields to be a list of tuples, not a dictionary"
        with assertRaises(ProgrammerError, f"{msg}\tcreating=Child"):

            class Child(metaclass=PacketSpecMetaKls):
                fields = {}

    def test_it_complains_if_it_cant_find_field(self):

        class Parent:
            fields = {}

        msg = "PacketSpecMixin expects a fields attribute on the class or a PacketSpec parent"
        with assertRaises(ProgrammerError, f"{msg}\tcreating=Child"):

            class Child(Parent, metaclass=PacketSpecMetaKls):
                pass

        with assertRaises(ProgrammerError, f"{msg}\tcreating=Child"):

            class Child2(metaclass=PacketSpecMetaKls):
                pass

    def test_it_sets_the_defaults_for_groups_to_Initial_and_sbNotSpecified_for_normal_fields(self):

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

    def test_it_allows_mixins(self):
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

    class TestMeta:

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

        def test_it_has_a_nice_repr(self):

            class Thing(metaclass=PacketSpecMetaKls):
                fields = []

            assert repr(Thing.Meta) == "<type Thing.Meta>"

        def test_it_has_multi(self):

            class Thing(metaclass=PacketSpecMetaKls):
                fields = []

            assert Thing.Meta.multi is None

        def test_it_has_groups(self, V):

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert Together.Meta.groups == {"g1": ["one", "two"], "g2": ["three", "four"]}

            assert V.Group1.Meta.groups == {}

        def test_it_has_name_to_group(self, V):

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert Together.Meta.name_to_group == {
                "one": "g1",
                "two": "g1",
                "three": "g2",
                "four": "g2",
            }

            assert V.Group1.Meta.name_to_group == {}

        def test_it_has_all_names(self, V):

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert Together.Meta.all_names == ["one", "two", "three", "four", "another"]
            assert V.Group1.Meta.all_names == ["one", "two"]

        def test_it_has_all_field_types(self, V):

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

        def test_it_has_field_types(self, V):

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

        def test_it_has_format_types(self, V):

            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", V.Group1), ("g2", V.Group2), ("another", T.Bool)]

            assert Together.Meta.format_types == [V.Group1, V.Group2, T.Bool]

            assert V.Group1.Meta.format_types == [V.one_typ, V.two_typ]

            assert V.Group2.Meta.format_types == [V.three_typ, V.four_typ]

        def test_it_has_original_fields(self, V):

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

        def test_it_can_get_type_from_a_string(self, V):

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
