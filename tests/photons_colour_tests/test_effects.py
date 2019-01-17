# coding: spec

from photons_colour import Effects, Waveform, NoSuchEffect

from photons_app.test_helpers import TestCase

from photons_messages import LightMessages

import random

describe TestCase, "Effects":
    it "supports a None effect":
        self.assertEqual(Effects.make(None), {})

    it "complains if the effect doesn't exist":
        assert not hasattr(Effects, "blah")
        with self.fuzzyAssertRaisesError(NoSuchEffect, effect="blah"):
            Effects.make("blah")

    it "complains if the effect does exist but isn't an effect":
        assert hasattr(Effects, "__dict__")
        with self.fuzzyAssertRaisesError(NoSuchEffect, effect="__dict__"):
            Effects.make("__dict__")

    it "has built in effects":
        available = [
              "pulse"
            , "sine"
            , "half_sine"
            , "triangle"
            , "saw"
            , "breathe"
            ]

        for effect in available:
            assert hasattr(Effects, effect)
            assert getattr(Effects, effect)._is_effect
            options = Effects.make(effect)
            self.assertEqual(type(options["waveform"]), Waveform)
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
            self.assertEqual(options2, {"waveform": options["waveform"], **final})
