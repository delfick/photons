import json
import random
import uuid
from unittest import mock

import pytest
from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import BadSpecValue, Meta, dictobj, sb
from interactor.database.models import scene_spec
from photons_app import helpers as hp
from photons_messages import LightMessages, MultiZoneMessages, TileMessages


@pytest.fixture()
def meta():
    return Meta.empty()


@pytest.fixture()
def overrides():
    return mock.Mock(name="overrides")


class TestRangeSpec:
    def test_it_complains_if_the_value_isnt_a_float(self, meta):
        for val in (True, False, {}, [], None, lambda: 1):
            with assertRaises(BadSpecValue):
                scene_spec.range_spec(0, 1).normalise(meta, val)

    def test_it_can_use_the_spec_that_is_provided(self, meta):
        got = scene_spec.range_spec(0, 1, sb.integer_spec()).normalise(meta, 0)
        assert got == 0
        assert type(got) == int

        # Prove it's not an integer without specifying integer_spec
        got = scene_spec.range_spec(0, 1).normalise(meta, 0)
        assert got == 0.0
        assert type(got) == float

    def test_it_complains_if_less_than_minimum(self, meta):
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

    def test_it_complains_if_greater_than_maximum(self, meta):
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

    def test_it_works_if_number_is_between_min_and_max(self, meta):
        for val in (0.1, 0.5, 0.9):
            assert scene_spec.range_spec(0, 1).normalise(meta, val) == val


class TestSizedListSpec:
    def test_it_complains_if_not_matching_the_spec(self, meta):
        val = [1, 2, None]
        spec = scene_spec.sized_list_spec(sb.integer_spec(), 4)
        with assertRaises(BadSpecValue):
            spec.normalise(meta, val)

    def test_it_complains_if_list_is_not_the_correct_length(self, meta):
        spec = scene_spec.sized_list_spec(sb.integer_spec(), 2)
        with assertRaises(BadSpecValue, "Expected certain number of parts", want=2, got=1):
            spec.normalise(meta, 1)

        with assertRaises(BadSpecValue, "Expected certain number of parts", want=2, got=1):
            spec.normalise(meta, [1])

        with assertRaises(BadSpecValue, "Expected certain number of parts", want=2, got=3):
            spec.normalise(meta, [1, 2, 3])

    def test_it_returns_the_list_if_correct_length(self, meta):
        spec = scene_spec.sized_list_spec(sb.string_spec(), 1)

        got = spec.normalise(meta, "one")
        assert got == ["one"]

        got = spec.normalise(meta, ["one"])
        assert got == ["one"]

        spec = scene_spec.sized_list_spec(sb.string_spec(), 2)
        got = spec.normalise(meta, ["one", "two"])
        assert got == ["one", "two"]


class TestHsbk:
    def test_it_expects_4_items(self, meta):
        spec = scene_spec.hsbk()

        val = [200, 1, 1, 3500]
        assert spec.normalise(meta, val) == val

    def test_it_complains_if_hue_is_outside_0_and_360(self, meta):
        spec = scene_spec.hsbk()

        with assertRaises(
            BadSpecValue, "Number must be between min and max", minimum=0, maximum=360
        ):
            spec.normalise(meta, [-1, 1, 1, 3500])

        with assertRaises(
            BadSpecValue, "Number must be between min and max", minimum=0, maximum=360
        ):
            spec.normalise(meta, [361, 1, 1, 3500])

    def test_it_complains_if_saturation_is_outside_0_and_1(self, meta):
        spec = scene_spec.hsbk()

        with assertRaises(BadSpecValue, "Number must be between min and max", minimum=0, maximum=1):
            spec.normalise(meta, [1, -0.1, 1, 3500])

        with assertRaises(BadSpecValue, "Number must be between min and max", minimum=0, maximum=1):
            spec.normalise(meta, [360, 1.1, 1, 3500])

    def test_it_complains_if_brightness_is_outside_0_and_1(self, meta):
        spec = scene_spec.hsbk()

        with assertRaises(BadSpecValue, "Number must be between min and max", minimum=0, maximum=1):
            spec.normalise(meta, [1, 0, -0.1, 3500])

        with assertRaises(BadSpecValue, "Number must be between min and max", minimum=0, maximum=1):
            spec.normalise(meta, [360, 1, 1.1, 3500])

    def test_it_complains_if_kelvin_is_outside_1500_and_9000(self, meta):
        spec = scene_spec.hsbk()

        with assertRaises(
            BadSpecValue, "Number must be between min and max", minimum=1500, maximum=9000
        ):
            spec.normalise(meta, [1, 0, 0, 1000])

        with assertRaises(
            BadSpecValue, "Number must be between min and max", minimum=1500, maximum=9000
        ):
            spec.normalise(meta, [360, 1, 1, 9001])


class TestJsonStringSpec:
    class TestStoring:
        def test_it_loads_if_the_val_is_a_string_and_returns_as_dumps(self, meta):
            spec = sb.set_options(one=sb.integer_spec())
            spec = scene_spec.json_string_spec(spec, True)
            got = spec.normalise(meta, '{"one": 2, "two": 3}')
            assert got == '{"one": 2}'

        def test_it_doesnt_loads_if_not_a_string_and_returns_as_dumps(self, meta):
            spec = sb.set_options(one=sb.integer_spec())
            spec = scene_spec.json_string_spec(spec, True)
            got = spec.normalise(meta, {"one": 2, "two": 3})
            assert got == '{"one": 2}'

        def test_it_complains_if_string_is_not_valid_json(self, meta):
            spec = sb.set_options(one=sb.integer_spec())
            spec = scene_spec.json_string_spec(spec, True)
            with assertRaises(BadSpecValue, "Value was not valid json"):
                spec.normalise(meta, "{")

        def test_it_complains_if_we_dont_match_our_spec(self, meta):
            spec = sb.set_options(one=sb.required(sb.integer_spec()))
            spec = scene_spec.json_string_spec(spec, True)
            with assertRaises(BadSpecValue):
                spec.normalise(meta, '{"two": 3}')

    class TestNotStoring:
        def test_it_loads_if_the_val_is_a_string(self, meta):
            spec = sb.set_options(one=sb.integer_spec())
            spec = scene_spec.json_string_spec(spec, False)
            got = spec.normalise(meta, '{"one": 2, "two": 3}')
            assert got == {"one": 2}

        def test_it_doesnt_loads_if_not_a_string(self, meta):
            spec = sb.set_options(one=sb.integer_spec())
            spec = scene_spec.json_string_spec(spec, False)
            got = spec.normalise(meta, {"one": 2, "two": 3})
            assert got == {"one": 2}

        def test_it_complains_if_we_dont_match_our_spec(self, meta):
            spec = sb.set_options(one=sb.required(sb.integer_spec()))
            spec = scene_spec.json_string_spec(spec, False)
            with assertRaises(BadSpecValue):
                spec.normalise(meta, {"two": 3})


class TestMakeSpec:
    class TestStoring:
        def test_it_has_nullable_fields_for_everything_but_uuid_and_matcher(self, meta):
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

        def test_it_makes_a_class_with_no_extra_methods_and_makes_json_into_text(self, meta):
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

    class TestNotStoring:

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
                                pytest.helpers.print_packet_difference(w, m)

                    assert len(want) == len(msgs)
                    assert list(want) == msgs

                    power_message.assert_called_once_with(overrides)
                    colors_from_hsbks.assert_called_once_with(s.obj.zones, overrides)
                    determine_duration.assert_called_once_with(overrides)

            return V()

        def test_it_has_nullable_fields_for_everything_but_uuid_and_matcher(self, meta):
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

        def test_it_does_not_store_as_text(self, V):
            for key, val in V.kwargs.items():
                assert getattr(V.obj, key) == val

        class TestTransformOptions:
            def test_it_takes_into_account_power_color_and_duration(self, V):
                assert V.obj.transform_options == {"power": "on", "color": "red", "duration": 1}

                V.obj.power = False
                assert V.obj.transform_options == {"power": "off", "color": "red", "duration": 1}

                V.obj.color = None
                assert V.obj.transform_options == {"power": "off", "duration": 1}

                V.obj.duration = None
                assert V.obj.transform_options == {"power": "off"}

                V.obj.power = None
                assert V.obj.transform_options == {}

        class TestColorsFromHsbks:
            def test_it_takes_uses_hsbks_if_no_overrides(self, V):
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

            def test_it_takes_overrides_from_overrides(self, V):
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

        class TestPowerMessage:
            def test_it_does_not_provide_SetLightPower_if_we_have_no_power(self, V):
                V.obj.power = None
                msg = V.obj.power_message({})
                assert msg is None

            def test_it_provides_power_if_in_overrides(self, V):
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

            def test_it_provides_power_if_on_the_object(self, V):
                V.obj.power = True
                V.obj.duration = 3

                msg = V.obj.power_message({})
                assert msg == LightMessages.SetLightPower(level=65535, duration=3)

                V.obj.power = False
                msg = V.obj.power_message({})
                assert msg == LightMessages.SetLightPower(level=0, duration=3)

        class TestZoneMsgs:
            def test_it_yields_power_message_if_we_have_one(self, V, overrides):
                msg = mock.Mock(name="msg")
                power_message = mock.Mock(name="power_message", return_value=msg)

                with mock.patch.object(V.obj, "power_message", power_message):
                    itr = iter(V.obj.zone_msgs(overrides))
                    m = next(itr)
                    assert m is msg

                power_message.assert_called_once_with(overrides)

            def test_it_does_not_yield_power_message_if_we_dont_have_one(self, V, overrides):
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

            class TestYieldingSetMultiZoneColorZonesMessages:

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

            def test_it_works(self, V, setter):
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

            def test_it_works2(self, V, setter):
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

        class TestChainMsgs:
            def test_it_yields_power_message_if_we_have_one(self, V, overrides):
                msg = mock.Mock(name="msg")
                power_message = mock.Mock(name="power_message", return_value=msg)

                with mock.patch.object(V.obj, "power_message", power_message):
                    itr = iter(V.obj.chain_msgs(overrides))
                    m = next(itr)
                    assert m is msg

                power_message.assert_called_once_with(overrides)

            def test_it_does_not_yield_power_message_if_we_dont_have_one(self, V, overrides):
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

            class TestYieldingSet64Messages:

                @pytest.fixture()
                def setter(self):
                    def setter(**kwargs):
                        return TileMessages.Set64(
                            length=1, x=0, y=0, width=8, res_required=False, **kwargs
                        )

                    return setter

                def test_it_works(self, V, setter, overrides):
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
                                pytest.helpers.print_packet_difference(w, m)

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
