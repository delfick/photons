# coding: spec

from photons_app.test_helpers import TestCase

from photons_messages import ColourMessages, Waveform, protocol_register

describe TestCase, "ColourMessages":
    def unpack(self, msg):
        return ColourMessages.unpack(msg, protocol_register=protocol_register)

    it "has Setcolor":
        msg = self.unpack("3100001480dd8f29d073d522932200000000000000000301000000000000000066000000001c079919ff7fc409e8030000")
        assert msg | ColourMessages.SetColor
        self.assertEqual(msg.payload.as_dict()
            , { 'setcolor_reserved1': b'\x00'
              , 'hue': 9.997711146715496
              , 'saturation': 0.09999237048905166
              , 'brightness': 0.49999237048905165
              , 'kelvin': 2500
              , 'duration': 1
              }
            )

        self.assertEqual(msg.payload.actual("hue"), 1820)
        self.assertEqual(msg.payload.actual("saturation"), 6553)
        self.assertEqual(msg.payload.actual("brightness"), 32767)
        self.assertEqual(msg.payload.actual("kelvin"), 2500)
        self.assertEqual(msg.payload.actual("duration"), 1000)

    it "has SetWaveForm":
        msg = self.unpack("39000014575df165d073d52293220000000000000000030100000000000000006700000000001c479919ff7fc409d00700000000a040cc0c01")
        assert msg | ColourMessages.SetWaveForm
        self.assertEqual(msg.payload.as_dict()
            , { 'stream': 0
              , 'transient': 0
              , 'hue': 99.9990844586862
              , 'saturation': 0.09999237048905166
              , 'brightness': 0.49999237048905165
              , 'kelvin': 2500
              , 'period': 2.0
              , 'cycles': 5.0
              , 'skew_ratio': 0.0999786370433668
              , 'waveform': Waveform.SINE
              }
            )

        self.assertEqual(msg.payload.actual("stream"), 0)
        self.assertEqual(msg.payload.actual("transient"), 0)
        self.assertEqual(msg.payload.actual("hue"), 18204)
        self.assertEqual(msg.payload.actual("saturation"), 6553)
        self.assertEqual(msg.payload.actual("brightness"), 32767)
        self.assertEqual(msg.payload.actual("kelvin"), 2500)
        self.assertEqual(msg.payload.actual("period"), 2000)
        self.assertEqual(msg.payload.actual("cycles"), 5)
        self.assertEqual(msg.payload.actual("skew_ratio"), 3276)
        self.assertEqual(msg.payload.actual("waveform"), 1)

    it "has SetWaveFormOptional":
        msg = self.unpack("3d0000149c0bf333d073d52293220000000000000000030100000000000000007700000000001c470000ff7fc409d00700000000a040cc0c0101000101")
        assert msg | ColourMessages.SetWaveFormOptional
        self.assertEqual(msg.payload.as_dict()
            , { 'stream': 0
              , 'transient': 0
              , 'hue': 99.9990844586862
              , 'saturation': 0.0
              , 'brightness': 0.49999237048905165
              , 'kelvin': 2500
              , 'period': 2.0
              , 'cycles': 5.0
              , 'skew_ratio': 0.0999786370433668
              , 'waveform': Waveform.SINE
              , 'set_hue': 1
              , 'set_saturation': 0
              , 'set_brightness': 1
              , 'set_kelvin': 1
              }
            )

        self.assertEqual(msg.payload.actual("stream"), 0)
        self.assertEqual(msg.payload.actual("transient"), 0)
        self.assertEqual(msg.payload.actual("hue"), 18204)
        self.assertEqual(msg.payload.actual("saturation"), 0)
        self.assertEqual(msg.payload.actual("brightness"), 32767)
        self.assertEqual(msg.payload.actual("kelvin"), 2500)
        self.assertEqual(msg.payload.actual("period"), 2000)
        self.assertEqual(msg.payload.actual("cycles"), 5)
        self.assertEqual(msg.payload.actual("skew_ratio"), 3276)
        self.assertEqual(msg.payload.actual("waveform"), 1)
        self.assertEqual(msg.payload.actual("set_hue"), 1)
        self.assertEqual(msg.payload.actual("set_saturation"), 0)
        self.assertEqual(msg.payload.actual("set_brightness"), 1)
        self.assertEqual(msg.payload.actual("set_kelvin"), 1)

    it "has LightState":
        msg = self.unpack("580000149c0bf333d073d522932200004c4946585632010100e8a719e40800006b00000000079919ff7fc4090000ffff64656e00000000000000000000000000000000000000000000000000000000000000000000000000")
        assert msg | ColourMessages.LightState
        self.assertEqual(msg.payload.as_dict()
            , { 'hue': 9.843900205996796
              , 'saturation': 0.09999237048905166
              , 'brightness': 0.49999237048905165
              , 'kelvin': 2500
              , 'power': 65535
              , 'label': 'den'
              , 'state_reserved1': 0
              , 'state_reserved2': 0
              }
            )

        self.assertEqual(msg.payload.actual("hue"), 1792)
        self.assertEqual(msg.payload.actual("saturation"), 6553)
        self.assertEqual(msg.payload.actual("brightness"), 32767)
        self.assertEqual(msg.payload.actual("kelvin"), 2500)
        self.assertEqual(msg.payload.actual("power"), 65535)
        self.assertEqual(msg.payload.actual("label")
            , b"den\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            )
