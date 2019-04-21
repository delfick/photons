# coding: spec

from photons_protocol.packets import PacketSpecMetaKls, dictobj, Initial
from photons_protocol.types import Type as T

from photons_app.errors import ProgrammerError
from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms import spec_base as sb
from unittest import mock
import uuid

describe TestCase, "PacketSpecMetaKls":
    it "complains if we have fields that are already attributes":
        with self.fuzzyAssertRaisesError(ProgrammerError, "Can't override attributes with fields\talready_attributes=\['items', 'values'\]"):
            class Together(dictobj.PacketSpec):
                fields = [("items", T.Bool), ("values", T.Bool), ("one", T.Bool)]

        with self.fuzzyAssertRaisesError(ProgrammerError, "Can't override attributes with fields\talready_attributes=\['one'\]"):
            class Together(dictobj.PacketSpec):
                fields = [("one", T.Bool)]

                def one(self):
                    pass

    it "complains if we have duplicate names":
        class Group1(metaclass=PacketSpecMetaKls):
            fields = [("one", T.Bool), ("two", T.Bool)]

        class Group2(metaclass=PacketSpecMetaKls):
            fields = [("two", T.Bool), ("three", T.Bool)]

        with self.fuzzyAssertRaisesError(ProgrammerError, "Duplicated names!\t\['two', 'two'\]"):
            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", Group1), ("g2", Group2)]

        with self.fuzzyAssertRaisesError(ProgrammerError, "Duplicated names!\t\['one', 'one'\]"):
            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", Group1), ("one", T.Bool)]

    it "complains if we have fields as a dictionary":
        msg = "PacketSpecMixin expect fields to be a list of tuples, not a dictionary"
        with self.fuzzyAssertRaisesError(ProgrammerError, "{0}\tcreating=Child".format(msg)):
            class Child(metaclass=PacketSpecMetaKls):
                fields = {}

    it "complains if it can't find field":
        class Parent:
            fields = {}

        msg = "PacketSpecMixin expects a fields attribute on the class or a PacketSpec parent"
        with self.fuzzyAssertRaisesError(ProgrammerError, "{0}\tcreating=Child".format(msg)):
            class Child(Parent, metaclass=PacketSpecMetaKls):
                pass

        with self.fuzzyAssertRaisesError(ProgrammerError, "{0}\tcreating=Child".format(msg)):
            class Child(metaclass=PacketSpecMetaKls):
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
                self.assertIs(dflt(), Initial)
            else:
                normald += 1
                self.assertIs(dflt(), sb.NotSpecified)

        self.assertEqual(initiald, 2)
        self.assertEqual(normald, 4)

        for g in (Group1, Group2):
            for name, dflt in g.fields:
                self.assertIs(dflt(), sb.NotSpecified)

    it "allows mixins":
        yeap = str(uuid.uuid1())

        class Mixin:
            @property
            def yeap(self):
                return yeap

        class Wat(Mixin, metaclass=PacketSpecMetaKls):
            fields = []

        self.assertEqual(Wat().yeap, yeap)

        class Wat2(Wat):
            fields = []

        self.assertEqual(Wat2().yeap, yeap)

    describe "Meta":
        before_each:
            self.one_typ = mock.Mock(name="one_typ", spec=[])
            self.two_typ = mock.Mock(name="two_typ", spec=[])
            self.three_typ = mock.Mock(name="three_typ", spec=[])
            self.four_typ = mock.Mock(name="four_typ", spec=[])

            # Make us example groups
            class Group1(metaclass=PacketSpecMetaKls):
                fields = [("one", self.one_typ), ("two", self.two_typ)]

            class Group2(metaclass=PacketSpecMetaKls):
                fields = [("three", self.three_typ), ("four", self.four_typ)]

            self.Group1 = Group1
            self.Group2 = Group2

        it "has a nice repr":
            class Thing(metaclass=PacketSpecMetaKls):
                fields = []

            self.assertEqual(repr(Thing.Meta), "<type Thing.Meta>")

        it "has multi":
            class Thing(metaclass=PacketSpecMetaKls):
                fields = []

            self.assertIs(Thing.Meta.multi, None)

        it "has groups":
            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", self.Group1), ("g2", self.Group2), ("another", T.Bool)]

            self.assertEqual(Together.Meta.groups
                , { "g1": ["one", "two"]
                  , "g2": ["three", "four"]
                  }
                )

            self.assertEqual(self.Group1.Meta.groups, {})

        it "has name_to_group":
            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", self.Group1), ("g2", self.Group2), ("another", T.Bool)]

            self.assertEqual(Together.Meta.name_to_group
                , { "one": "g1"
                  , "two": "g1"
                  , "three": "g2"
                  , "four": "g2"
                  }
                )

            self.assertEqual(self.Group1.Meta.name_to_group, {})

        it "has all_names":
            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", self.Group1), ("g2", self.Group2), ("another", T.Bool)]

            self.assertEqual(Together.Meta.all_names, ["one", "two", "three", "four", "another"])
            self.assertEqual(self.Group1.Meta.all_names, ["one", "two"])

        it "has all_field_types":
            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", self.Group1), ("g2", self.Group2), ("another", T.Bool)]

            self.assertEqual(Together.Meta.all_field_types
                , [ ("one", self.one_typ), ("two", self.two_typ), ("three", self.three_typ), ("four", self.four_typ)
                  , ("another", T.Bool)
                  ]
                )
            self.assertEqual(Together.Meta.all_field_types_dict
                , dict(Together.Meta.all_field_types)
                )

            self.assertEqual(self.Group1.Meta.all_field_types
                , [("one", self.one_typ), ("two", self.two_typ)]
                )
            self.assertEqual(self.Group1.Meta.all_field_types_dict
                , dict(self.Group1.Meta.all_field_types)
                )

        it "has field_types":
            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", self.Group1), ("g2", self.Group2), ("another", T.Bool)]

            self.assertEqual(Together.Meta.field_types
                , [ ("g1", self.Group1), ("g2", self.Group2)
                  , ("another", T.Bool)
                  ]
                )
            self.assertEqual(Together.Meta.field_types_dict
                , dict(Together.Meta.field_types)
                )

            self.assertEqual(self.Group1.Meta.field_types
                , [("one", self.one_typ), ("two", self.two_typ)]
                )
            self.assertEqual(self.Group1.Meta.field_types_dict
                , dict(self.Group1.Meta.field_types)
                )

        it "has format_types":
            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", self.Group1), ("g2", self.Group2), ("another", T.Bool)]

            self.assertEqual(Together.Meta.format_types
                , [self.Group1, self.Group2, T.Bool]
                )

            self.assertEqual(self.Group1.Meta.format_types
                , [self.one_typ, self.two_typ]
                )

            self.assertEqual(self.Group2.Meta.format_types
                , [self.three_typ, self.four_typ]
                )

        it "has original_fields":
            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", self.Group1), ("g2", self.Group2), ("another", T.Bool)]

            self.assertEqual(self.Group1.Meta.original_fields, [("one", self.one_typ), ("two", self.two_typ)])
            self.assertEqual(self.Group2.Meta.original_fields, [("three", self.three_typ), ("four", self.four_typ)])
            self.assertEqual(Together.Meta.original_fields, [("g1", self.Group1), ("g2", self.Group2), ("another", T.Bool)])

        it "can get type from a string":
            class Together(metaclass=PacketSpecMetaKls):
                fields = [("g1", self.Group1), ("g2", self.Group2), ("another", "Another")]

                class Another(metaclass=PacketSpecMetaKls):
                    fields = []

            class Child(Together):
                class Another(metaclass=PacketSpecMetaKls):
                    fields = [("five", T.String), ("six", T.JSON)]

            self.assertEqual(repr(Together.Meta), "<type Together.Meta>")
            self.assertEqual(repr(Child.Meta), "<type Child.Meta>")

            self.assertEqual(Together.Meta.groups
                , { "g1": ["one", "two"]
                  , "g2": ["three", "four"]
                  , "another": []
                  }
                )
            self.assertEqual(Together.Meta.name_to_group
                , { "one": "g1"
                  , "two": "g1"
                  , "three": "g2"
                  , "four": "g2"
                  }
                )
            self.assertEqual(Child.Meta.groups
                , { "g1": ["one", "two"]
                  , "g2": ["three", "four"]
                  , "another": ["five", "six"]
                  }
                )
            self.assertEqual(Child.Meta.name_to_group
                , { "one": "g1"
                  , "two": "g1"
                  , "three": "g2"
                  , "four": "g2"
                  , "five": "another"
                  , "six": "another"
                  }
                )

            self.assertEqual(Together.Meta.all_names, ["one", "two", "three", "four"])
            self.assertEqual(Child.Meta.all_names, ["one", "two", "three", "four", "five", "six"])

            self.assertEqual(Together.Meta.all_field_types
                , [ ("one", self.one_typ), ("two", self.two_typ), ("three", self.three_typ), ("four", self.four_typ)
                  ]
                )
            self.assertEqual(Together.Meta.all_field_types_dict
                , dict(Together.Meta.all_field_types)
                )
            self.assertEqual(Child.Meta.all_field_types
                , [ ("one", self.one_typ), ("two", self.two_typ), ("three", self.three_typ), ("four", self.four_typ)
                  , ("five", T.String), ("six", T.JSON)
                  ]
                )
            self.assertEqual(Child.Meta.all_field_types_dict
                , dict(Child.Meta.all_field_types)
                )

            self.assertEqual(Together.Meta.field_types
                , [ ("g1", self.Group1), ("g2", self.Group2)
                  , ("another", Together.Another)
                  ]
                )
            self.assertEqual(Together.Meta.field_types_dict
                , dict(Together.Meta.field_types)
                )
            self.assertEqual(Child.Meta.field_types
                , [ ("g1", self.Group1), ("g2", self.Group2)
                  , ("another", Child.Another)
                  ]
                )
            self.assertEqual(Child.Meta.field_types_dict
                , dict(Child.Meta.field_types)
                )

            self.assertEqual(Together.Meta.format_types
                , [self.Group1, self.Group2, Together.Another]
                )
            self.assertEqual(Child.Meta.format_types
                , [self.Group1, self.Group2, Child.Another]
                )

            self.assertEqual(Together.Meta.original_fields, [("g1", self.Group1), ("g2", self.Group2), ("another", "Another")])
            self.assertEqual(Child.Meta.original_fields, [("g1", self.Group1), ("g2", self.Group2), ("another", "Another")])
