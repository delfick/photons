# coding: spec

from photons_app.test_helpers import assert_payloads_equals

from photons_messages import LightMessages, Waveform, protocol_register

from photons_protocol.messages import Messages
from photons_protocol.types import Optional

from delfick_project.norms import sb
import pytest

describe "LightMessages":

    def create(self, msg):
        return LightMessages.create(msg, protocol_register=protocol_register)

    it "has Setcolor":
        msg = self.create(
            "3100001480dd8f29d073d522932200000000000000000301000000000000000066000000001c079919ff7fc409e8030000"
        )
        assert msg | LightMessages.SetColor
        assert_payloads_equals(
            msg.payload,
            {
                "hue": 9.997711146715496,
                "saturation": 0.09999237048905166,
                "brightness": 0.49999237048905165,
                "kelvin": 2500,
                "duration": 1,
            },
        )

        assert msg.payload.actual("hue") == 1820
        assert msg.payload.actual("saturation") == 6553
        assert msg.payload.actual("brightness") == 32767
        assert msg.payload.actual("kelvin") == 2500
        assert msg.payload.actual("duration") == 1000

    it "has SetWaveform":
        msg = self.create(
            "39000014575df165d073d52293220000000000000000030100000000000000006700000000001c479919ff7fc409d00700000000a040cc0c01"
        )
        assert msg | LightMessages.SetWaveform
        assert_payloads_equals(
            msg.payload,
            {
                "transient": 0,
                "hue": 99.9990844586862,
                "saturation": 0.09999237048905166,
                "brightness": 0.49999237048905165,
                "kelvin": 2500,
                "period": 2.0,
                "cycles": 5.0,
                "skew_ratio": 0.5499961852445259,
                "waveform": Waveform.SINE,
            },
        )

        assert msg.payload.actual("transient") == 0
        assert msg.payload.actual("hue") == 18204
        assert msg.payload.actual("saturation") == 6553
        assert msg.payload.actual("brightness") == 32767
        assert msg.payload.actual("kelvin") == 2500
        assert msg.payload.actual("period") == 2000
        assert msg.payload.actual("cycles") == 5
        assert msg.payload.actual("skew_ratio") == 3276
        assert msg.payload.actual("waveform") == 1

    it "has SetWaveformOptional":
        msg = self.create(
            "3d0000149c0bf333d073d52293220000000000000000030100000000000000007700000000001c470000ff7fc409d00700000000a040ff7f0101000101"
        )
        assert msg | LightMessages.SetWaveformOptional
        assert_payloads_equals(
            msg.payload,
            {
                "transient": 0,
                "hue": 99.9990844586862,
                "saturation": 0.0,
                "brightness": 0.49999237048905165,
                "kelvin": 2500,
                "period": 2.0,
                "cycles": 5.0,
                "skew_ratio": 1,
                "waveform": Waveform.SINE,
                "set_hue": 1,
                "set_saturation": 0,
                "set_brightness": 1,
                "set_kelvin": 1,
            },
        )

        assert msg.payload.actual("transient") == 0
        assert msg.payload.actual("hue") == 18204
        assert msg.payload.actual("saturation") == 0
        assert msg.payload.actual("brightness") == 32767
        assert msg.payload.actual("kelvin") == 2500
        assert msg.payload.actual("period") == 2000
        assert msg.payload.actual("cycles") == 5
        assert msg.payload.actual("skew_ratio") == 32767
        assert msg.payload.actual("waveform") == 1
        assert msg.payload.actual("set_hue") == 1
        assert msg.payload.actual("set_saturation") == 0
        assert msg.payload.actual("set_brightness") == 1
        assert msg.payload.actual("set_kelvin") == 1

    it "SetWaveformOptional does not require all hsbk values":
        msg = LightMessages.SetWaveformOptional(hue=100, source=1, sequence=0, target=None)
        assert msg.actual("brightness") is sb.NotSpecified

        assert msg.set_hue == 1
        assert msg.set_saturation == 0
        assert msg.set_brightness == 0
        assert msg.set_kelvin == 0
        unpackd = Messages.create(msg.pack(), protocol_register=protocol_register)

        assert unpackd.hue == pytest.approx(100, rel=1e-2)
        assert unpackd.set_hue == 1
        assert unpackd.set_saturation == 0
        assert unpackd.saturation == 0
        assert unpackd.set_brightness == 0
        assert unpackd.brightness == 0
        assert unpackd.set_kelvin == 0
        assert unpackd.kelvin == 0

        msg = LightMessages.SetWaveformOptional.create(hue=100, source=1, sequence=0, target=None)
        assert msg.actual("brightness") is Optional

        assert msg.set_hue == 1
        assert msg.set_saturation == 0
        assert msg.set_brightness == 0
        assert msg.set_kelvin == 0

        unpackd = Messages.create(msg.pack(), protocol_register=protocol_register)

        assert unpackd.hue == pytest.approx(100, rel=1e-2)
        assert unpackd.set_hue == 1
        assert unpackd.set_saturation == 0
        assert unpackd.saturation == 0
        assert unpackd.set_brightness == 0
        assert unpackd.brightness == 0
        assert unpackd.set_kelvin == 0
        assert unpackd.kelvin == 0

    it "has LightState":
        msg = self.create(
            "580000149c0bf333d073d522932200004c4946585632010100e8a719e40800006b00000000079919ff7fc4090000ffff64656e00000000000000000000000000000000000000000000000000000000000000000000000000"
        )
        assert msg | LightMessages.LightState
        assert_payloads_equals(
            msg.payload,
            {
                "hue": 9.843900205996796,
                "saturation": 0.09999237048905166,
                "brightness": 0.49999237048905165,
                "kelvin": 2500,
                "power": 65535,
                "label": "den",
            },
        )

        assert msg.payload.actual("hue") == 1792
        assert msg.payload.actual("saturation") == 6553
        assert msg.payload.actual("brightness") == 32767
        assert msg.payload.actual("kelvin") == 2500
        assert msg.payload.actual("power") == 65535
        assert (
            msg.payload.actual("label").tobytes()
            == b"den\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )
