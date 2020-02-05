# coding: spec

from photons_app.registers import (
    Target,
    TargetRegister,
    ProtocolRegister,
    MessagesRegister,
    ReferenceResolerRegister,
)
from photons_app.option_spec.photons_app_spec import PhotonsAppSpec
from photons_app.errors import TargetNotFound, ResolverNotFound

from delfick_project.errors_pytest import assertRaises
from delfick_project.option_merge import MergedOptions
from delfick_project.norms import dictobj, sb, Meta
from unittest import mock
import pytest
import pickle


@pytest.fixture()
def collector():
    return mock.Mock(name="collector")


describe "Target":
    it "takes in things":
        target = Target.FieldSpec().empty_normalise(type="thing", optional=True, options={"one": 2})
        assert target.type == "thing"
        assert target.optional == True
        assert target.options == {"one": 2}

    it "has defaults":
        target = Target.FieldSpec().empty_normalise(type="thing")
        assert target.type == "thing"
        assert target.optional == False
        assert target.options == {}

describe "MessageRegister":
    it "has message_classes list":
        register = MessagesRegister()
        assert register.message_classes == []

    it "can add classes":
        kls = mock.Mock(name="kls")
        kls2 = mock.Mock(name="kls2")

        register = MessagesRegister()
        register.add(kls)
        assert register.message_classes == [kls]

        register.add(kls2)
        assert register.message_classes == [kls, kls2]

    it "can iter classes":
        kls = mock.Mock(name="kls")
        kls2 = mock.Mock(name="kls2")

        register = MessagesRegister()
        assert list(register) == []

        register.add(kls)
        assert list(register) == [kls]

        register.add(kls2)
        assert list(register) == [kls, kls2]

describe "ProtocolRegister":
    it "can be formatted":
        assert ProtocolRegister._merged_options_formattable == True

    it "has a dictionary of protocol_classes":
        register = ProtocolRegister()
        assert register.protocol_classes == {}

    it "can add protocol klses":
        protocol = mock.Mock(name="protocol")
        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        assert register.protocol_classes == {protocol: (kls, mock.ANY)}
        assert isinstance(register.protocol_classes[protocol][1], MessagesRegister)

    it "can iter protocols":
        protocol = mock.Mock(name="protocol")
        protocol2 = mock.Mock(name="protocol2")

        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        assert list(register) == [protocol]

        register.add(protocol2, kls)
        assert list(register) == [protocol, protocol2]

    it "has getitem and get synatx into protocol_classes":
        register = ProtocolRegister()
        protocol = mock.Mock(name="protocol")
        protocol2 = mock.Mock(name="protocol2")

        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        assert register[protocol] == register.protocol_classes[protocol]

        assert register.get(protocol) == register.protocol_classes[protocol]

        assert register.get(protocol2) == None

        dflt = mock.Mock(name="dflt")
        assert register.get(protocol2, dflt) is dflt

    it "can get message_register for a protocol":
        protocol = mock.Mock(name="protocol")
        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        assert register.message_register(protocol) is register.protocol_classes[protocol][1]

    it "can be pickled (for the docs)":
        register = ProtocolRegister()
        pickled = pickle.dumps(register)
        unpickled = pickle.loads(pickled)
        assert isinstance(unpickled, ProtocolRegister)

describe "TargetRegister":
    it "can be formatted":
        assert TargetRegister._merged_options_formattable == True

    it "has some things on it", collector:
        register = TargetRegister(collector)
        assert register.collector is collector
        assert register.types == {}
        assert register.targets == {}

    it "can get target_values", collector:
        target1 = mock.Mock(name="target1")
        maker1 = mock.Mock(name="maker1", return_value=("type1", target1))

        target2 = mock.Mock(name="target2")
        maker2 = mock.Mock(name="maker2", return_value=("type2", target2))

        register = TargetRegister(collector)
        register.targets["target1"] = maker1
        register.targets["target2"] = maker2

        assert register.target_values == [target1, target2]

    it "can get used targets", collector:
        meta = Meta({}, []).at("targets")
        targets = PhotonsAppSpec().targets_spec.normalise(
            meta,
            {
                "target1": {"type": "example", "options": {"one": 1}},
                "target2": {"type": "example", "options": {"one": 2}},
            },
        )

        class T(dictobj.Spec):
            one = dictobj.Field(sb.integer_spec)

        register = TargetRegister(collector)
        register.register_type("example", T.FieldSpec())
        for name, options in targets.items():
            register.add_target(name, options)

        assert register.used_targets == []

        first = register.resolve("target1")
        assert first.one == 1
        assert register.used_targets == [first]

        second = register.resolve("target2")
        assert second.one == 2
        assert register.used_targets == [first, second]

    it "can get type for a target name", collector:
        target1 = mock.Mock(name="target1")
        maker1 = mock.Mock(name="maker1", return_value=("type1", target1))

        target2 = mock.Mock(name="target2")
        maker2 = mock.Mock(name="maker2", return_value=("type2", target2))

        register = TargetRegister(collector)
        register.targets["target1"] = maker1
        register.targets["target2"] = maker2

        assert register.type_for("target1") == "type1"
        assert register.type_for("target2") == "type2"
        assert register.type_for("target3") == None

    it "says the type for sb.NotSpecified is None", collector:
        register = TargetRegister(collector)
        assert register.type_for(sb.NotSpecified) == None

    it "can get description of a target", collector:
        desc = mock.Mock(name="desc")
        target1 = mock.Mock(name="target1", description=desc)
        maker1 = mock.Mock(name="maker1", return_value=("type1", target1))

        target2 = mock.Mock(name="target2", spec=[])
        maker2 = mock.Mock(name="maker2", return_value=("type2", target2))

        register = TargetRegister(collector)
        register.targets["target1"] = maker1
        register.targets["target2"] = maker2

        assert register.desc_for("target1") is desc
        assert register.desc_for("target2") == ""
        assert register.desc_for(sb.NotSpecified) is None

    it "can register a type", collector:
        name = mock.Mock(name="mock")
        target = mock.Mock(name="target")
        target2 = mock.Mock(name="target")
        register = TargetRegister(collector)

        register.register_type(name, target)
        assert register.types == {name: target}

        # And we can override
        register.register_type(name, target2)
        assert register.types == {name: target2}

    it "can resolve a name", collector:
        desc = mock.Mock(name="desc")
        target1 = mock.Mock(name="target1", description=desc)
        maker1 = mock.Mock(name="maker1", return_value=("type1", target1))

        target2 = mock.Mock(name="target2", spec=[])
        maker2 = mock.Mock(name="maker2", return_value=("type2", target2))

        register = TargetRegister(collector)
        register.targets["target1"] = maker1
        register.targets["target2"] = maker2

        assert register.resolve("target1") is target1
        assert register.resolve("target2") is target2

        with assertRaises(TargetNotFound, name="target3", available=["target1", "target2"]):
            register.resolve("target3")

    it "can add a dictionary of targets", collector:
        add_target = mock.Mock(name="add_target")

        register = TargetRegister(collector)

        target1 = mock.Mock(name="target1")
        target2 = mock.Mock(name="target2")

        with mock.patch.object(register, "add_target", add_target):
            register.add_targets({"one": target1, "two": target2})

        assert add_target.mock_calls == [mock.call("one", target1), mock.call("two", target2)]

    describe "adding a target":

        @pytest.fixture()
        def configuration(self):
            return MergedOptions()

        @pytest.fixture()
        def collector(self, collector, configuration):
            collector.configuration = configuration
            return collector

        @pytest.fixture()
        def register(self, collector):
            return TargetRegister(collector)

        it "complains if the type doesn't exist", register:
            target = Target.FieldSpec().empty_normalise(type="blah")
            with assertRaises(
                TargetNotFound,
                "Unknown type specified for target",
                name="target1",
                specified="blah",
            ):
                register.add_target("target1", target)

        it "does not complain if it can't find type and target is optional", register:
            target = Target.FieldSpec().empty_normalise(type="blah", optional=True)
            register.add_target("target1", target)
            assert register.targets == {}

        it "returns a function that creates our target", register, configuration:
            value = mock.Mock(name="value")
            spec = mock.Mock(name="spec")
            spec.normalise.return_value = value

            register.register_type("blah", spec)
            register.add_target(
                "thing", Target.FieldSpec().empty_normalise(type="blah", options={"one": 2})
            )

            assert len(spec.normalise.mock_calls) == 0
            assert register.resolve("thing") == value
            spec.normalise.assert_called_once_with(
                Meta(configuration, []).at("targets").at("thing").at("options"), {"one": 2}
            )

            # and it memoizes
            assert register.targets["thing"]() == ("blah", value)
            assert len(spec.normalise.mock_calls) == 1

describe "ReferenceResolerRegister":

    @pytest.fixture()
    def register(self):
        return ReferenceResolerRegister()

    describe "initialization":
        it "has file resolver by default", register:
            filename = mock.Mock(name="filename")
            resolver = mock.Mock(name="resolver")
            FakeResolveReferencesFromFile = mock.Mock(
                name="ResolveReferencesFromFile", return_value=resolver
            )

            with mock.patch(
                "photons_app.registers.ResolveReferencesFromFile", FakeResolveReferencesFromFile
            ):
                r = register.resolve("file", filename, mock.Mock(name="target"))

            assert r is resolver
            FakeResolveReferencesFromFile.assert_called_once_with(filename)

    describe "adding a resolver":
        it "adds and overrides", register:
            typ = mock.Mock(name="typ")
            resolver = mock.Mock(name="resolver")
            register.add(typ, resolver)
            assert register.resolvers[typ] is resolver

            resolver2 = mock.Mock(name="resolver2")
            register.add(typ, resolver2)
            assert register.resolvers[typ] is resolver2

    describe "resolving":
        it "complains if the typ isn't registered", register:
            typ = mock.Mock(name="typ")
            with assertRaises(ResolverNotFound, wanted=typ):
                register.resolve(typ, "blah", mock.Mock(name="target"))

        it "uses registered resolver", register:
            ret = mock.Mock(name="ret")
            typ = mock.Mock(name="typ")
            target = mock.Mock(name="target")
            resolver = mock.Mock(name="resolver", return_value=ret)
            register.add(typ, resolver)
            assert register.resolve(typ, "blah", target) is ret
            resolver.assert_called_once_with("blah", target)
