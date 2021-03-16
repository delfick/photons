# coding: spec

from photons_app.registers import (
    ProtocolRegister,
    MessagesRegister,
    ReferenceResolerRegister,
)
from photons_app.special import SpecialReference, HardCodedSerials, FoundSerials
from photons_app.errors import ResolverNotFound

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from unittest import mock
import binascii
import pickle
import pytest


@pytest.fixture()
def collector():
    return mock.Mock(name="collector")


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
