
import binascii
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import BadSpecValue, Meta, sb
from photons_messages import Services
from photons_transport.session import discovery_options as do


@pytest.fixture()
def meta():
    return Meta.empty()


class TestServiceTypeSpec:

    @pytest.fixture()
    def spec(self):
        return do.service_type_spec()

    def test_it_returns_as_is_if_the_value_is_already_a_Services(self, meta, spec):
        val = Services.UDP
        assert spec.normalise(meta, val) is val

    def test_it_returns_the_enum_value_if_it_matches(self, meta, spec):
        val = "UDP"
        assert spec.normalise(meta, val) is Services.UDP

    def test_it_complains_if_we_dont_have_a_match(self, meta, spec):
        msg = "Unknown service type"

        services = sorted([s.name for s in Services if not s.name.startswith("RESERVED")])
        assert len(services) > 0

        kwargs = dict(want="WAT", available=services)
        with assertRaises(BadSpecValue, msg, **kwargs):
            spec.normalise(meta, "WAT")

class TestHardcodedDiscoverySpec:

    @pytest.fixture()
    def spec(self):
        return do.hardcoded_discovery_spec()

    @pytest.fixture()
    def ret(self):
        return mock.Mock(name="ret")

    @pytest.fixture()
    def fake_spec(self, ret):
        fake_spec = mock.Mock(name="fake_spec")
        fake_spec.normalise.return_value = ret
        return fake_spec

    def test_it_uses_HARDCODED_DISCOVERY_environment_variable_if_it_exists(self, meta, spec, ret, fake_spec):
        spec.spec = fake_spec

        with pytest.helpers.modified_env(HARDCODED_DISCOVERY='{"one": "two"}'):
            for v in (sb.NotSpecified, None, {"three": "four"}):
                assert spec.normalise(meta, v) is ret
                fake_spec.normalise.assert_called_once_with(mock.ANY, {"one": "two"})
                fake_spec.normalise.reset_mock()

        with pytest.helpers.modified_env(HARDCODED_DISCOVERY="null"):
            for v in (sb.NotSpecified, None, {"three": "four"}):
                assert spec.normalise(meta, v) is None
                assert len(fake_spec.normalise.mock_calls) == 0

    def test_it_does_nothing_with_sbNotSpecified(self, meta, spec, fake_spec):
        spec.spec = fake_spec
        assert spec.normalise(meta, sb.NotSpecified) is sb.NotSpecified
        assert len(fake_spec.normalise.mock_calls) == 0

    def test_it_otherwise_uses_spec(self, meta, spec, ret, fake_spec):
        spec.spec = fake_spec
        val = mock.Mock(name="val")
        assert spec.normalise(meta, val) is ret
        fake_spec.normalise.assert_called_once_with(meta, val)

    def test_it_works(self, meta, spec):
        val = {
            "d073d5001337": "192.168.0.14",
            "d073d5001338": ["192.168.0.15"],
            "d073d5001339": ["192.168.0.16", 56],
            "d073d5001340": {"UDP": "192.168.0.17"},
            "d073d5001341": {"UDP": ["192.168.0.18"]},
            "d073d5001342": {"UDP": ["192.168.0.19", 78]},
            "d073d5001343": {"UDP": {"host": "192.168.0.20", "port": 90}},
        }

        res = spec.normalise(meta, val)

        assert res == {
            "d073d5001337": {Services.UDP: {"host": "192.168.0.14", "port": 56700}},
            "d073d5001338": {Services.UDP: {"host": "192.168.0.15", "port": 56700}},
            "d073d5001339": {Services.UDP: {"host": "192.168.0.16", "port": 56}},
            "d073d5001340": {Services.UDP: {"host": "192.168.0.17", "port": 56700}},
            "d073d5001341": {Services.UDP: {"host": "192.168.0.18", "port": 56700}},
            "d073d5001342": {Services.UDP: {"host": "192.168.0.19", "port": 78}},
            "d073d5001343": {Services.UDP: {"host": "192.168.0.20", "port": 90}},
        }

    def test_it_complains_if_the_keys_are_not_serials(self, meta, spec):
        val = {
            "d073d500133": "192.168.0.14",
            "e073d5001338": "192.168.0.15",
            "d073d5zz1339": "192.168.0.16",
            True: "192.168.0.17",
        }

        class S:
            def __init__(s, expected):
                s.expected = expected

            def __eq__(s, other):
                return s.expected == str(other)

        e1 = BadSpecValue(
            "serials must be 12 characters long, like d073d5001337",
            got="d073d500133",
            meta=meta.at("d073d500133"),
        )
        e2 = BadSpecValue(
            "serials must start with d073d5", got="e073d5001338", meta=meta.at("e073d5001338")
        )
        e3 = BadSpecValue(
            "serials must be valid hex",
            error=S("Non-hexadecimal digit found"),
            got="d073d5zz1339",
            meta=meta.at("d073d5zz1339"),
        )
        e4 = BadSpecValue("Expected a string", got=bool, meta=meta.at(True))

        errors = [e1, e2, e3, e4]
        with assertRaises(BadSpecValue, _errors=errors):
            spec.normalise(meta, val)

class TestServiceInfoSpec:

    @pytest.fixture()
    def spec(self):
        return do.service_info_spec()

    def test_it_can_expand_a_string(self, meta, spec):
        res = spec.normalise(meta, "192.168.0.1")
        assert res == {Services.UDP: {"host": "192.168.0.1", "port": 56700}}

    def test_it_can_expand_a_singe_item_list(self, meta, spec):
        res = spec.normalise(meta, ["192.168.0.1"])
        assert res == {Services.UDP: {"host": "192.168.0.1", "port": 56700}}

    def test_it_can_expand_a_two_item_list(self, meta, spec):
        res = spec.normalise(meta, ["192.168.0.1", 67])
        assert res == {Services.UDP: {"host": "192.168.0.1", "port": 67}}

    def test_it_complains_about_other_length_lists(self, meta, spec):
        msg = r"A list must be \[host\] or \[host, port\]"
        with assertRaises(BadSpecValue, msg, got=[]):
            spec.normalise(meta, [])

        with assertRaises(BadSpecValue, msg, got=[1, 2, 3]):
            spec.normalise(meta, [1, 2, 3])

    def test_it_complains_about_lists_with_wrong_types(self, meta, spec):
        e1 = BadSpecValue("Expected a string", got=int, meta=meta.at("UDP").at("host"))
        e2 = BadSpecValue("Expected an integer", got=str, meta=meta.at("UDP").at("port"))
        e = BadSpecValue(meta=meta.at("UDP"), _errors=[e1, e2])
        with assertRaises(BadSpecValue, _errors=[e]):
            spec.normalise(meta, [56, "192.168.0.1"])

    def test_it_can_take_in_a_dictionary(self, meta, spec):
        val = {"UDP": {"host": "192.168.5.6", "port": 89}}
        res = spec.normalise(meta, val)
        assert res == {Services.UDP: {"host": "192.168.5.6", "port": 89}}

    def test_it_complains_about_incomplete_dictionaries(self, meta, spec):
        val = {"UDP": {}}
        e1 = BadSpecValue("Expected a value but got none", meta=meta.at("UDP").at("host"))
        e2 = BadSpecValue("Expected a value but got none", meta=meta.at("UDP").at("port"))
        e = BadSpecValue(meta=meta.at("UDP"), _errors=[e1, e2])
        with assertRaises(BadSpecValue, _errors=[e]):
            spec.normalise(meta, val)

class TestSerialSpec:

    @pytest.fixture()
    def spec(self):
        return do.serial_spec()

    def test_it_complains_if_the_serial_doesnt_start_with_d073d5(self, meta, spec):
        msg = "serials must start with d073d5"
        with assertRaises(BadSpecValue, msg, got="e073d5001338"):
            spec.normalise(meta, "e073d5001338")

    def test_it_complains_if_the_serial_isnt_12_characters_long(self, meta, spec):
        msg = "serials must be 12 characters long, like d073d5001337"
        with assertRaises(BadSpecValue, msg, got="d073d500133"):
            spec.normalise(meta, "d073d500133")

    def test_it_complains_if_the_serial_isnt_valid_hex(self, meta, spec):
        msg = "serials must be valid hex"
        with assertRaises(BadSpecValue, msg, got="d073d5zz1339"):
            spec.normalise(meta, "d073d5zz1339")

    def test_it_complains_if_the_serial_isnt_a_string(self, meta, spec):
        msg = "Expected a string"
        with assertRaises(BadSpecValue, msg, got=bool):
            spec.normalise(meta, True)

    def test_it_otherwise_returns_the_serial(self, meta, spec):
        assert spec.normalise(meta, "d073d5001337") == "d073d5001337"

class TestSerialFilterSpec:

    @pytest.fixture()
    def spec(self):
        return do.serial_filter_spec()

    def test_it_uses_SERIAL_FILTER_environment_variable_if_available(self, meta, spec):
        with pytest.helpers.modified_env(SERIAL_FILTER="d073d5001337"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                res = spec.normalise(meta, v)
                assert res == ["d073d5001337"]

        with pytest.helpers.modified_env(SERIAL_FILTER="d073d5001337,d073d5001338"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                res = spec.normalise(meta, v)
                assert res == ["d073d5001337", "d073d5001338"]

        with pytest.helpers.modified_env(SERIAL_FILTER="null"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                res = spec.normalise(meta, v)
                assert res is None

    def test_it_returns_sbNotSpecified_as_sbNotSpecified(self, meta, spec):
        assert spec.normalise(meta, sb.NotSpecified) is sb.NotSpecified

    def test_it_returns_None_as_None(self, meta, spec):
        assert spec.normalise(meta, None) is None

    def test_it_converts_a_string_into_a_list(self, meta, spec):
        assert spec.normalise(meta, "d073d5001337") == ["d073d5001337"]

    def test_it_understands_list_of_strings(self, meta, spec):
        assert spec.normalise(meta, ["d073d5001337", "d073d5000001"]) == [
            "d073d5001337",
            "d073d5000001",
        ]

    def test_it_complains_about_invalid_serials_in_SERIAL_FILTER(self, meta, spec):
        e = BadSpecValue(
            "serials must start with d073d5",
            got="e073d5001337",
            meta=meta.at("${SERIAL_FILTER}").indexed_at(0),
        )
        with pytest.helpers.modified_env(SERIAL_FILTER="e073d5001337"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                kwargs = {"meta": meta.at("${SERIAL_FILTER}"), "_errors": [e]}
                with assertRaises(BadSpecValue, **kwargs):
                    spec.normalise(meta, v)

    def test_it_complains_about_invalid_serials_in_value(self, meta, spec):
        e = BadSpecValue(
            "serials must start with d073d5", got="e073d5001339", meta=meta.indexed_at(0)
        )
        with assertRaises(BadSpecValue, _errors=[e]):
            spec.normalise(meta, "e073d5001339")

class TestDiscoveryOptions:
    async def test_it_has_serial_filter_and_hardcoded_discovery(self):
        with pytest.helpers.modified_env(
            HARDCODED_DISCOVERY='{"d073d5001337": "192.168.0.1"}', SERIAL_FILTER="d073d5001337"
        ):
            options = do.DiscoveryOptions.FieldSpec().empty_normalise()
            assert options.serial_filter == ["d073d5001337"]
            assert options.hardcoded_discovery == {
                "d073d5001337": {Services.UDP: {"host": "192.168.0.1", "port": 56700}}
            }

        options = do.DiscoveryOptions.FieldSpec().empty_normalise()
        assert options.serial_filter == sb.NotSpecified
        assert options.hardcoded_discovery == sb.NotSpecified

        options = do.DiscoveryOptions.FieldSpec().empty_normalise(
            serial_filter=["d073d5001338"], hardcoded_discovery={"d073d5001339": "192.178.1.1"}
        )
        assert options.serial_filter == ["d073d5001338"]
        assert options.hardcoded_discovery == {
            "d073d5001339": {Services.UDP: {"host": "192.178.1.1", "port": 56700}}
        }

    async def test_it_says_we_dont_have_hardcoded_discovery_if_thats_the_case(self):
        options = do.DiscoveryOptions.FieldSpec().empty_normalise()
        assert not options.has_hardcoded_discovery

        options = do.DiscoveryOptions.FieldSpec().empty_normalise(hardcoded_discovery=None)
        assert not options.has_hardcoded_discovery

        options = do.DiscoveryOptions.FieldSpec().empty_normalise(hardcoded_discovery={})
        assert not options.has_hardcoded_discovery

    async def test_it_says_we_have_hardcoded_discovery_if_we_do(self):
        v = {"d073d5001337": "192.168.0.1"}
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(hardcoded_discovery=v)
        assert options.has_hardcoded_discovery

    async def test_it_says_all_serials_are_wanted_if_we_dont_have_a_serial_filter(self):
        do1 = do.DiscoveryOptions.FieldSpec().empty_normalise()
        do2 = do.DiscoveryOptions.FieldSpec().empty_normalise(serial_filter=None)
        do3 = do.DiscoveryOptions.FieldSpec().empty_normalise(serial_filter=[])

        for options in (do1, do2, do3):
            assert options.want("d073d5000001")
            assert options.want("d073d5000002")
            assert options.want(mock.Mock(name="serial"))

    async def test_it_says_we_only_want_filtered_serials(self):
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(
            serial_filter=["d073d5001337", "d073d5001338"]
        )
        assert not options.want("d073d5000001")
        assert not options.want("d073d5000002")
        assert not options.want(mock.Mock(name="serial"))

        assert options.want("d073d5001337")
        assert options.want("d073d5001338")

    async def test_it_can_do_discovery(self):
        add_service = pytest.helpers.AsyncMock(name="add_service")
        v = {"d073d5000001": "192.168.9.3", "d073d5000002": ["192.168.7.8", 56]}
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(hardcoded_discovery=v)

        expected_found = set(
            [binascii.unhexlify("d073d5000001"), binascii.unhexlify("d073d5000002")]
        )
        assert await options.discover(add_service) == expected_found

        assert add_service.mock_calls == [
            mock.call("d073d5000001", Services.UDP, host="192.168.9.3", port=56700),
            mock.call("d073d5000002", Services.UDP, host="192.168.7.8", port=56),
        ]

    async def test_it_pays_attention_to_serial_filter_in_discover(self):
        add_service = pytest.helpers.AsyncMock(name="add_service")
        v = {
            "d073d5000001": "192.168.9.3",
            "d073d5000002": ["192.168.7.8", 56],
            "d073d5000003": "192.158.0.7",
        }
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(
            hardcoded_discovery=v, serial_filter=["d073d5000001", "d073d5000002"]
        )

        expected_found = set(
            [binascii.unhexlify("d073d5000001"), binascii.unhexlify("d073d5000002")]
        )
        assert await options.discover(add_service) == expected_found

        assert add_service.mock_calls == [
            mock.call("d073d5000001", Services.UDP, host="192.168.9.3", port=56700),
            mock.call("d073d5000002", Services.UDP, host="192.168.7.8", port=56),
        ]

class TestNoDiscoveryOptions:
    def test_it_overrides_serial_filter_and_hardcoded_discovery_with_None(self):
        with pytest.helpers.modified_env(
            HARDCODED_DISCOVERY='{"d073d5001337": "192.168.0.1"}', SERIAL_FILTER="d073d5001337"
        ):
            options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
            assert options.serial_filter is None
            assert options.hardcoded_discovery is None

        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
        assert options.serial_filter is None
        assert options.hardcoded_discovery is None

        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise(
            serial_filter=["d073d5001338"], hardcoded_discovery={"d073d5001339": "192.178.1.1"}
        )
        assert options.serial_filter is None
        assert options.hardcoded_discovery is None

    def test_it_says_no_hardcoded_discovery(self):
        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
        assert not options.hardcoded_discovery

    def test_it_wants_all_serials(self):
        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
        assert options.want("d073d5000001")
        assert options.want("d073d5000002")

class TestNoEnvDiscoveryOptions:
    def test_it_does_not_care_about_environment_variables(self):
        with pytest.helpers.modified_env(
            HARDCODED_DISCOVERY='{"d073d5001337": "192.168.0.1"}', SERIAL_FILTER="d073d5001337"
        ):
            options = do.NoEnvDiscoveryOptions.FieldSpec().empty_normalise()
            assert options.serial_filter == sb.NotSpecified
            assert options.hardcoded_discovery == sb.NotSpecified

            options = do.NoEnvDiscoveryOptions.FieldSpec().empty_normalise(
                serial_filter=["d073d5001338"], hardcoded_discovery={"d073d5001339": "192.178.1.1"}
            )
            assert options.serial_filter == ["d073d5001338"]
            assert options.hardcoded_discovery == {
                "d073d5001339": {Services.UDP: {"host": "192.178.1.1", "port": 56700}}
            }

            assert isinstance(options, do.DiscoveryOptions)

class TestDiscoveryOptionsSpec:

    @pytest.fixture()
    def spec(self):
        return do.discovery_options_spec()

    def test_it_creates_a_DiscoveryOptions_when_no_discovery_options_in_metaeverything(self, meta, spec):
        res = spec.normalise(meta, sb.NotSpecified)
        assert isinstance(res, do.DiscoveryOptions)

    def test_it_inherits_from_global_discovery_options(self, meta, spec):
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(
            serial_filter=["d073d5000001"], hardcoded_discovery={"d073d5000001": "192.168.0.6"}
        )
        meta.everything["discovery_options"] = options
        res = spec.normalise(meta, sb.NotSpecified)
        assert res.serial_filter == ["d073d5000001"]
        assert res.hardcoded_discovery == {
            "d073d5000001": {Services.UDP: {"host": "192.168.0.6", "port": 56700}}
        }

        # And modifying res doesn't change global
        res.serial_filter.append("d073d5000002")
        res.hardcoded_discovery["d073d5000001"][Services.UDP]["wat"] = True

        assert options.serial_filter == ["d073d5000001"]
        assert options.hardcoded_discovery == {
            "d073d5000001": {Services.UDP: {"host": "192.168.0.6", "port": 56700}}
        }

    def test_it_can_override_global_serial_filter(self, meta, spec):
        for gl in ("d073d5000001", ["d073d5000002"], None, sb.NotSpecified):
            options = do.DiscoveryOptions.FieldSpec().empty_normalise(serial_filter=gl)
            meta.everything["discovery_options"] = options

            for v in (None, [], ["d073d5000001"]):
                res = spec.normalise(meta, {"serial_filter": v})
                assert res.serial_filter == v

            # And global is not touched
            if isinstance(gl, str):
                assert options.serial_filter == [gl]
            else:
                assert options.serial_filter == gl

    def test_it_can_override_global_hardcoded_discovery(self, meta, spec):
        for gl in (None, sb.NotSpecified):
            options = do.DiscoveryOptions.FieldSpec().empty_normalise(hardcoded_discovery=gl)
            meta.everything["discovery_options"] = options

            res = spec.normalise(meta, {"hardcoded_discovery": None})
            assert res.hardcoded_discovery is None

            res = spec.normalise(meta, {"hardcoded_discovery": {"d073d5000002": "192.168.0.2"}})
            assert res.hardcoded_discovery == {
                "d073d5000002": {Services.UDP: {"host": "192.168.0.2", "port": 56700}}
            }

            res = spec.normalise(
                meta,
                {
                    "hardcoded_discovery": {
                        "d073d5000001": "192.168.0.3",
                        "d073d5000002": "192.168.0.2",
                    }
                },
            )
            assert res.hardcoded_discovery == {
                "d073d5000001": {Services.UDP: {"host": "192.168.0.3", "port": 56700}},
                "d073d5000002": {Services.UDP: {"host": "192.168.0.2", "port": 56700}},
            }

            # And global is not touched
            assert options.hardcoded_discovery == gl

    def test_it_can_add_to_global_hardcoded_discovery(self, meta, spec):
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(
            hardcoded_discovery={"d073d5000001": "192.168.0.1"}
        )
        meta.everything["discovery_options"] = options

        res = spec.normalise(meta, {"hardcoded_discovery": None})
        assert res.hardcoded_discovery is None

        res = spec.normalise(meta, {"hardcoded_discovery": {"d073d5000002": "192.168.0.2"}})
        assert res.hardcoded_discovery == {
            "d073d5000001": {Services.UDP: {"host": "192.168.0.1", "port": 56700}},
            "d073d5000002": {Services.UDP: {"host": "192.168.0.2", "port": 56700}},
        }

        res = spec.normalise(
            meta,
            {"hardcoded_discovery": {"d073d5000001": "192.168.0.3", "d073d5000002": "192.168.0.2"}},
        )
        assert res.hardcoded_discovery == {
            "d073d5000001": {Services.UDP: {"host": "192.168.0.3", "port": 56700}},
            "d073d5000002": {Services.UDP: {"host": "192.168.0.2", "port": 56700}},
        }

        assert options.hardcoded_discovery == {
            "d073d5000001": {Services.UDP: {"host": "192.168.0.1", "port": 56700}}
        }
