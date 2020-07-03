# coding: spec

from interactor.database.models import scene_spec

from photons_app.test_helpers import print_packet_difference
from photons_app import helpers as hp

from photons_messages import LightMessages, MultiZoneMessages, TileMessages

from delfick_project.norms import dictobj, sb, Meta, BadSpecValue
from delfick_project.errors_pytest import assertRaises
from unittest import mock
import random
import pytest
import json
import uuid


@pytest.fixture()
def meta():
    return Meta.empty()


@pytest.fixture()
def overrides():
    return mock.Mock(name="overrides")


describe "range_spec":
    it "complains if the value isn't a float", meta:
        for val in (True, False, {}, [], None, lambda: 1):
            with assertRaises(BadSpecValue):
                scene_spec.range_spec(0, 1).normalise(meta, val)

    it "can use the spec that is provided", meta:
        got = scene_spec.range_spec(0, 1, sb.integer_spec()).normalise(meta, 0)
        assert got == 0
        assert type(got) == int

        # Prove it's not an integer without specifying integer_spec
        got = scene_spec.range_spec(0, 1).normalise(meta, 0)
        assert got == 0.0
        assert type(got) == float

    it "complains if less than minimum", meta:
        for val in (-1.0, -2.0, -3.0):
            with assertRaises(
                BadSpecValue,
                "Number must be between min and max",
                minimum=0,
                maximum=1,
                got=val,
                meta=meta,
            ):
                scene_spec.range_spec(0, 1).normalise(meta, val)

    it "complains if greater than maximum", meta:
        for val in (1.1, 2.0, 3.0):
            with assertRaises(
                BadSpecValue,
                "Number must be between min and max",
                minimum=0,
                maximum=1,
                got=val,
                meta=meta,
            ):
                scene_spec.range_spec(0, 1).normalise(meta, val)

    it "works if number is between min and max", meta:
        for val in (0.1, 0.5, 0.9):
            assert scene_spec.range_spec(0, 1).normalise(meta, val) == val

describe "sized_list_spec":
    it "complains if not matching the spec", meta:
        val = [1, 2, None]
        spec = scene_spec.sized_list_spec(sb.integer_spec(), 4)
        with assertRaises(BadSpecValue):
            spec.normalise(meta, val)

    it "complains if list is not the correct length", meta:
        spec = scene_spec.sized_list_spec(sb.integer_spec(), 2)
        with assertRaises(BadSpecValue, "Expected certain number of parts", want=2, got=1):
            spec.normalise(meta, 1)

        with assertRaises(BadSpecValue, "Expected certain number of parts", want=2, got=1):
            spec.normalise(meta, [1])

        with assertRaises(BadSpecValue, "Expected certain number of parts", want=2, got=3):
            spec.normalise(meta, [1, 2, 3])

    it "returns the list if correct length", meta:
        spec = scene_spec.sized_list_spec(sb.string_spec(), 1)

        got = spec.normalise(meta, "one")
        assert got == ["one"]

        got = spec.normalise(meta, ["one"])
        assert got == ["one"]

        spec = scene_spec.sized_list_spec(sb.string_spec(), 2)
        got = spec.normalise(meta, ["one", "two"])
        assert got == ["one", "two"]

describe "hsbk":
    it "expects 4 items", meta:
        spec = scene_spec.hsbk()

        val = [200, 1, 1, 3500]
        assert spec.normalise(meta, val) == val

    it "complains if hue is outside 0 and 360", meta:
        spec = scene_spec.hsbk()

        with assertRaises(
            BadSpecValue, "Number must be between min and max", minimum=0, maximum=360
        ):
            spec.normalise(meta, [-1, 1, 1, 3500])

        with assertRaises(
            BadSpecValue, "Number must be between min and max", minimum=0, maximum=360
        ):
            spec.normalise(meta, [361, 1, 1, 3500])

    it "complains if saturation is outside 0 and 1", meta:
        spec = scene_spec.hsbk()

        with assertRaises(BadSpecValue, "Number must be between min and max", minimum=0, maximum=1):
            spec.normalise(meta, [1, -0.1, 1, 3500])

        with assertRaises(BadSpecValue, "Number must be between min and max", minimum=0, maximum=1):
            spec.normalise(meta, [360, 1.1, 1, 3500])

    it "complains if brightness is outside 0 and 1", meta:
        spec = scene_spec.hsbk()

        with assertRaises(BadSpecValue, "Number must be between min and max", minimum=0, maximum=1):
            spec.normalise(meta, [1, 0, -0.1, 3500])

        with assertRaises(BadSpecValue, "Number must be between min and max", minimum=0, maximum=1):
            spec.normalise(meta, [360, 1, 1.1, 3500])

    it "complains if kelvin is outside 2500 and 9000", meta:
        spec = scene_spec.hsbk()

        with assertRaises(
            BadSpecValue, "Number must be between min and max", minimum=2500, maximum=9000
        ):
            spec.normalise(meta, [1, 0, 0, 2499])

        with assertRaises(
            BadSpecValue, "Number must be between min and max", minimum=2500, maximum=9000
        ):
            spec.normalise(meta, [360, 1, 1, 9001])

describe "chain_spec":
    it "complains if list is not 64", meta:
        chain = []
        for i in range(63):
            chain.append([0, 0, 0, 2500])

        spec = scene_spec.chain_spec
        with assertRaises(BadSpecValue, "Expected certain number of parts", want=64, got=63):
            spec.normalise(meta, chain)

        chain.extend([[0, 0, 0, 2500], [1, 1, 1, 9000]])
        with assertRaises(BadSpecValue, "Expected certain number of parts", want=64, got=65):
            spec.normalise(meta, chain)

describe "json_string_spec":
    describe "storing":
        it "loads if the val is a string and returns as dumps", meta:
            spec = sb.set_options(one=sb.integer_spec())
            spec = scene_spec.json_string_spec(spec, True)
            got = spec.normalise(meta, '{"one": 2, "two": 3}')
            assert got == '{"one": 2}'

        it "doesn't loads if not a string and returns as dumps", meta:
            spec = sb.set_options(one=sb.integer_spec())
            spec = scene_spec.json_string_spec(spec, True)
            got = spec.normalise(meta, {"one": 2, "two": 3})
            assert got == '{"one": 2}'

        it "complains if string is not valid json", meta:
            spec = sb.set_options(one=sb.integer_spec())
            spec = scene_spec.json_string_spec(spec, True)
            with assertRaises(BadSpecValue, "Value was not valid json"):
                spec.normalise(meta, "{")

        it "complains if we don't match our spec", meta:
            spec = sb.set_options(one=sb.required(sb.integer_spec()))
            spec = scene_spec.json_string_spec(spec, True)
            with assertRaises(BadSpecValue):
                spec.normalise(meta, '{"two": 3}')

    describe "not storing":
        it "loads if the val is a string", meta:
            spec = sb.set_options(one=sb.integer_spec())
            spec = scene_spec.json_string_spec(spec, False)
            got = spec.normalise(meta, '{"one": 2, "two": 3}')
            assert got == {"one": 2}

        it "doesn't loads if not a string", meta:
            spec = sb.set_options(one=sb.integer_spec())
            spec = scene_spec.json_string_spec(spec, False)
            got = spec.normalise(meta, {"one": 2, "two": 3})
            assert got == {"one": 2}

        it "complains if we don't match our spec", meta:
            spec = sb.set_options(one=sb.required(sb.integer_spec()))
            spec = scene_spec.json_string_spec(spec, False)
            with assertRaises(BadSpecValue):
                spec.normalise(meta, {"two": 3})

describe "make_spec":
    describe "storing":
        it "has nullable fields for everything but uuid and matcher", meta:
            spec = scene_spec.make_spec(storing=True)
            obj = spec.normalise(meta, {"uuid": "one", "matcher": {"label": "kitchen"}})
            assert obj.as_dict() == {
                "uuid": "one",
                "matcher": '{"label": "kitchen"}',
                "power": None,
                "color": None,
                "zones": None,
                "chain": None,
                "duration": None,
            }

            with assertRaises(BadSpecValue):
                obj = spec.normalise(meta, {"uuid": "one"})

            with assertRaises(BadSpecValue):
                obj = spec.normalise(meta, {"matcher": {"label": "kitchen"}})

        it "makes a class with no extra methods and makes json into text", meta:
            zones = []
            for i in range(10):
                zones.append([float(i), 1.0, 0.0, 3500])

            chain = []
            for i in range(5):
                tile = []
                for j in range(64):
                    tile.append([float(j), 0.0, 1.0, 2500])
                chain.append(tile)

            spec = scene_spec.make_spec(storing=True)
            identifier = str(uuid.uuid1())

            obj = spec.normalise(
                meta,
                {
                    "uuid": identifier,
                    "matcher": {"label": "den"},
                    "power": True,
                    "color": "red",
                    "zones": zones,
                    "chain": chain,
                    "duration": 1,
                },
            )

            class base(dictobj.Spec):
                pass

            got = dir(obj)
            diff = set(got) - set(dir(base()))
            assert diff == set(["uuid", "matcher", "power", "color", "zones", "chain", "duration"])

            assert obj.as_dict() == {
                "uuid": identifier,
                "matcher": '{"label": "den"}',
                "power": True,
                "color": "red",
                "zones": json.dumps(zones),
                "chain": json.dumps(chain),
                "duration": 1,
            }

    describe "not storing":

        @pytest.fixture()
        def V(self, meta):
            class V:
                spec = scene_spec.make_spec(storing=False)
                identifier = str(uuid.uuid1())

                @hp.memoized_property
                def zones(s):
                    zones = []
                    for i in range(10):
                        zones.append([float(i), 1.0, 0.0, 3500])
                    return zones

                @hp.memoized_property
                def chain(s):
                    chain = []
                    for i in range(5):
                        tile = []
                        for j in range(64):
                            tile.append([float(j), 0.0, 1.0, 2500])
                        chain.append(tile)
                    return chain

                @hp.memoized_property
                def kwargs(s):
                    return {
                        "uuid": s.identifier,
                        "matcher": {"label": "den"},
                        "power": True,
                        "color": "red",
                        "zones": s.zones,
                        "chain": s.chain,
                        "duration": 1,
                    }

                @hp.memoized_property
                def obj(s):
                    return s.spec.normalise(meta, s.kwargs)

                def assertCorrect(s, zones, *want):
                    power_message = mock.Mock(name="power_message", return_value=None)

                    colors = s.obj.colors_from_hsbks(zones, {})
                    colors_from_hsbks = mock.Mock(name="colors_from_hsbks", return_value=colors)

                    determine_duration = mock.Mock(name="determine_duration", return_value=1)

                    with mock.patch.multiple(
                        s.obj,
                        power_message=power_message,
                        colors_from_hsbks=colors_from_hsbks,
                        determine_duration=determine_duration,
                    ):
                        msgs = list(s.obj.zone_msgs(overrides))

                    if msgs != want:
                        for i, (w, m) in enumerate(zip(want, msgs)):
                            if w != m:
                                print(f"Message {i}:")
                                print_packet_difference(w, m)

                    assert len(want) == len(msgs)
                    assert list(want) == msgs

                    power_message.assert_called_once_with(overrides)
                    colors_from_hsbks.assert_called_once_with(s.obj.zones, overrides)
                    determine_duration.assert_called_once_with(overrides)

            return V()

        it "has nullable fields for everything but uuid and matcher", meta:
            spec = scene_spec.make_spec(storing=False)
            obj = spec.normalise(meta, {"uuid": "one", "matcher": {"label": "kitchen"}})
            assert obj.as_dict() == {
                "uuid": "one",
                "matcher": {"label": "kitchen"},
                "power": None,
                "color": None,
                "zones": None,
                "chain": None,
                "duration": None,
            }

            with assertRaises(BadSpecValue):
                obj = spec.normalise(meta, {"uuid": "one"})

            with assertRaises(BadSpecValue):
                obj = spec.normalise(meta, {"matcher": {"label": "kitchen"}})

        it "does not store as text", V:
            for key, val in V.kwargs.items():
                assert getattr(V.obj, key) == val

        describe "transform_options":
            it "takes into account power, color and duration", V:
                assert V.obj.transform_options == {"power": "on", "color": "red", "duration": 1}

                V.obj.power = False
                assert V.obj.transform_options == {"power": "off", "color": "red", "duration": 1}

                V.obj.color = None
                assert V.obj.transform_options == {"power": "off", "duration": 1}

                V.obj.duration = None
                assert V.obj.transform_options == {"power": "off"}

                V.obj.power = None
                assert V.obj.transform_options == {}

        describe "colors_from_hsbks":
            it "takes uses hsbks if no overrides", V:
                hsbks = []
                result = []
                for i in range(10):
                    hue = random.randrange(0, 360)
                    saturation = random.randrange(0, 10) / 10
                    brightness = random.randrange(0, 10) / 10
                    kelvin = random.randrange(2500, 9000)

                    hsbks.append([hue, saturation, brightness, kelvin])
                    result.append(
                        {
                            "hue": hue,
                            "saturation": saturation,
                            "brightness": brightness,
                            "kelvin": kelvin,
                        }
                    )

                    assert V.obj.colors_from_hsbks(hsbks, {}) == result

            it "takes overrides from overrides", V:
                h = mock.Mock(name="hue")
                s = mock.Mock(name="saturation")
                b = mock.Mock(name="brightness")
                k = mock.Mock(name="kelvin")

                o1 = {"hue": h}
                o2 = {"saturation": s}
                o3 = {"brightness": b}
                o4 = {"kelvin": k}
                o5 = {"hue": h, "saturation": s}
                o6 = {"brightness": b, "kelvin": k}

                for overrides in (o1, o2, o3, o4, o5, o6):
                    hsbks = []
                    result = []
                    for i in range(10):
                        hue = random.randrange(0, 360)
                        saturation = random.randrange(0, 10) / 10
                        brightness = random.randrange(0, 10) / 10
                        kelvin = random.randrange(2500, 9000)

                        hsbks.append([hue, saturation, brightness, kelvin])
                        want = {
                            "hue": hue,
                            "saturation": saturation,
                            "brightness": brightness,
                            "kelvin": kelvin,
                        }
                        want.update(overrides)
                        result.append(want)

                    assert V.obj.colors_from_hsbks(hsbks, overrides) == result

        describe "power_message":
            it "does not provide SetLightPower if we have no power", V:
                V.obj.power = None
                msg = V.obj.power_message({})
                assert msg is None

            it "provides power if in overrides", V:
                V.obj.power = None
                V.obj.duration = None

                msg = V.obj.power_message({"power": "on"})
                assert msg == LightMessages.SetLightPower(level=65535, duration=0)

                msg = V.obj.power_message({"power": True})
                assert msg == LightMessages.SetLightPower(level=65535, duration=0)

                msg = V.obj.power_message({"power": False})
                assert msg == LightMessages.SetLightPower(level=0, duration=0)

                msg = V.obj.power_message({"power": "off"})
                assert msg == LightMessages.SetLightPower(level=0, duration=0)

                V.obj.duration = 2
                msg = V.obj.power_message({"power": "off"})
                assert msg == LightMessages.SetLightPower(level=0, duration=2)

            it "provides power if on the object", V:
                V.obj.power = True
                V.obj.duration = 3

                msg = V.obj.power_message({})
                assert msg == LightMessages.SetLightPower(level=65535, duration=3)

                V.obj.power = False
                msg = V.obj.power_message({})
                assert msg == LightMessages.SetLightPower(level=0, duration=3)

        describe "zone_msgs":
            it "yields power message if we have one", V, overrides:
                msg = mock.Mock(name="msg")
                power_message = mock.Mock(name="power_message", return_value=msg)

                with mock.patch.object(V.obj, "power_message", power_message):
                    itr = iter(V.obj.zone_msgs(overrides))
                    m = next(itr)
                    assert m is msg

                power_message.assert_called_once_with(overrides)

            it "does not yield power message if we don't have one", V, overrides:
                power_message = mock.Mock(name="power_message", return_value=None)
                colors = V.obj.colors_from_hsbks(V.obj.zones, {})
                colors_from_hsbks = mock.Mock(name="colors_from_hsbks", return_value=colors)
                determine_duration = mock.Mock(name="determine_duration", return_value=1)

                with mock.patch.multiple(
                    V.obj,
                    power_message=power_message,
                    colors_from_hsbks=colors_from_hsbks,
                    determine_duration=determine_duration,
                ):
                    itr = iter(V.obj.zone_msgs(overrides))
                    m = next(itr)
                    assert type(m) is MultiZoneMessages.SetColorZones

                power_message.assert_called_once_with(overrides)
                colors_from_hsbks.assert_called_once_with(V.obj.zones, overrides)
                determine_duration.assert_called_once_with(overrides)

            describe "Yielding SetMultiZoneColorZones messages":

                @pytest.fixture()
                def setter(self):
                    def setter(h, s, b, k, **kwargs):
                        return MultiZoneMessages.SetColorZones(
                            hue=h,
                            saturation=s,
                            brightness=b,
                            kelvin=k,
                            res_required=False,
                            **kwargs,
                        )

                    return setter

            it "works", V, setter:
                zones = [
                    [0, 0, 0, 3500],
                    [0, 0, 0, 3500],
                    [0, 0, 0, 3500],
                    [100, 1, 0, 3500],
                    [100, 0.5, 0, 3500],
                    [100, 0.5, 0, 3500],
                    [100, 0.5, 1, 3500],
                    [100, 0.5, 1, 9000],
                    [100, 0.5, 1, 9000],
                ]

                V.assertCorrect(
                    zones,
                    setter(0, 0, 0, 3500, start_index=0, end_index=2, duration=1),
                    setter(100, 1, 0, 3500, start_index=3, end_index=3, duration=1),
                    setter(100, 0.5, 0, 3500, start_index=4, end_index=5, duration=1),
                    setter(100, 0.5, 1, 3500, start_index=6, end_index=6, duration=1),
                    setter(100, 0.5, 1, 9000, start_index=7, end_index=8, duration=1),
                )

            it "works2", V, setter:
                zones = [
                    [0, 0, 0, 3500],
                    [100, 1, 0, 3500],
                    [100, 0.5, 0, 3500],
                    [100, 0.5, 0, 3500],
                    [100, 0.5, 1, 3500],
                    [100, 0.5, 1, 9000],
                ]

                V.assertCorrect(
                    zones,
                    setter(0, 0, 0, 3500, start_index=0, end_index=0, duration=1),
                    setter(100, 1, 0, 3500, start_index=1, end_index=1, duration=1),
                    setter(100, 0.5, 0, 3500, start_index=2, end_index=3, duration=1),
                    setter(100, 0.5, 1, 3500, start_index=4, end_index=4, duration=1),
                    setter(100, 0.5, 1, 9000, start_index=5, end_index=5, duration=1),
                )

        describe "chain_msgs":
            it "yields power message if we have one", V, overrides:
                msg = mock.Mock(name="msg")
                power_message = mock.Mock(name="power_message", return_value=msg)

                with mock.patch.object(V.obj, "power_message", power_message):
                    itr = iter(V.obj.chain_msgs(overrides))
                    m = next(itr)
                    assert m is msg

                power_message.assert_called_once_with(overrides)

            it "does not yield power message if we don't have one", V, overrides:
                power_message = mock.Mock(name="power_message", return_value=None)
                colors = V.obj.colors_from_hsbks(V.obj.zones, {})
                colors_from_hsbks = mock.Mock(name="colors_from_hsbks", return_value=colors)
                determine_duration = mock.Mock(name="determine_duration", return_value=1)

                with mock.patch.multiple(
                    V.obj,
                    power_message=power_message,
                    colors_from_hsbks=colors_from_hsbks,
                    determine_duration=determine_duration,
                ):
                    itr = iter(V.obj.chain_msgs(overrides))
                    m = next(itr)
                    assert type(m) is TileMessages.Set64

                power_message.assert_called_once_with(overrides)
                colors_from_hsbks.assert_called_once_with(V.obj.chain[0], overrides)
                determine_duration.assert_called_once_with(overrides)

            describe "yielding Set64 messages":

                @pytest.fixture()
                def setter(self):
                    def setter(**kwargs):
                        return TileMessages.Set64(
                            length=1, x=0, y=0, width=8, res_required=False, **kwargs
                        )

                    return setter

                it "works", V, setter, overrides:
                    power_message = mock.Mock(name="power_message", return_value=None)

                    original = V.obj.colors_from_hsbks
                    returned = [original(c, {}) for c in V.obj.chain]

                    def colors_from_hsbks(c, o):
                        assert o is overrides
                        return original(c, {})

                    colors_from_hsbks = mock.Mock(
                        name="colors_from_hsbks", side_effect=colors_from_hsbks
                    )

                    determine_duration = mock.Mock(name="determine_duration", return_value=1)

                    with mock.patch.multiple(
                        V.obj,
                        power_message=power_message,
                        colors_from_hsbks=colors_from_hsbks,
                        determine_duration=determine_duration,
                    ):
                        msgs = list(V.obj.chain_msgs(overrides))

                    want = [
                        setter(tile_index=0, duration=1, colors=returned[0]),
                        setter(tile_index=1, duration=1, colors=returned[1]),
                        setter(tile_index=2, duration=1, colors=returned[2]),
                        setter(tile_index=3, duration=1, colors=returned[3]),
                        setter(tile_index=4, duration=1, colors=returned[4]),
                    ]

                    if msgs != want:
                        for i, (w, m) in enumerate(zip(want, msgs)):
                            if w != m:
                                print(f"Message {i}:")
                                print_packet_difference(w, m)

                    assert len(want) == len(msgs)
                    assert list(want) == msgs

                    power_message.assert_called_once_with(overrides)
                    determine_duration.assert_called_once_with(overrides)

                    assert colors_from_hsbks.mock_calls == [
                        mock.call(V.obj.chain[0], overrides),
                        mock.call(V.obj.chain[1], overrides),
                        mock.call(V.obj.chain[2], overrides),
                        mock.call(V.obj.chain[3], overrides),
                        mock.call(V.obj.chain[4], overrides),
                    ]
