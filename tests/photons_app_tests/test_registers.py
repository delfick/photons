# coding: spec

from photons_app.registers import Target, TargetRegister, ProtocolRegister, MessagesRegister, ReferenceResolerRegister
from photons_app.option_spec.photons_app_spec import PhotonsAppSpec
from photons_app.errors import TargetNotFound, ResolverNotFound
from photons_app.test_helpers import TestCase

from noseOfYeti.tokeniser.support import noy_sup_setUp
from input_algorithms import spec_base as sb
from input_algorithms.dictobj import dictobj
from input_algorithms.meta import Meta
from option_merge import MergedOptions
from unittest import mock
import pickle

describe TestCase, "Target":
    it "takes in things":
        target = Target.FieldSpec().empty_normalise(type="thing", optional=True, options={"one": 2})
        self.assertEqual(target.type, "thing")
        self.assertEqual(target.optional, True)
        self.assertEqual(target.options, {"one": 2})

    it "has defaults":
        target = Target.FieldSpec().empty_normalise(type="thing")
        self.assertEqual(target.type, "thing")
        self.assertEqual(target.optional, False)
        self.assertEqual(target.options, {})

describe TestCase, "MessageRegister":
    it "has message_classes list":
        register = MessagesRegister()
        self.assertEqual(register.message_classes, [])

    it "can add classes":
        kls = mock.Mock(name="kls")
        kls2 = mock.Mock(name="kls2")

        register = MessagesRegister()
        register.add(kls)
        self.assertEqual(register.message_classes, [kls])

        register.add(kls2)
        self.assertEqual(register.message_classes, [kls, kls2])

    it "can iter classes":
        kls = mock.Mock(name="kls")
        kls2 = mock.Mock(name="kls2")

        register = MessagesRegister()
        self.assertEqual(list(register), [])

        register.add(kls)
        self.assertEqual(list(register), [kls])

        register.add(kls2)
        self.assertEqual(list(register), [kls, kls2])

describe TestCase, "ProtocolRegister":
    it "can be formatted":
        self.assertEqual(ProtocolRegister._merged_options_formattable, True)

    it "has a dictionary of protocol_classes":
        register = ProtocolRegister()
        self.assertEqual(register.protocol_classes, {})

    it "can add protocol klses":
        protocol = mock.Mock(name="protocol")
        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        self.assertEqual(register.protocol_classes, {protocol: (kls, mock.ANY)})
        assert isinstance(register.protocol_classes[protocol][1], MessagesRegister)

    it "can iter protocols":
        protocol = mock.Mock(name="protocol")
        protocol2 = mock.Mock(name="protocol2")

        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        self.assertEqual(list(register), [protocol])

        register.add(protocol2, kls)
        self.assertEqual(list(register), [protocol, protocol2])

    it "has getitem and get synatx into protocol_classes":
        register = ProtocolRegister()
        protocol = mock.Mock(name="protocol")
        protocol2 = mock.Mock(name="protocol2")

        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        self.assertEqual(register[protocol], register.protocol_classes[protocol])

        self.assertEqual(register.get(protocol), register.protocol_classes[protocol])

        self.assertEqual(register.get(protocol2), None)

        dflt = mock.Mock(name='dflt')
        self.assertIs(register.get(protocol2, dflt), dflt)

    it "can get message_register for a protocol":
        protocol = mock.Mock(name="protocol")
        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        self.assertIs(register.message_register(protocol), register.protocol_classes[protocol][1])

    it "can be pickled (for the docs)":
        register = ProtocolRegister()
        pickled = pickle.dumps(register)
        unpickled = pickle.loads(pickled)
        assert isinstance(unpickled, ProtocolRegister)

describe TestCase, "TargetRegister":
    before_each:
        self.collector = mock.Mock(name="collector")

    it "can be formatted":
        self.assertEqual(TargetRegister._merged_options_formattable, True)

    it "has some things on it":
        register = TargetRegister(self.collector)
        self.assertIs(register.collector, self.collector)
        self.assertEqual(register.types, {})
        self.assertEqual(register.targets, {})

    it "can get target_values":
        target1 = mock.Mock(name="target1")
        maker1 = mock.Mock(name="maker1", return_value=("type1", target1))

        target2 = mock.Mock(name="target2")
        maker2 = mock.Mock(name="maker2", return_value=("type2", target2))

        register = TargetRegister(self.collector)
        register.targets["target1"] = maker1
        register.targets["target2"] = maker2

        self.assertEqual(register.target_values, [target1, target2])

    it "can get used targets":
        meta = Meta({}, []).at("targets")
        targets = PhotonsAppSpec().targets_spec.normalise(meta
            , { "target1": {"type": "example", "options": {"one": 1}}
              , "target2": {"type": "example", "options": {"one": 2}}
              }
            )

        class T(dictobj.Spec):
            one = dictobj.Field(sb.integer_spec)

        register = TargetRegister(self.collector)
        register.register_type("example", T.FieldSpec())
        for name, options in targets.items():
            register.add_target(name, options)

        self.assertEqual(register.used_targets, [])

        first = register.resolve("target1")
        self.assertEqual(first.one, 1)
        self.assertEqual(register.used_targets, [first])

        second = register.resolve("target2")
        self.assertEqual(second.one, 2)
        self.assertEqual(register.used_targets, [first, second])

    it "can get type for a target name":
        target1 = mock.Mock(name="target1")
        maker1 = mock.Mock(name="maker1", return_value=("type1", target1))

        target2 = mock.Mock(name="target2")
        maker2 = mock.Mock(name="maker2", return_value=("type2", target2))

        register = TargetRegister(self.collector)
        register.targets["target1"] = maker1
        register.targets["target2"] = maker2

        self.assertEqual(register.type_for("target1"), "type1")
        self.assertEqual(register.type_for("target2"), "type2")
        self.assertEqual(register.type_for("target3"), None)

    it "says the type for sb.NotSpecified is None":
        register = TargetRegister(self.collector)
        self.assertEqual(register.type_for(sb.NotSpecified), None)

    it "can get description of a target":
        desc = mock.Mock(name="desc")
        target1 = mock.Mock(name="target1", description=desc)
        maker1 = mock.Mock(name="maker1", return_value=("type1", target1))

        target2 = mock.Mock(name="target2", spec=[])
        maker2 = mock.Mock(name="maker2", return_value=("type2", target2))

        register = TargetRegister(self.collector)
        register.targets["target1"] = maker1
        register.targets["target2"] = maker2

        self.assertIs(register.desc_for("target1"), desc)
        self.assertEqual(register.desc_for("target2"), "")
        self.assertIs(register.desc_for(sb.NotSpecified), None)

    it "can register a type":
        name = mock.Mock(name="mock")
        target = mock.Mock(name="target")
        target2 = mock.Mock(name="target")
        register = TargetRegister(self.collector)

        register.register_type(name, target)
        self.assertEqual(register.types, {name: target})

        # And we can override
        register.register_type(name, target2)
        self.assertEqual(register.types, {name: target2})

    it "can resolve a name":
        desc = mock.Mock(name="desc")
        target1 = mock.Mock(name="target1", description=desc)
        maker1 = mock.Mock(name="maker1", return_value=("type1", target1))

        target2 = mock.Mock(name="target2", spec=[])
        maker2 = mock.Mock(name="maker2", return_value=("type2", target2))

        register = TargetRegister(self.collector)
        register.targets["target1"] = maker1
        register.targets["target2"] = maker2

        self.assertIs(register.resolve("target1"), target1)
        self.assertIs(register.resolve("target2"), target2)

        with self.fuzzyAssertRaisesError(TargetNotFound, name="target3", available=["target1", "target2"]):
            register.resolve("target3")

    it "can add a dictionary of targets":
        add_target = mock.Mock(name="add_target")

        register = TargetRegister(self.collector)

        target1 = mock.Mock(name='target1')
        target2 = mock.Mock(name='target2')

        with mock.patch.object(register, "add_target", add_target):
            register.add_targets({"one": target1, "two": target2})

        self.assertEqual(add_target.mock_calls
            , [ mock.call("one", target1)
              , mock.call("two", target2)
              ]
            )

    describe "adding a target":
        before_each:
            self.register = TargetRegister(self.collector)
            self.configuration = MergedOptions()
            self.collector.configuration = self.configuration

        it "complains if the type doesn't exist":
            target = Target.FieldSpec().empty_normalise(type="blah")
            with self.fuzzyAssertRaisesError(TargetNotFound, "Unknown type specified for target", name="target1", specified="blah"):
                self.register.add_target("target1", target)

        it "does not complain if it can't find type and target is optional":
            target = Target.FieldSpec().empty_normalise(type="blah", optional=True)
            self.register.add_target("target1", target)
            self.assertEqual(self.register.targets, {})

        it "returns a function that creates our target":
            value = mock.Mock(name="value")
            spec = mock.Mock(name='spec')
            spec.normalise.return_value = value

            self.register.register_type("blah", spec)
            self.register.add_target("thing", Target.FieldSpec().empty_normalise(type="blah", options={"one": 2}))

            self.assertEqual(len(spec.normalise.mock_calls), 0)
            self.assertEqual(self.register.resolve("thing"), value)
            spec.normalise.assert_called_once_with(Meta(self.configuration, []).at("targets").at("thing").at("options"), {"one": 2})

            # and it memoizes
            self.assertEqual(self.register.targets["thing"](), ("blah", value))
            self.assertEqual(len(spec.normalise.mock_calls), 1)

describe TestCase, "ReferenceResolerRegister":
    before_each:
        self.register = ReferenceResolerRegister()

    describe "initialization":
        it "has file resolver by default":
            filename = mock.Mock(name="filename")
            resolver = mock.Mock(name="resolver")
            FakeResolveReferencesFromFile = mock.Mock(name="ResolveReferencesFromFile", return_value=resolver)

            with mock.patch("photons_app.registers.ResolveReferencesFromFile", FakeResolveReferencesFromFile):
                r = self.register.resolve("file", filename, mock.Mock(name="target"))

            self.assertIs(r, resolver)
            FakeResolveReferencesFromFile.assert_called_once_with(filename)

    describe "adding a resolver":
        it "adds and overrides":
            typ = mock.Mock(name='typ')
            resolver = mock.Mock(name='resolver')
            self.register.add(typ, resolver)
            self.assertIs(self.register.resolvers[typ], resolver)

            resolver2 = mock.Mock(name="resolver2")
            self.register.add(typ, resolver2)
            self.assertIs(self.register.resolvers[typ], resolver2)

    describe "resolving":
        it "complains if the typ isn't registered":
            typ = mock.Mock(name='typ')
            with self.fuzzyAssertRaisesError(ResolverNotFound, wanted=typ):
                self.register.resolve(typ, "blah", mock.Mock(name="target"))

        it "uses registered resolver":
            ret = mock.Mock(name="ret")
            typ = mock.Mock(name='typ')
            target = mock.Mock(name="target")
            resolver = mock.Mock(name="resolver", return_value=ret)
            self.register.add(typ, resolver)
            self.assertIs(self.register.resolve(typ, "blah", target), ret)
            resolver.assert_called_once_with("blah", target)
