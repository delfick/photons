import binascii

import pytest
from delfick_project.norms import sb
from photons_canvas.points.simple_messages import Set64
from photons_messages import TileMessages
from photons_messages.fields import Color


@pytest.fixture
def seed():
    return TileMessages.Set64.create(
        source=0,
        sequence=0,
        target="d073d5000000",
        res_required=False,
        ack_required=False,
        tile_index=0,
        length=1,
        x=0,
        y=0,
        width=8,
        duration=0,
        colors=[],
    )


def assertSame(real, simple):
    different = []
    for name in real.Meta.all_names:
        if "reserved" in name:
            continue

        if not hasattr(simple, name):
            continue

        if name == "target":
            assert real.serial == simple.serial
        else:
            r = getattr(real, name)
            s = getattr(simple, name)
            if r != s:
                different.append((name, r, s))

    if different:
        print("FOUND DIFFERENCES:")
        for name, r, s in different:
            if name == "colors":
                print("COLORS:")
                for i, (cr, cs) in enumerate(zip(r, s)):
                    print(f"\t{i}:\n\t\t{cr}\n\t\t{cs}")
            else:
                print(f"{name}: '{s}' instead of '{r}'")
        assert False

    assert real.pack() == simple.pack()


class TestSet64:
    def test_it_is_based_off_a_seed(self, seed):
        assertSame(seed, Set64(source=0))

    def test_it_behaves_like_a_real_message(self, seed):
        msg = Set64()
        assert seed.tobytes(serial=None) == msg.tobytes(serial=None)

        assert msg | TileMessages.Set64
        assert not msg | TileMessages.State64

        assert msg | Set64

        assert msg.simplify() is msg
        assert not msg.is_dynamic

    def test_it_allows_you_to_create_directly_with_attributes(self):
        colors = [(i, 1, 1, 3500) for i in range(64)]

        kwargs = {
            "source": 1,
            "sequence": 1,
            "target": "d073d5000001",
            "res_required": True,
            "ack_required": True,
            "tile_index": 21,
            "length": 6,
            "x": 20,
            "y": 80,
            "protocol": 1024,
            "width": 6,
            "duration": 11,
            "colors": colors,
        }

        real = TileMessages.Set64.create(
            **{
                **kwargs,
                "colors": [{"hue": h, "saturation": s, "brightness": b, "kelvin": k} for h, s, b, k in colors],
            }
        )
        simple = Set64(**kwargs)

        assertSame(real, simple)

    def test_it_lets_you_modify_attributes(self):
        changes = [
            ("source", 10),
            ("sequence", 12),
            ("res_required", True),
            ("ack_required", True),
            ("tile_index", 5),
            ("length", 10),
            ("x", 9),
            ("y", 99),
            ("protocol", 1024),
            ("width", 9),
            ("duration", 1000),
        ]

        original = {
            "source": 3,
            "sequence": 3,
            "target": "d073d5000003",
            "res_required": False,
            "ack_required": False,
            "tile_index": 3,
            "length": 3,
            "x": 3,
            "y": 3,
            "protocol": 3,
            "width": 3,
            "duration": 3,
        }

        for name, val in changes:
            real = TileMessages.Set64.create(**original)
            simple = Set64(**original)

            setattr(real, name, val)
            setattr(simple, name, val)

            assert getattr(real, name) == getattr(simple, name)
            if name == "duration":
                assert simple.actual(name) == val * 1000
            else:
                assert simple.actual(name) == val

            assertSame(real, simple)
            assertSame(real, simple.clone())

            real.target = "d073d5001188"
            simple.target = "d073d5001188"
            assert real.serial == simple.serial == "d073d5001188"
            assert real.target == binascii.unhexlify("d073d5001188") + b"\x00\x00"

        real = TileMessages.Set64.create(**original)
        simple = Set64(**original)

        for name, value in changes + [("target", "d073d5998877")]:
            real[name] = value

        simple.update({**dict(changes), "target": "d073d5998877"})
        assertSame(real, simple)
        assertSame(real, simple.clone())

    def test_it_can_be_cloned(self):
        msg = Set64(width=6, tile_index=20)
        clone = msg.clone()
        assert clone.pack() == msg.pack()

        clone.width = 8
        assert clone.width == 8
        assert msg.width == 6

    def test_it_can_be_given_colors_in_multiple_ways(self, seed):
        c1 = Color(100, 1, 1, 3500)
        c2 = Color(200, 0, 0, 3500)

        setting = [
            (c1.hue, c1.saturation, c1.brightness, c1.kelvin),
            (c2.hue, c2.saturation, c2.brightness, c2.kelvin),
        ]
        real = seed.clone()
        real.colors = [Color(h, s, b, k) for h, s, b, k in setting]

        simple = Set64(colors=setting)
        r = real.payload.pack()
        w = simple.pack()[36 * 8 :]

        assert len(r) == len(w)
        assert r == w
        assert simple.colors == [c1, c2, *([Color(0, 0, 0, 0)] * 62)]

        setting = setting * 3
        simple = Set64(colors=setting)
        assert simple.colors == [*([c1, c2] * 3), *([Color(0, 0, 0, 0)] * 58)]

    def test_it_can_be_given_None_as_a_valid_color(self):
        simple = Set64(colors=[(100, 1, 0, 3500), None, (200, 0, 1, 9000)])
        assert simple.colors == [Color(100, 1, 0, 3500), Color(0, 0, 0, 0), Color(200, 0, 1, 9000)] + [Color(0, 0, 0, 0)] * 61

    def test_it_can_have_a_source_set(self):
        simple = Set64()
        assert simple.source is sb.NotSpecified

        simple.update(dict(source=200, sequence=3, target="d073d5001188"))
        assert simple.source == 200
        assert simple.sequence == 3
        assert simple.serial == "d073d5001188"
