import binascii
import pickle
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import sb
from photons_app.errors import ResolverNotFound
from photons_app.registers import (
    MessagesRegister,
    ProtocolRegister,
    ReferenceResolverRegister,
)
from photons_app.special import FoundSerials, HardCodedSerials, SpecialReference


@pytest.fixture()
def collector():
    return mock.Mock(name="collector")


class TestMessageRegister:
    def test_it_has_message_classes_list(self):
        register = MessagesRegister()
        assert register.message_classes == []

    def test_it_can_add_classes(self):
        kls = mock.Mock(name="kls")
        kls2 = mock.Mock(name="kls2")

        register = MessagesRegister()
        register.add(kls)
        assert register.message_classes == [kls]

        register.add(kls2)
        assert register.message_classes == [kls, kls2]

    def test_it_can_iter_classes(self):
        kls = mock.Mock(name="kls")
        kls2 = mock.Mock(name="kls2")

        register = MessagesRegister()
        assert list(register) == []

        register.add(kls)
        assert list(register) == [kls]

        register.add(kls2)
        assert list(register) == [kls, kls2]


class TestProtocolRegister:
    def test_it_can_be_formatted(self):
        assert ProtocolRegister._merged_options_formattable is True

    def test_it_has_a_dictionary_of_protocol_classes(self):
        register = ProtocolRegister()
        assert register.protocol_classes == {}

    def test_it_can_add_protocol_klses(self):
        protocol = mock.Mock(name="protocol")
        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        assert register.protocol_classes == {protocol: (kls, mock.ANY)}
        assert isinstance(register.protocol_classes[protocol][1], MessagesRegister)

    def test_it_can_iter_protocols(self):
        protocol = mock.Mock(name="protocol")
        protocol2 = mock.Mock(name="protocol2")

        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        assert list(register) == [protocol]

        register.add(protocol2, kls)
        assert list(register) == [protocol, protocol2]

    def test_it_has_getitem_and_get_synatx_into_protocol_classes(self):
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

    def test_it_can_get_message_register_for_a_protocol(self):
        protocol = mock.Mock(name="protocol")
        kls = mock.Mock(name="kls")
        register = ProtocolRegister()

        register.add(protocol, kls)
        assert register.message_register(protocol) is register.protocol_classes[protocol][1]

    def test_it_can_be_pickled_for_the_docs(self):
        register = ProtocolRegister()
        pickled = pickle.dumps(register)
        unpickled = pickle.loads(pickled)
        assert isinstance(unpickled, ProtocolRegister)


class TestReferenceResolverRegister:

    @pytest.fixture()
    def register(self):
        return ReferenceResolverRegister()

    class TestInitialization:
        def test_it_has_file_resolver_by_default(self, register):
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

    class TestAddingAResolver:
        def test_it_adds_and_overrides(self, register):
            typ = mock.Mock(name="typ")
            resolver = mock.Mock(name="resolver")
            register.add(typ, resolver)
            assert register.resolvers[typ] is resolver

            resolver2 = mock.Mock(name="resolver2")
            register.add(typ, resolver2)
            assert register.resolvers[typ] is resolver2

    class TestResolving:
        def test_it_complains_if_the_typ_isnt_registered(self, register):
            typ = mock.Mock(name="typ")
            with assertRaises(ResolverNotFound, wanted=typ):
                register.resolve(typ, "blah")

        def test_it_uses_registered_resolver(self, register):
            ret = mock.Mock(name="ret")
            typ = mock.Mock(name="typ")
            resolver = mock.Mock(name="resolver", return_value=ret)
            register.add(typ, resolver)
            assert register.resolve(typ, "blah") is ret
            resolver.assert_called_once_with("blah")

    class TestGettingAReferenceObject:

        def test_it_returns_SpecialReference_objects_as_is(self, register):

            class Reference(SpecialReference):
                pass

            ref = Reference()
            assert register.reference_object(ref) is ref

        def test_it_returns_a_FoundSerials_instruction_if_no_reference_is_specified(self, register):
            for r in ("", None, sb.NotSpecified):
                references = register.reference_object(r)
                assert isinstance(references, FoundSerials), references

            assert isinstance(register.reference_object("_"), FoundSerials)

        def test_it_returns_a_FoundSerials_for_an_underscore(self, register):
            references = register.reference_object("_")
            assert isinstance(references, FoundSerials), references

        def test_it_returns_the_resolved_reference_if_of_type_typoptions(self, register):
            ret = HardCodedSerials(["d073d5000001", "d073d5000002"])
            resolver = mock.Mock(name="resolver", return_value=ret)
            register.add("my_resolver", resolver)

            reference = "my_resolver:blah:and,stuff"
            resolved = register.reference_object(reference)
            assert resolved is ret

        def test_it_returns_a_SpecialReference_if_our_resolver_returns_not_a_special_reference(
            self, register
        ):
            ret = "d073d5000001,d073d5000002"
            wanted = [binascii.unhexlify(ref) for ref in ret.split(",")]

            for reference in (ret, ret.split(",")):
                resolver = mock.Mock(name="resolver", return_value=reference)

                register.add("my_resolver", resolver)

                reference = "my_resolver:blah:and,stuff"
                resolved = register.reference_object(reference)
                assert type(resolved) == HardCodedSerials, resolved
                assert resolved.targets == wanted

        def test_it_returns_hard_coded_serials_otherwise(self, register):
            serials = ["d073d5000001", "d073d5000002"]
            targets = [binascii.unhexlify(s) for s in serials]
            for ref in (serials, ",".join(serials)):
                reference = register.reference_object(ref)
                assert isinstance(reference, HardCodedSerials)
                assert reference.targets == targets
