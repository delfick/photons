
import random

from delfick_project.errors_pytest import assertRaises
from photons_control.colour import Effects, NoSuchEffect, Waveform
from photons_messages import LightMessages

class TestEffects:
    def test_it_supports_a_None_effect(self):
        assert Effects.make(None) == {}

    def test_it_complains_if_the_effect_doesnt_exist(self):
        assert not hasattr(Effects, "blah")
        with assertRaises(NoSuchEffect, effect="blah"):
            Effects.make("blah")

    def test_it_complains_if_the_effect_does_exist_but_isnt_an_effect(self):
        assert hasattr(Effects, "__dict__")
        with assertRaises(NoSuchEffect, effect="__dict__"):
            Effects.make("__dict__")

    def test_it_has_built_in_effects(self):
        available = ["pulse", "sine", "half_sine", "triangle", "saw", "breathe"]

        for effect in available:
            assert hasattr(Effects, effect)
            assert getattr(Effects, effect)._is_effect
            options = Effects.make(effect)
            assert type(options["waveform"]) == Waveform
            for k in options:
                assert k in LightMessages.SetWaveformOptional.Meta.all_names

            overrides = {k: random.random() * 10 for k in options if k != "waveform"}
            final = {**overrides}

            if effect == "pulse":
                # pulse is special, it takes in duty_cycle too
                overrides["duty_cycle"] = random.random() * 10
                del overrides["skew_ratio"]
                final["skew_ratio"] = 1 - overrides["duty_cycle"]

            options2 = Effects.make(effect, **overrides)
            assert options2 == {"waveform": options["waveform"], **final}
