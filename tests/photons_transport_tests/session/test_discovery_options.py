# coding: spec

from photons_transport.session import discovery_options as do

from photons_app.test_helpers import modified_env

from photons_messages import Services

from delfick_project.norms import Meta, sb, BadSpecValue
from delfick_project.errors_pytest import assertRaises
from unittest import mock
import asynctest
import binascii
import pytest


@pytest.fixture()
def meta():
    return Meta.empty()


describe "service_type_spec":

    @pytest.fixture()
    def spec(self):
        return do.service_type_spec()

    it "returns as is if the value is already a Services", meta, spec:
        val = Services.UDP
        assert spec.normalise(meta, val) is val

    it "returns the enum value if it matches", meta, spec:
        val = "UDP"
        assert spec.normalise(meta, val) is Services.UDP

    it "complains if we don't have a match", meta, spec:
        msg = "Unknown service type"

        services = sorted([s.name for s in Services if not s.name.startswith("RESERVED")])
        assert len(services) > 0

        kwargs = dict(want="WAT", available=services)
        with assertRaises(BadSpecValue, msg, **kwargs):
            spec.normalise(meta, "WAT")

describe "hardcoded_discovery_spec":

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

    it "uses HARDCODED_DISCOVERY environment variable if it exists", meta, spec, ret, fake_spec:
        spec.spec = fake_spec

        with modified_env(HARDCODED_DISCOVERY='{"one": "two"}'):
            for v in (sb.NotSpecified, None, {"three": "four"}):
                assert spec.normalise(meta, v) is ret
                fake_spec.normalise.called_once_with(meta, {"one": "two"})
                fake_spec.normalise.reset_mock()

        with modified_env(HARDCODED_DISCOVERY="null"):
            for v in (sb.NotSpecified, None, {"three": "four"}):
                assert spec.normalise(meta, v) is None
                assert len(fake_spec.normalise.mock_calls) == 0

    it "does nothing with sb.NotSpecified", meta, spec, fake_spec:
        spec.spec = fake_spec
        assert spec.normalise(meta, sb.NotSpecified) is sb.NotSpecified
        assert len(fake_spec.normalise.mock_calls) == 0

    it "otherwise uses spec", meta, spec, ret, fake_spec:
        spec.spec = fake_spec
        val = mock.Mock(name="val")
        assert spec.normalise(meta, val) is ret
        fake_spec.normalise.assert_called_once_with(meta, val)

    it "works", meta, spec:
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

    it "complains if the keys are not serials", meta, spec:
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

describe "service_info_spec":

    @pytest.fixture()
    def spec(self):
        return do.service_info_spec()

    it "can expand a string", meta, spec:
        res = spec.normalise(meta, "192.168.0.1")
        assert res == {Services.UDP: {"host": "192.168.0.1", "port": 56700}}

    it "can expand a singe item list", meta, spec:
        res = spec.normalise(meta, ["192.168.0.1"])
        assert res == {Services.UDP: {"host": "192.168.0.1", "port": 56700}}

    it "can expand a two item list", meta, spec:
        res = spec.normalise(meta, ["192.168.0.1", 67])
        assert res == {Services.UDP: {"host": "192.168.0.1", "port": 67}}

    it "complains about other length lists", meta, spec:
        msg = r"A list must be \[host\] or \[host, port\]"
        with assertRaises(BadSpecValue, msg, got=[]):
            spec.normalise(meta, [])

        with assertRaises(BadSpecValue, msg, got=[1, 2, 3]):
            spec.normalise(meta, [1, 2, 3])

    it "complains about lists with wrong types", meta, spec:
        e1 = BadSpecValue("Expected a string", got=int, meta=meta.at("UDP").at("host"))
        e2 = BadSpecValue("Expected an integer", got=str, meta=meta.at("UDP").at("port"))
        e = BadSpecValue(meta=meta.at("UDP"), _errors=[e1, e2])
        with assertRaises(BadSpecValue, _errors=[e]):
            spec.normalise(meta, [56, "192.168.0.1"])

    it "can take in a dictionary", meta, spec:
        val = {"UDP": {"host": "192.168.5.6", "port": 89}}
        res = spec.normalise(meta, val)
        assert res == {Services.UDP: {"host": "192.168.5.6", "port": 89}}

    it "complains about incomplete dictionaries", meta, spec:
        val = {"UDP": {}}
        e1 = BadSpecValue("Expected a value but got none", meta=meta.at("UDP").at("host"))
        e2 = BadSpecValue("Expected a value but got none", meta=meta.at("UDP").at("port"))
        e = BadSpecValue(meta=meta.at("UDP"), _errors=[e1, e2])
        with assertRaises(BadSpecValue, _errors=[e]):
            spec.normalise(meta, val)

describe "serial_spec":

    @pytest.fixture()
    def spec(self):
        return do.serial_spec()

    it "complains if the serial doesn't start with d073d5", meta, spec:
        msg = "serials must start with d073d5"
        with assertRaises(BadSpecValue, msg, got="e073d5001338"):
            spec.normalise(meta, "e073d5001338")

    it "complains if the serial isn't 12 characters long", meta, spec:
        msg = "serials must be 12 characters long, like d073d5001337"
        with assertRaises(BadSpecValue, msg, got="d073d500133"):
            spec.normalise(meta, "d073d500133")

    it "complains if the serial isn't valid hex", meta, spec:
        msg = "serials must be valid hex"
        with assertRaises(BadSpecValue, msg, got="d073d5zz1339"):
            spec.normalise(meta, "d073d5zz1339")

    it "complains if the serial isn't a string", meta, spec:
        msg = "Expected a string"
        with assertRaises(BadSpecValue, msg, got=bool):
            spec.normalise(meta, True)

    it "otherwise returns the serial", meta, spec:
        assert spec.normalise(meta, "d073d5001337") == "d073d5001337"

describe "serial_filter_spec":

    @pytest.fixture()
    def spec(self):
        return do.serial_filter_spec()

    it "uses SERIAL_FILTER environment variable if available", meta, spec:
        with modified_env(SERIAL_FILTER="d073d5001337"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                res = spec.normalise(meta, v)
                assert res == ["d073d5001337"]

        with modified_env(SERIAL_FILTER="d073d5001337,d073d5001338"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                res = spec.normalise(meta, v)
                assert res == ["d073d5001337", "d073d5001338"]

        with modified_env(SERIAL_FILTER="null"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                res = spec.normalise(meta, v)
                assert res == None

    it "returns sb.NotSpecified as sb.NotSpecified", meta, spec:
        assert spec.normalise(meta, sb.NotSpecified) is sb.NotSpecified

    it "returns None as None", meta, spec:
        assert spec.normalise(meta, None) is None

    it "converts a string into a list", meta, spec:
        assert spec.normalise(meta, "d073d5001337") == ["d073d5001337"]

    it "understands list of strings", meta, spec:
        assert spec.normalise(meta, ["d073d5001337", "d073d5000001"]) == [
            "d073d5001337",
            "d073d5000001",
        ]

    it "complains about invalid serials in SERIAL_FILTER", meta, spec:
        e = BadSpecValue(
            "serials must start with d073d5",
            got="e073d5001337",
            meta=meta.at("${SERIAL_FILTER}").indexed_at(0),
        )
        with modified_env(SERIAL_FILTER="e073d5001337"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                kwargs = {"meta": meta.at("${SERIAL_FILTER}"), "_errors": [e]}
                with assertRaises(BadSpecValue, **kwargs):
                    spec.normalise(meta, v)

    it "complains about invalid serials in value", meta, spec:
        e = BadSpecValue(
            "serials must start with d073d5", got="e073d5001339", meta=meta.indexed_at(0)
        )
        with assertRaises(BadSpecValue, _errors=[e]):
            spec.normalise(meta, "e073d5001339")

describe "DiscoveryOptions":
    async it "has serial_filter and hardcoded_discovery":
        with modified_env(
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

    async it "says we don't have hardcoded_discovery if that's the case":
        options = do.DiscoveryOptions.FieldSpec().empty_normalise()
        assert not options.has_hardcoded_discovery

        options = do.DiscoveryOptions.FieldSpec().empty_normalise(hardcoded_discovery=None)
        assert not options.has_hardcoded_discovery

        options = do.DiscoveryOptions.FieldSpec().empty_normalise(hardcoded_discovery={})
        assert not options.has_hardcoded_discovery

    async it "says we have hardcoded_discovery if we do":
        v = {"d073d5001337": "192.168.0.1"}
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(hardcoded_discovery=v)
        assert options.has_hardcoded_discovery

    async it "says all serials are wanted if we don't have a serial_filter":
        do1 = do.DiscoveryOptions.FieldSpec().empty_normalise()
        do2 = do.DiscoveryOptions.FieldSpec().empty_normalise(serial_filter=None)
        do3 = do.DiscoveryOptions.FieldSpec().empty_normalise(serial_filter=[])

        for options in (do1, do2, do3):
            assert options.want("d073d5000001")
            assert options.want("d073d5000002")
            assert options.want(mock.Mock(name="serial"))

    async it "says we only want filtered serials":
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(
            serial_filter=["d073d5001337", "d073d5001338"]
        )
        assert not options.want("d073d5000001")
        assert not options.want("d073d5000002")
        assert not options.want(mock.Mock(name="serial"))

        assert options.want("d073d5001337")
        assert options.want("d073d5001338")

    async it "can do discovery":
        add_service = asynctest.mock.CoroutineMock(name="add_service")
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

    async it "pays attention to serial_filter in discover":
        add_service = asynctest.mock.CoroutineMock(name="add_service")
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

describe "NoDiscoveryOptions":
    it "overrides serial_filter and hardcoded_discovery with None":
        with modified_env(
            HARDCODED_DISCOVERY='{"d073d5001337": "192.168.0.1"}', SERIAL_FILTER="d073d5001337"
        ):
            options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
            assert options.serial_filter == None
            assert options.hardcoded_discovery == None

        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
        assert options.serial_filter == None
        assert options.hardcoded_discovery == None

        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise(
            serial_filter=["d073d5001338"], hardcoded_discovery={"d073d5001339": "192.178.1.1"}
        )
        assert options.serial_filter == None
        assert options.hardcoded_discovery == None

    it "says no hardcoded_discovery":
        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
        assert not options.hardcoded_discovery

    it "wants all serials":
        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
        assert options.want("d073d5000001")
        assert options.want("d073d5000002")

describe "NoEnvDiscoveryOptions":
    it "does not care about environment variables":
        with modified_env(
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

describe "discovery_options_spec":

    @pytest.fixture()
    def spec(self):
        return do.discovery_options_spec()

    it "creates a DiscoveryOptions when no discovery_options in meta.everything", meta, spec:
        res = spec.normalise(meta, sb.NotSpecified)
        assert isinstance(res, do.DiscoveryOptions)

    it "inherits from global discovery_options", meta, spec:
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

    it "can override global serial_filter", meta, spec:
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

    it "can override global hardcoded_discovery", meta, spec:
        for gl in (None, sb.NotSpecified):
            options = do.DiscoveryOptions.FieldSpec().empty_normalise(hardcoded_discovery=gl)
            meta.everything["discovery_options"] = options

            res = spec.normalise(meta, {"hardcoded_discovery": None})
            assert res.hardcoded_discovery == None

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

    it "can add to global hardcoded_discovery", meta, spec:
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(
            hardcoded_discovery={"d073d5000001": "192.168.0.1"}
        )
        meta.everything["discovery_options"] = options

        res = spec.normalise(meta, {"hardcoded_discovery": None})
        assert res.hardcoded_discovery == None

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
