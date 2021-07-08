# coding: spec

from photons_control import test_helpers as chp

from photons_app import helpers as hp

from photons_messages import MultiZoneEffectType, TileEffectType
from photons_transport.fake import FakeDevice
from photons_products import Products

from delfick_project.errors_pytest import assertRaises

describe "default_responders":
    async it "has defaults":
        device = FakeDevice("d073d5000001", chp.default_responders())
        await device.start()

        assert device.attrs.vendor_id == 1
        assert device.attrs.product_id == 27

        assert device.attrs.firmware == hp.Firmware(0, 0)
        assert device.attrs.color == hp.Color(0, 1, 1, 3500)
        assert device.attrs.power == 0

        assert device.attrs.group_uuid == ""
        assert device.attrs.group_label == ""
        assert device.attrs.group_updated_at == 0

        assert device.attrs.location_uuid == ""
        assert device.attrs.location_label == ""
        assert device.attrs.location_updated_at == 0

        assert not any(isinstance(r, chp.ZonesResponder) for r in device.responders)
        assert not any(isinstance(r, chp.MatrixResponder) for r in device.responders)
        assert not any(isinstance(r, chp.InfraredResponder) for r in device.responders)

        for expect in (chp.ProductResponder, chp.LightStateResponder, chp.GroupingResponder):
            assert any(isinstance(r, expect) for r in device.responders)

    async it "can be infrared":
        device = FakeDevice("d073d5000001", chp.default_responders(Products.LCM2_A19_PLUS))
        await device.start()

        assert any(isinstance(r, chp.InfraredResponder) for r in device.responders)
        assert device.attrs.infrared == 0
        assert device.attrs.vendor_id == 1
        assert device.attrs.product_id == 29

        device = FakeDevice(
            "d073d5000001", chp.default_responders(Products.LCM2_A19_PLUS, infrared=200)
        )
        await device.start()
        assert device.attrs.infrared == 200

    async it "can be multizone":
        with assertRaises(
            AssertionError, "Product has multizone capability but no zones specified"
        ):
            device = FakeDevice("d073d5000001", chp.default_responders(Products.LCM1_Z))

        zones = [hp.Color(0, 0, 0, 0), hp.Color(1, 1, 1, 1)]
        device = FakeDevice("d073d5000001", chp.default_responders(Products.LCM1_Z, zones=zones))
        await device.start()

        assert any(isinstance(r, chp.ZonesResponder) for r in device.responders)
        assert device.attrs.zones == zones
        assert device.attrs.zones_effect == MultiZoneEffectType.OFF
        assert device.attrs.vendor_id == 1
        assert device.attrs.product_id == 31

        device = FakeDevice(
            "d073d5000001",
            chp.default_responders(
                Products.LCM1_Z, zones=zones, zones_effect=MultiZoneEffectType.MOVE
            ),
        )
        await device.start()
        assert device.attrs.zones_effect == MultiZoneEffectType.MOVE

    async it "can be a tile":
        device = FakeDevice("d073d5000001", chp.default_responders(Products.LCM3_TILE))
        await device.start()

        assert device.attrs.vendor_id == 1
        assert device.attrs.product_id == 55

        assert any(isinstance(r, chp.MatrixResponder) for r in device.responders)
        assert device.attrs.matrix_effect == TileEffectType.OFF

        device = FakeDevice(
            "d073d5000001",
            chp.default_responders(Products.LCM3_TILE, matrix_effect=TileEffectType.FLAME),
        )
        await device.start()
        assert device.attrs.matrix_effect == TileEffectType.FLAME
