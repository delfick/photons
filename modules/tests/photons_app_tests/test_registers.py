# coding: spec

from photons_app.registers import (
    Target,
    TargetRegister,
    ProtocolRegister,
    MessagesRegister,
    ReferenceResolerRegister,
)
from photons_app.errors import TargetNotFound, ResolverNotFound, TargetTypeNotFound
from photons_app.special import SpecialReference, HardCodedSerials, FoundSerials

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from unittest import mock
import binascii
import pickle
import pytest


@pytest.fixture()
def collector():
    return mock.Mock(name="collector")


describe "Target":
    it "takes in things":
        target = Target.FieldSpec().empty_normalise(type="thing", optional=True, options={"one": 2})
        assert target.type == "thing"
        assert target.optional is True
        assert target.options == {"one": 2}

    it "has defaults":
        target = Target.FieldSpec().empty_normalise(type="thing")
        assert target.type == "thing"
        assert target.optional is False
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
        assert ProtocolRegister._merged_options_formattable is True

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

        assert register.get(protocol2) is None

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
                r = register.resolve("file", filename)

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
                register.resolve(typ, "blah")

        it "uses registered resolver", register:
            ret = mock.Mock(name="ret")
            typ = mock.Mock(name="typ")
            resolver = mock.Mock(name="resolver", return_value=ret)
            register.add(typ, resolver)
            assert register.resolve(typ, "blah") is ret
            resolver.assert_called_once_with("blah")

    describe "getting a reference object":

        it "returns SpecialReference objects as is", register:

            class Reference(SpecialReference):
                pass

            ref = Reference()
            assert register.reference_object(ref) is ref

        it "returns a FoundSerials instruction if no reference is specified", register:
            for r in ("", None, sb.NotSpecified):
                references = register.reference_object(r)
                assert isinstance(references, FoundSerials), references

            assert isinstance(register.reference_object("_"), FoundSerials)

        it "returns a FoundSerials for an underscore", register:
            references = register.reference_object("_")
            assert isinstance(references, FoundSerials), references

        it "returns the resolved reference if of type typ:options", register:
            ret = HardCodedSerials(["d073d5000001", "d073d5000002"])
            resolver = mock.Mock(name="resolver", return_value=ret)
            register.add("my_resolver", resolver)

            reference = "my_resolver:blah:and,stuff"
            resolved = register.reference_object(reference)
            assert resolved is ret

        it "returns a SpecialReference if our resolver returns not a special reference", register:
            ret = "d073d5000001,d073d5000002"
            wanted = [binascii.unhexlify(ref) for ref in ret.split(",")]

            for reference in (ret, ret.split(",")):
                resolver = mock.Mock(name="resolver", return_value=reference)

                register.add("my_resolver", resolver)

                reference = "my_resolver:blah:and,stuff"
                resolved = register.reference_object(reference)
                assert type(resolved) == HardCodedSerials, resolved
                assert resolved.targets == wanted

        it "returns hard coded serials otherwise", register:
            serials = ["d073d5000001", "d073d5000002"]
            targets = [binascii.unhexlify(s) for s in serials]
            for ref in (serials, ",".join(serials)):
                reference = register.reference_object(ref)
                assert isinstance(reference, HardCodedSerials)
                assert reference.targets == targets

describe "TargetRegister":

    @pytest.fixture()
    def reg(self):
        return TargetRegister()

    it "has some information on it", reg:
        assert reg.types == {}
        assert reg.created == {}
        assert reg.registered == {}

    describe "getting registered tasks":
        it "complains if we ask for None", reg:
            with assertRaises(TargetNotFound, wanted=None):
                reg[None]

            reg.registered[None] = mock.Mock(name="info")
            with assertRaises(TargetNotFound, wanted=None):
                reg[None]

        it "complains if we ask for db.NotSpecified", reg:
            with assertRaises(TargetNotFound, wanted=sb.NotSpecified):
                reg[sb.NotSpecified]

            reg.registered[sb.NotSpecified] = mock.Mock(name="info")
            with assertRaises(TargetNotFound, wanted=sb.NotSpecified):
                reg[sb.NotSpecified]

        it "complains if the name not in registered", reg:
            with assertRaises(TargetNotFound, wanted="thing"):
                reg["thing"]

            thing = mock.Mock(name="info")
            reg.registered["thing"] = thing
            assert reg["thing"] is thing

        it "retrieves from registered", reg:
            thing = mock.Mock(name="info")
            reg.registered["thing"] = thing
            assert reg["thing"] is thing

    describe "used_targets":
        it "returns targets that were resolved", reg:
            made1 = mock.Mock(name="made1")
            made2 = mock.Mock(name="made2")
            made3 = mock.Mock(name="made3")

            creator1 = mock.Mock(name="creator1", return_value=made1)
            creator2 = mock.Mock(name="creator2", return_value=made2)
            creator3 = mock.Mock(name="creator3", return_value=made3)

            reg.register_type("o", mock.Mock(name="oTarget"))
            reg.register_type("t", mock.Mock(name="tTarget"))

            reg.add_target("one", Target.FieldSpec().empty_normalise(type="o"), creator1)
            reg.add_target("two", Target.FieldSpec().empty_normalise(type="t"), creator2)
            reg.add_target("three", Target.FieldSpec().empty_normalise(type="o"), creator3)

            assert reg.used_targets == []

            assert reg.resolve("one") is made1
            assert reg.used_targets == [made1]

            # Resolving again should make no difference
            assert reg.resolve("one") is made1
            assert reg.used_targets == [made1]

            # And multiple resolves should be fine
            assert reg.resolve("three") is made3
            assert reg.used_targets == [made1, made3]

    describe "type_for":
        it "returns the type of the target", reg:
            reg.register_type("o", mock.Mock(name="oTarget"))
            reg.add_target(
                "one", Target.FieldSpec().empty_normalise(type="o"), mock.Mock(name="creator")
            )
            assert reg.type_for("one") == "o"

            with assertRaises(TargetNotFound):
                reg.type_for("two")

            reg.register_type("s", mock.Mock(name="sTarget"))
            reg.add_target(
                "two", Target.FieldSpec().empty_normalise(type="s"), mock.Mock(name="creator")
            )
            assert reg.type_for("one") == "o"
            assert reg.type_for("two") == "s"

    describe "desc_for":
        it "returns description or doc or empty from a resolved target", reg:
            made = mock.Mock(name="made", spec=[])
            made.__doc__ = None
            creator = mock.Mock(name="creator", return_value=made)

            with assertRaises(TargetNotFound):
                reg.type_for("one")

            reg.register_type("o", mock.Mock(name="oTarget"))
            reg.add_target("one", Target.FieldSpec().empty_normalise(type="o"), creator)

            assert reg.desc_for("one") == ""
            made.__doc__ = "stuff and things"
            assert reg.desc_for("one") == "stuff and things"
            made.description = "better stuff"
            assert reg.desc_for("one") == "better stuff"

    describe "register_type":
        it "adds the type to the types dictionary", reg:
            assert reg.types == {}

            OneTarget = mock.Mock(name="OneTarget")
            reg.register_type("one", OneTarget)
            assert reg.types == {"one": OneTarget}

            OneTarget2 = mock.Mock(name="OneTarget2")
            reg.register_type("one", OneTarget2)
            assert reg.types == {"one": OneTarget2}

            TwoTarget = mock.Mock(name="TwoTarget")
            reg.register_type("two", TwoTarget)
            assert reg.types == {"one": OneTarget2, "two": TwoTarget}

    describe "resolve":
        it "will use already created target if one exists", reg:
            made = mock.Mock(name="made")
            reg.created["one"] = made
            assert reg.resolve("one") is made

        it "will complain if the name doesn't exists", reg:
            with assertRaises(TargetNotFound, wanted="things"):
                reg.resolve("things")

        it "will use the type object and the creator to create a target", reg:
            HeroTarget = mock.Mock(name="HeroTarget")

            made = mock.Mock(name="made")
            target = Target.FieldSpec().empty_normalise(type="hero")
            creator = mock.Mock(name="creator", spec=[], return_value=made)

            reg.register_type("hero", HeroTarget)
            reg.add_target("superman", target, creator)

            assert reg.resolve("superman") is made
            creator.assert_called_once_with("superman", HeroTarget, target)

    describe "add_target":
        it "complains if the type doesn't exist and the target isn't optional", reg:
            target = Target.FieldSpec().empty_normalise(type="hero")
            assert not target.optional

            with assertRaises(TargetTypeNotFound, target="superman", wanted="hero"):
                reg.add_target("superman", target, mock.Mock(name="creator"))

        it "does nothing if the type doesn't exist but the target is optional", reg:
            target = Target.FieldSpec().empty_normalise(type="hero", optional=True)
            reg.add_target("superman", target, mock.Mock(name="creator"))
            assert reg.registered == {}

        it "puts the information in registered otherwise", reg:
            HeroTarget = mock.Mock(name="HeroTarget")
            reg.register_type("hero", HeroTarget)

            target = Target.FieldSpec().empty_normalise(type="hero")
            creator = mock.Mock(name="creator")
            reg.add_target("superman", target, creator)
            assert reg.registered == {"superman": ("hero", target, creator)}

            target2 = Target.FieldSpec().empty_normalise(type="hero")
            creator2 = mock.Mock(name="creator2")
            reg.add_target("batman", target2, creator2)
            assert reg.registered == {
                "superman": ("hero", target, creator),
                "batman": ("hero", target2, creator2),
            }
