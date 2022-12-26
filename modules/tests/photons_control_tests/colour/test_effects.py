# coding: spec

import random

from delfick_project.errors_pytest import assertRaises
from photons_control.colour import Effects, NoSuchEffect, Waveform
from photons_messages import LightMessages

describe "Effects":
    it "supports a None effect":
        assert Effects.make(None) == {}

    it "complains if the effect doesn't exist":
        assert not hasattr(Effects, "blah")
        with assertRaises(NoSuchEffect, effect="blah"):
            Effects.make("blah")

    it "complains if the effect does exist but isn't an effect":
        assert hasattr(Effects, "__dict__")
        with assertRaises(NoSuchEffect, effect="__dict__"):
            Effects.make("__dict__")

    it "has built in effects":
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
