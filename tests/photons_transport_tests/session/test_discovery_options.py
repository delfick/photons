# coding: spec

from photons_transport.session import discovery_options as do

from photons_app.test_helpers import TestCase, AsyncTestCase, modified_env

from photons_messages import Services

from delfick_project.norms import Meta, sb, BadSpecValue
from noseOfYeti.tokeniser.support import noy_sup_setUp
from unittest import mock
import asynctest
import binascii

describe TestCase, "service_type_spec":
    before_each:
        self.meta = Meta.empty()
        self.spec = do.service_type_spec()

    it "returns as is if the value is already a Services":
        val = Services.UDP
        self.assertIs(self.spec.normalise(self.meta, val), val)

    it "returns the enum value if it matches":
        val = "UDP"
        self.assertIs(self.spec.normalise(self.meta, val), Services.UDP)

    it "complains if we don't have a match":
        msg = "Unknown service type"

        services = sorted([s.name for s in Services if not s.name.startswith("RESERVED")])
        self.assertGreater(len(services), 0)

        kwargs = dict(want="WAT", available=services)
        with self.fuzzyAssertRaisesError(BadSpecValue, msg, **kwargs):
            self.spec.normalise(self.meta, "WAT")

describe TestCase, "hardcoded_discovery_spec":
    before_each:
        self.meta = Meta.empty()
        self.spec = do.hardcoded_discovery_spec()

        self.ret = mock.Mock(name="ret")
        self.fake_spec = mock.Mock(name="fake_spec")
        self.fake_spec.normalise.return_value = self.ret

    it "uses HARDCODED_DISCOVERY environment variable if it exists":
        self.spec.spec = self.fake_spec

        with modified_env(HARDCODED_DISCOVERY='{"one": "two"}'):
            for v in (sb.NotSpecified, None, {"three": "four"}):
                self.assertIs(self.spec.normalise(self.meta, v), self.ret)
                self.fake_spec.normalise.called_once_with(self.meta, {"one": "two"})
                self.fake_spec.normalise.reset_mock()

        with modified_env(HARDCODED_DISCOVERY="null"):
            for v in (sb.NotSpecified, None, {"three": "four"}):
                self.assertIs(self.spec.normalise(self.meta, v), None)
                self.assertEqual(len(self.fake_spec.normalise.mock_calls), 0)

    it "does nothing with sb.NotSpecified":
        self.spec.spec = self.fake_spec
        self.assertIs(self.spec.normalise(self.meta, sb.NotSpecified), sb.NotSpecified)
        self.assertEqual(len(self.fake_spec.normalise.mock_calls), 0)

    it "otherwise uses self.spec":
        self.spec.spec = self.fake_spec
        val = mock.Mock(name="val")
        self.assertIs(self.spec.normalise(self.meta, val), self.ret)
        self.fake_spec.normalise.assert_called_once_with(self.meta, val)

    it "works":
        val = {
            "d073d5001337": "192.168.0.14",
            "d073d5001338": ["192.168.0.15"],
            "d073d5001339": ["192.168.0.16", 56],
            "d073d5001340": {"UDP": "192.168.0.17"},
            "d073d5001341": {"UDP": ["192.168.0.18"]},
            "d073d5001342": {"UDP": ["192.168.0.19", 78]},
            "d073d5001343": {"UDP": {"host": "192.168.0.20", "port": 90}},
        }

        res = self.spec.normalise(self.meta, val)

        self.assertEqual(
            res,
            {
                "d073d5001337": {Services.UDP: {"host": "192.168.0.14", "port": 56700}},
                "d073d5001338": {Services.UDP: {"host": "192.168.0.15", "port": 56700}},
                "d073d5001339": {Services.UDP: {"host": "192.168.0.16", "port": 56}},
                "d073d5001340": {Services.UDP: {"host": "192.168.0.17", "port": 56700}},
                "d073d5001341": {Services.UDP: {"host": "192.168.0.18", "port": 56700}},
                "d073d5001342": {Services.UDP: {"host": "192.168.0.19", "port": 78}},
                "d073d5001343": {Services.UDP: {"host": "192.168.0.20", "port": 90}},
            },
        )

    it "complains if the keys are not serials":
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
            meta=self.meta.at("d073d500133"),
        )
        e2 = BadSpecValue(
            "serials must start with d073d5", got="e073d5001338", meta=self.meta.at("e073d5001338")
        )
        e3 = BadSpecValue(
            "serials must be valid hex",
            error=S("Non-hexadecimal digit found"),
            got="d073d5zz1339",
            meta=self.meta.at("d073d5zz1339"),
        )
        e4 = BadSpecValue("Expected a string", got=bool, meta=self.meta.at(True))

        errors = [e1, e2, e3, e4]
        with self.fuzzyAssertRaisesError(BadSpecValue, _errors=errors):
            self.spec.normalise(self.meta, val)

describe TestCase, "service_info_spec":
    before_each:
        self.meta = Meta.empty()
        self.spec = do.service_info_spec()

    it "can expand a string":
        res = self.spec.normalise(self.meta, "192.168.0.1")
        self.assertEqual(res, {Services.UDP: {"host": "192.168.0.1", "port": 56700}})

    it "can expand a singe item list":
        res = self.spec.normalise(self.meta, ["192.168.0.1"])
        self.assertEqual(res, {Services.UDP: {"host": "192.168.0.1", "port": 56700}})

    it "can expand a two item list":
        res = self.spec.normalise(self.meta, ["192.168.0.1", 67])
        self.assertEqual(res, {Services.UDP: {"host": "192.168.0.1", "port": 67}})

    it "complains about other length lists":
        msg = "A list must be \[host\] or \[host, port\]"
        with self.fuzzyAssertRaisesError(BadSpecValue, msg, got=[]):
            self.spec.normalise(self.meta, [])

        with self.fuzzyAssertRaisesError(BadSpecValue, msg, got=[1, 2, 3]):
            self.spec.normalise(self.meta, [1, 2, 3])

    it "complains about lists with wrong types":
        e1 = BadSpecValue("Expected a string", got=int, meta=self.meta.at("UDP").at("host"))
        e2 = BadSpecValue("Expected an integer", got=str, meta=self.meta.at("UDP").at("port"))
        e = BadSpecValue(meta=self.meta.at("UDP"), _errors=[e1, e2])
        with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[e]):
            self.spec.normalise(self.meta, [56, "192.168.0.1"])

    it "can take in a dictionary":
        val = {"UDP": {"host": "192.168.5.6", "port": 89}}
        res = self.spec.normalise(self.meta, val)
        self.assertEqual(res, {Services.UDP: {"host": "192.168.5.6", "port": 89}})

    it "complains about incomplete dictionaries":
        val = {"UDP": {}}
        e1 = BadSpecValue("Expected a value but got none", meta=self.meta.at("UDP").at("host"))
        e2 = BadSpecValue("Expected a value but got none", meta=self.meta.at("UDP").at("port"))
        e = BadSpecValue(meta=self.meta.at("UDP"), _errors=[e1, e2])
        with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[e]):
            self.spec.normalise(self.meta, val)

describe TestCase, "serial_spec":
    before_each:
        self.meta = Meta.empty()
        self.spec = do.serial_spec()

    it "complains if the serial doesn't start with d073d5":
        msg = "serials must start with d073d5"
        with self.fuzzyAssertRaisesError(BadSpecValue, msg, got="e073d5001338"):
            self.spec.normalise(self.meta, "e073d5001338")

    it "complains if the serial isn't 12 characters long":
        msg = "serials must be 12 characters long, like d073d5001337"
        with self.fuzzyAssertRaisesError(BadSpecValue, msg, got="d073d500133"):
            self.spec.normalise(self.meta, "d073d500133")

    it "complains if the serial isn't valid hex":
        msg = "serials must be valid hex"
        with self.fuzzyAssertRaisesError(BadSpecValue, msg, got="d073d5zz1339"):
            self.spec.normalise(self.meta, "d073d5zz1339")

    it "complains if the serial isn't a string":
        msg = "Expected a string"
        with self.fuzzyAssertRaisesError(BadSpecValue, msg, got=bool):
            self.spec.normalise(self.meta, True)

    it "otherwise returns the serial":
        self.assertEqual(self.spec.normalise(self.meta, "d073d5001337"), "d073d5001337")

describe TestCase, "serial_filter_spec":
    before_each:
        self.meta = Meta.empty()
        self.spec = do.serial_filter_spec()

    it "uses SERIAL_FILTER environment variable if available":
        with modified_env(SERIAL_FILTER="d073d5001337"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                res = self.spec.normalise(self.meta, v)
                self.assertEqual(res, ["d073d5001337"])

        with modified_env(SERIAL_FILTER="d073d5001337,d073d5001338"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                res = self.spec.normalise(self.meta, v)
                self.assertEqual(res, ["d073d5001337", "d073d5001338"])

        with modified_env(SERIAL_FILTER="null"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                res = self.spec.normalise(self.meta, v)
                self.assertEqual(res, None)

    it "returns sb.NotSpecified as sb.NotSpecified":
        self.assertIs(self.spec.normalise(self.meta, sb.NotSpecified), sb.NotSpecified)

    it "returns None as None":
        self.assertIs(self.spec.normalise(self.meta, None), None)

    it "converts a string into a list":
        self.assertEqual(self.spec.normalise(self.meta, "d073d5001337"), ["d073d5001337"])

    it "understands list of strings":
        self.assertEqual(
            self.spec.normalise(self.meta, ["d073d5001337", "d073d5000001"]),
            ["d073d5001337", "d073d5000001"],
        )

    it "complains about invalid serials in SERIAL_FILTER":
        e = BadSpecValue(
            "serials must start with d073d5",
            got="e073d5001337",
            meta=self.meta.at("${SERIAL_FILTER}").indexed_at(0),
        )
        with modified_env(SERIAL_FILTER="e073d5001337"):
            for v in (sb.NotSpecified, None, ["d073d5001339"], "d073d5001340"):
                kwargs = {"meta": self.meta.at("${SERIAL_FILTER}"), "_errors": [e]}
                with self.fuzzyAssertRaisesError(BadSpecValue, **kwargs):
                    self.spec.normalise(self.meta, v)

    it "complains about invalid serials in value":
        e = BadSpecValue(
            "serials must start with d073d5", got="e073d5001339", meta=self.meta.indexed_at(0)
        )
        with self.fuzzyAssertRaisesError(BadSpecValue, _errors=[e]):
            self.spec.normalise(self.meta, "e073d5001339")

describe AsyncTestCase, "DiscoveryOptions":
    async it "has serial_filter and hardcoded_discovery":
        with modified_env(
            HARDCODED_DISCOVERY='{"d073d5001337": "192.168.0.1"}', SERIAL_FILTER="d073d5001337"
        ):
            options = do.DiscoveryOptions.FieldSpec().empty_normalise()
            self.assertEqual(options.serial_filter, ["d073d5001337"])
            self.assertEqual(
                options.hardcoded_discovery,
                {"d073d5001337": {Services.UDP: {"host": "192.168.0.1", "port": 56700}}},
            )

        options = do.DiscoveryOptions.FieldSpec().empty_normalise()
        self.assertEqual(options.serial_filter, sb.NotSpecified)
        self.assertEqual(options.hardcoded_discovery, sb.NotSpecified)

        options = do.DiscoveryOptions.FieldSpec().empty_normalise(
            serial_filter=["d073d5001338"], hardcoded_discovery={"d073d5001339": "192.178.1.1"}
        )
        self.assertEqual(options.serial_filter, ["d073d5001338"])
        self.assertEqual(
            options.hardcoded_discovery,
            {"d073d5001339": {Services.UDP: {"host": "192.178.1.1", "port": 56700}}},
        )

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
        self.assertEqual(await options.discover(add_service), expected_found)

        self.assertEqual(
            add_service.mock_calls,
            [
                mock.call("d073d5000001", Services.UDP, host="192.168.9.3", port=56700),
                mock.call("d073d5000002", Services.UDP, host="192.168.7.8", port=56),
            ],
        )

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
        self.assertEqual(await options.discover(add_service), expected_found)

        self.assertEqual(
            add_service.mock_calls,
            [
                mock.call("d073d5000001", Services.UDP, host="192.168.9.3", port=56700),
                mock.call("d073d5000002", Services.UDP, host="192.168.7.8", port=56),
            ],
        )

describe TestCase, "NoDiscoveryOptions":
    it "overrides serial_filter and hardcoded_discovery with None":
        with modified_env(
            HARDCODED_DISCOVERY='{"d073d5001337": "192.168.0.1"}', SERIAL_FILTER="d073d5001337"
        ):
            options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
            self.assertEqual(options.serial_filter, None)
            self.assertEqual(options.hardcoded_discovery, None)

        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
        self.assertEqual(options.serial_filter, None)
        self.assertEqual(options.hardcoded_discovery, None)

        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise(
            serial_filter=["d073d5001338"], hardcoded_discovery={"d073d5001339": "192.178.1.1"}
        )
        self.assertEqual(options.serial_filter, None)
        self.assertEqual(options.hardcoded_discovery, None)

    it "says no hardcoded_discovery":
        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
        assert not options.hardcoded_discovery

    it "wants all serials":
        options = do.NoDiscoveryOptions.FieldSpec().empty_normalise()
        assert options.want("d073d5000001")
        assert options.want("d073d5000002")

describe TestCase, "NoEnvDiscoveryOptions":
    it "does not care about environment variables":
        with modified_env(
            HARDCODED_DISCOVERY='{"d073d5001337": "192.168.0.1"}', SERIAL_FILTER="d073d5001337"
        ):
            options = do.NoEnvDiscoveryOptions.FieldSpec().empty_normalise()
            self.assertEqual(options.serial_filter, sb.NotSpecified)
            self.assertEqual(options.hardcoded_discovery, sb.NotSpecified)

            options = do.NoEnvDiscoveryOptions.FieldSpec().empty_normalise(
                serial_filter=["d073d5001338"], hardcoded_discovery={"d073d5001339": "192.178.1.1"}
            )
            self.assertEqual(options.serial_filter, ["d073d5001338"])
            self.assertEqual(
                options.hardcoded_discovery,
                {"d073d5001339": {Services.UDP: {"host": "192.178.1.1", "port": 56700}}},
            )

            self.assertIsInstance(options, do.DiscoveryOptions)

describe TestCase, "discovery_options_spec":
    before_each:
        self.meta = Meta.empty()
        self.spec = do.discovery_options_spec()

    it "creates a DiscoveryOptions when no discovery_options in meta.everything":
        res = self.spec.normalise(self.meta, sb.NotSpecified)
        self.assertIsInstance(res, do.DiscoveryOptions)

    it "inherits from global discovery_options":
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(
            serial_filter=["d073d5000001"], hardcoded_discovery={"d073d5000001": "192.168.0.6"}
        )
        self.meta.everything["discovery_options"] = options
        res = self.spec.normalise(self.meta, sb.NotSpecified)
        self.assertEqual(res.serial_filter, ["d073d5000001"])
        self.assertEqual(
            res.hardcoded_discovery,
            {"d073d5000001": {Services.UDP: {"host": "192.168.0.6", "port": 56700}}},
        )

        # And modifying res doesn't change global
        res.serial_filter.append("d073d5000002")
        res.hardcoded_discovery["d073d5000001"][Services.UDP]["wat"] = True

        self.assertEqual(options.serial_filter, ["d073d5000001"])
        self.assertEqual(
            options.hardcoded_discovery,
            {"d073d5000001": {Services.UDP: {"host": "192.168.0.6", "port": 56700}}},
        )

    it "can override global serial_filter":
        for gl in ("d073d5000001", ["d073d5000002"], None, sb.NotSpecified):
            options = do.DiscoveryOptions.FieldSpec().empty_normalise(serial_filter=gl)
            self.meta.everything["discovery_options"] = options

            for v in (None, [], ["d073d5000001"]):
                res = self.spec.normalise(self.meta, {"serial_filter": v})
                self.assertEqual(res.serial_filter, v)

            # And global is not touched
            if isinstance(gl, str):
                self.assertEqual(options.serial_filter, [gl])
            else:
                self.assertEqual(options.serial_filter, gl)

    it "can override global hardcoded_discovery":
        for gl in (None, sb.NotSpecified):
            options = do.DiscoveryOptions.FieldSpec().empty_normalise(hardcoded_discovery=gl)
            self.meta.everything["discovery_options"] = options

            res = self.spec.normalise(self.meta, {"hardcoded_discovery": None})
            self.assertEqual(res.hardcoded_discovery, None)

            res = self.spec.normalise(
                self.meta, {"hardcoded_discovery": {"d073d5000002": "192.168.0.2"}}
            )
            self.assertEqual(
                res.hardcoded_discovery,
                {"d073d5000002": {Services.UDP: {"host": "192.168.0.2", "port": 56700}}},
            )

            res = self.spec.normalise(
                self.meta,
                {
                    "hardcoded_discovery": {
                        "d073d5000001": "192.168.0.3",
                        "d073d5000002": "192.168.0.2",
                    }
                },
            )
            self.assertEqual(
                res.hardcoded_discovery,
                {
                    "d073d5000001": {Services.UDP: {"host": "192.168.0.3", "port": 56700}},
                    "d073d5000002": {Services.UDP: {"host": "192.168.0.2", "port": 56700}},
                },
            )

            # And global is not touched
            self.assertEqual(options.hardcoded_discovery, gl)

    it "can add to global hardcoded_discovery":
        options = do.DiscoveryOptions.FieldSpec().empty_normalise(
            hardcoded_discovery={"d073d5000001": "192.168.0.1"}
        )
        self.meta.everything["discovery_options"] = options

        res = self.spec.normalise(self.meta, {"hardcoded_discovery": None})
        self.assertEqual(res.hardcoded_discovery, None)

        res = self.spec.normalise(
            self.meta, {"hardcoded_discovery": {"d073d5000002": "192.168.0.2"}}
        )
        self.assertEqual(
            res.hardcoded_discovery,
            {
                "d073d5000001": {Services.UDP: {"host": "192.168.0.1", "port": 56700}},
                "d073d5000002": {Services.UDP: {"host": "192.168.0.2", "port": 56700}},
            },
        )

        res = self.spec.normalise(
            self.meta,
            {"hardcoded_discovery": {"d073d5000001": "192.168.0.3", "d073d5000002": "192.168.0.2"}},
        )
        self.assertEqual(
            res.hardcoded_discovery,
            {
                "d073d5000001": {Services.UDP: {"host": "192.168.0.3", "port": 56700}},
                "d073d5000002": {Services.UDP: {"host": "192.168.0.2", "port": 56700}},
            },
        )

        self.assertEqual(
            options.hardcoded_discovery,
            {"d073d5000001": {Services.UDP: {"host": "192.168.0.1", "port": 56700}}},
        )
