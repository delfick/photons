# coding: spec

from photons_control import test_helpers as chp

from photons_app.test_helpers import AsyncTestCase

from photons_messages import MultiZoneEffectType, TileEffectType
from photons_transport.fake import FakeDevice
from photons_products import Products

describe AsyncTestCase, "default_responders":
    async it "has defaults":
        device = FakeDevice("d073d5000001", chp.default_responders())
        await device.start()

        self.assertEqual(device.attrs.vendor_id, 1)
        self.assertEqual(device.attrs.product_id, 27)

        self.assertEqual(device.attrs.firmware, chp.Firmware(0, 0, 0))
        self.assertEqual(device.attrs.color, chp.Color(0, 1, 1, 3500))
        self.assertEqual(device.attrs.power, 0)

        assert not any(isinstance(r, chp.ZonesResponder) for r in device.responders)
        assert not any(isinstance(r, chp.MatrixResponder) for r in device.responders)
        assert not any(isinstance(r, chp.InfraredResponder) for r in device.responders)

        for expect in (chp.ProductResponder, chp.LightStateResponder):
            assert any(isinstance(r, expect) for r in device.responders)

    async it "can be infrared":
        device = FakeDevice("d073d5000001", chp.default_responders(Products.LCM2_A19_PLUS))
        await device.start()

        assert any(isinstance(r, chp.InfraredResponder) for r in device.responders)
        self.assertEqual(device.attrs.infrared, 0)
        self.assertEqual(device.attrs.vendor_id, 1)
        self.assertEqual(device.attrs.product_id, 29)

        device = FakeDevice(
            "d073d5000001", chp.default_responders(Products.LCM2_A19_PLUS, infrared=200)
        )
        await device.start()
        self.assertEqual(device.attrs.infrared, 200)

    async it "can be multizone":
        with self.fuzzyAssertRaisesError(
            AssertionError, "Product has multizone capability but no zones specified"
        ):
            device = FakeDevice("d073d5000001", chp.default_responders(Products.LCM1_Z))

        zones = [chp.Color(0, 0, 0, 0), chp.Color(1, 1, 1, 1)]
        device = FakeDevice("d073d5000001", chp.default_responders(Products.LCM1_Z, zones=zones))
        await device.start()

        assert any(isinstance(r, chp.ZonesResponder) for r in device.responders)
        self.assertEqual(device.attrs.zones, zones)
        self.assertEqual(device.attrs.zones_effect, MultiZoneEffectType.OFF)
        self.assertEqual(device.attrs.vendor_id, 1)
        self.assertEqual(device.attrs.product_id, 31)

        device = FakeDevice(
            "d073d5000001",
            chp.default_responders(
                Products.LCM1_Z, zones=zones, zones_effect=MultiZoneEffectType.MOVE
            ),
        )
        await device.start()
        self.assertEqual(device.attrs.zones_effect, MultiZoneEffectType.MOVE)

    async it "can be a tile":
        device = FakeDevice("d073d5000001", chp.default_responders(Products.LCM3_TILE))
        await device.start()

        self.assertEqual(device.attrs.vendor_id, 1)
        self.assertEqual(device.attrs.product_id, 55)

        assert any(isinstance(r, chp.MatrixResponder) for r in device.responders)
        self.assertEqual(device.attrs.matrix_effect, TileEffectType.OFF)

        device = FakeDevice(
            "d073d5000001",
            chp.default_responders(Products.LCM3_TILE, matrix_effect=TileEffectType.FLAME),
        )
        await device.start()
        self.assertEqual(device.attrs.matrix_effect, TileEffectType.FLAME)
