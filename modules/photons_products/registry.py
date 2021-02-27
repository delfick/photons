from photons_products.base import CapabilityRange, CapabilityValue, ProductsHolder
from photons_products.enums import Zones, Family
from photons_products import lifx


class ProductRegistry:
    class LMB_MESH_A21(lifx.Product):
        pid = 1
        family = Family.LMB
        friendly = "LIFX Original 1000"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (2500, 9000)

    class LMBG_MESH_GU10(lifx.Product):
        pid = 3
        family = Family.LMBG
        friendly = "LIFX Color 650"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (2500, 9000)

    class LCMV4_A19_WHITE_LV(lifx.Product):
        pid = 10
        family = Family.LCM1
        friendly = "LIFX White 800 (Low Voltage)"

        class cap(lifx.Capability):
            has_color = False
            min_kelvin, max_kelvin = (2700, 6500)
            has_variable_color_temp = True

    class LCMV4_A19_WHITE_HV(lifx.Product):
        pid = 11
        family = Family.LCM1
        friendly = "LIFX White 800 (High Voltage)"

        class cap(lifx.Capability):
            has_color = False
            min_kelvin, max_kelvin = (2700, 6500)
            has_variable_color_temp = True

    class LCMV4_A21_COLOR(lifx.Product):
        pid = 15
        family = Family.LCM1
        friendly = "LIFX Color 1000"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (2500, 9000)

    class LCMV4_BR30_WHITE_LV(lifx.Product):
        pid = 18
        family = Family.LCM1
        friendly = "LIFX White 900 BR30 (Low Voltage)"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = True
            min_kelvin, max_kelvin = (2500, 9000)

    class LCMV4_BR30_WHITE_HV(lifx.Product):
        pid = 19
        family = Family.LCM1
        friendly = "LIFX White 900 BR30 (High Voltage)"

        class cap(lifx.Capability):
            has_color = False
            min_kelvin, max_kelvin = (2500, 9000)
            has_variable_color_temp = True

    class LCMV4_BR30_COLOR(lifx.Product):
        pid = 20
        family = Family.LCM1
        friendly = "LIFX Color 1000 BR30"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (2500, 9000)

    class LCMV4_A19_COLOR(lifx.Product):
        pid = 22
        family = Family.LCM1
        friendly = "LIFX Color 1000"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (2500, 9000)

    class LCM2_A19(lifx.Product):
        pid = 27
        family = Family.LCM2
        friendly = "LIFX A19"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_BR30(lifx.Product):
        pid = 28
        family = Family.LCM2
        friendly = "LIFX BR30"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_A19_PLUS(lifx.Product):
        pid = 29
        family = Family.LCM2
        friendly = "LIFX A19 Night Vision"

        class cap(lifx.Capability):
            has_ir = True
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_BR30_PLUS(lifx.Product):
        pid = 30
        family = Family.LCM2
        friendly = "LIFX BR30 Night Vision"

        class cap(lifx.Capability):
            has_ir = True
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM1_Z(lifx.Product):
        pid = 31
        family = Family.LCM1
        friendly = "LIFX Z"

        class cap(lifx.Capability):
            zones = Zones.LINEAR
            has_color = True
            min_kelvin, max_kelvin = (2500, 9000)

    class LCM2_Z(lifx.Product):
        pid = 32
        family = Family.LCM2
        friendly = "LIFX Z"

        class cap(lifx.Capability):
            zones = Zones.LINEAR
            has_color = True
            has_extended_multizone = CapabilityValue(False).until(2, 77, becomes=True)
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_DOWNLIGHT_OL(lifx.Product):
        pid = 36
        family = Family.LCM2
        friendly = "LIFX Downlight"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_DOWNLIGHT_NL(lifx.Product):
        pid = 37
        family = Family.LCM2
        friendly = "LIFX Downlight"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_BEAM(lifx.Product):
        pid = 38
        family = Family.LCM2
        friendly = "LIFX Beam"

        class cap(lifx.Capability):
            zones = Zones.LINEAR
            has_color = True
            has_extended_multizone = CapabilityValue(False).until(2, 77, becomes=True)
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_DOWNLIGHT_WW_IC4(lifx.Product):
        pid = 39
        family = Family.LCM2
        friendly = "LIFX Downlight White to Warm"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = True
            min_kelvin, max_kelvin = CapabilityRange((1500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_DOWNLIGHT_COLOR_IC4(lifx.Product):
        pid = 40
        family = Family.LCM2
        friendly = "LIFX Downlight"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_A19_HK(lifx.Product):
        pid = 43
        family = Family.LCM2
        friendly = "LIFX A19"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_BR30_HK(lifx.Product):
        pid = 44
        family = Family.LCM2
        friendly = "LIFX BR30"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_A19_PLUS_HK(lifx.Product):
        pid = 45
        family = Family.LCM2
        friendly = "LIFX A19 Night Vision"

        class cap(lifx.Capability):
            has_ir = True
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM2_BR30_PLUS_HK(lifx.Product):
        pid = 46
        family = Family.LCM2
        friendly = "LIFX BR30 Night Vision"

        class cap(lifx.Capability):
            has_ir = True
            has_color = True
            min_kelvin, max_kelvin = CapabilityRange((2500, 9000)).until(
                2, 80, becomes=(1500, 9000)
            )

    class LCM3_MINI_COLOR(lifx.Product):
        pid = 49
        family = Family.LCM3
        friendly = "LIFX Mini Color"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_MINI_WW(lifx.Product):
        pid = 50
        family = Family.LCM3
        friendly = "LIFX Mini White to Warm"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = True
            min_kelvin, max_kelvin = CapabilityRange((1500, 6500)).until(
                3, 70, becomes=(1500, 9000)
            )

    class LCM3_MINI_WHITE(lifx.Product):
        pid = 51
        family = Family.LCM3
        friendly = "LIFX Mini White"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin, max_kelvin = (2700, 2700)

    class LCM3_GU10_COLOR(lifx.Product):
        pid = 52
        family = Family.LCM3
        friendly = "LIFX GU10"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_GU10_ST(lifx.Product):
        pid = 53
        family = Family.LCM3
        friendly = "LIFX GU10"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_TILE(lifx.Product):
        pid = 55
        friendly = "LIFX Tile"
        family = Family.LCM3

        class cap(lifx.Capability):
            zones = Zones.MATRIX
            has_color = True
            has_chain = True
            min_kelvin, max_kelvin = (2500, 9000)

    class LCM3_CANDLE(lifx.Product):
        pid = 57
        family = Family.LCM3
        friendly = "LIFX Candle"

        class cap(lifx.Capability):
            zones = Zones.MATRIX
            has_chain = False
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_MINI2_COLOR(lifx.Product):
        pid = 59
        family = Family.LCM3
        friendly = "LIFX Mini Color"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_MINI2_WW(lifx.Product):
        pid = 60
        family = Family.LCM3
        friendly = "LIFX Mini White to Warm"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = True
            min_kelvin, max_kelvin = CapabilityRange((1500, 6500)).until(
                3, 70, becomes=(1500, 9000)
            )

    class LCM3_MINI2_WHITE(lifx.Product):
        pid = 61
        family = Family.LCM3
        friendly = "LIFX Mini White"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin, max_kelvin = (2700, 2700)

    class LCM3_A19(lifx.Product):
        pid = 62
        family = Family.LCM3
        friendly = "LIFX A19"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_BR30(lifx.Product):
        pid = 63
        family = Family.LCM3
        friendly = "LIFX BR30"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_A19_PLUS(lifx.Product):
        pid = 64
        family = Family.LCM3
        friendly = "LIFX A19 Night Vision"

        class cap(lifx.Capability):
            has_ir = True
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_BR30_PLUS(lifx.Product):
        pid = 65
        family = Family.LCM3
        friendly = "LIFX BR30 Night Vision"

        class cap(lifx.Capability):
            has_ir = True
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_MINI2_WHITE_INT(lifx.Product):
        pid = 66
        family = Family.LCM3
        friendly = "LIFX Mini White"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin, max_kelvin = (2700, 2700)

    class LCM3_CANDLE_CA(lifx.Product):
        pid = 68
        family = Family.LCM3
        friendly = "LIFX Candle"

        class cap(lifx.Capability):
            zones = Zones.MATRIX
            has_chain = False
            has_color = False
            has_variable_color_temp = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_16_SWITCH(lifx.Product):
        pid = 70
        family = Family.LCM3
        friendly = "LIFX Switch"

        class cap(lifx.NonLightCapability):
            has_relays = True
            has_buttons = True

    class LCM3_16_SWITCH_I(lifx.Product):
        pid = 71
        family = Family.LCM3
        friendly = "Switch"

        class cap(lifx.NonLightCapability):
            has_relays = True
            has_buttons = True

    class LCM3_32_CANDLE_WW(lifx.Product):
        pid = 81
        family = Family.LCM3
        friendly = "LIFX Candle White to Warm"

        class cap(lifx.Capability):
            zones = Zones.SINGLE
            has_chain = False
            has_color = False
            has_variable_color_temp = True
            min_kelvin, max_kelvin = (2200, 6500)

    class LCM3_FILAMENT_ST64_CLEAR_US(lifx.Product):
        pid = 82
        family = Family.LCM3
        friendly = "LIFX Filament Clear"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin, max_kelvin = (2100, 2100)

    class LCM3_FILAMENT_ST64_AMBER_US(lifx.Product):
        pid = 85
        family = Family.LCM3
        friendly = "LIFX Filament Amber"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin, max_kelvin = (2000, 2000)

    class LCM3_MINI_WHITE_US(lifx.Product):
        pid = 87
        family = Family.LCM3
        friendly = "Mini White"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin, max_kelvin = (2700, 2700)

    class LCM3_MINI_WHITE_INTL(lifx.Product):
        pid = 88
        family = Family.LCM3
        friendly = "LIFX Mini White"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin, max_kelvin = (2700, 2700)

    class LCM3_32_SWITCH_I(lifx.Product):
        pid = 89
        family = Family.LCM3
        friendly = "LIFX Switch"

        class cap(lifx.NonLightCapability):
            has_relays = True
            has_buttons = True

    class LCM3_A19_CLEAN(lifx.Product):
        pid = 90
        family = Family.LCM3
        friendly = "LIFX Clean"

        class cap(lifx.Capability):
            has_hev = True
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_32_MINI_COLOR_US(lifx.Product):
        pid = 91
        family = Family.LCM3
        friendly = "LIFX Color"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_32_MINI_COLOR_INTL(lifx.Product):
        pid = 92
        family = Family.LCM3
        friendly = "LIFX Color"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_32_BR30_US(lifx.Product):
        pid = 94
        family = Family.LCM3
        friendly = "LIFX BR30"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_32_CANDLE_WW_INTL(lifx.Product):
        pid = 96
        family = Family.LCM3
        friendly = "LIFX Candle White to Warm"

        class cap(lifx.Capability):
            zones = Zones.SINGLE
            has_chain = False
            has_color = False
            has_variable_color_temp = True
            min_kelvin, max_kelvin = (2200, 6500)

    class LCM3_32_A19_INTL(lifx.Product):
        pid = 97
        family = Family.LCM3
        friendly = "LIFX A19"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_32_BR30_INTL(lifx.Product):
        pid = 98
        family = Family.LCM3
        friendly = "LIFX BR30"

        class cap(lifx.Capability):
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_A19_CLEAN_INTL(lifx.Product):
        pid = 99
        family = Family.LCM3
        friendly = "LIFX Clean"

        class cap(lifx.Capability):
            has_hev = True
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_FILAMENT_ST64_CLEAR_INTL(lifx.Product):
        pid = 100
        family = Family.LCM3
        friendly = "LIFX Filament Clear"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin, max_kelvin = (2100, 2100)

    class LCM3_FILAMENT_ST64_AMBER_INTL(lifx.Product):
        pid = 101
        family = Family.LCM3
        friendly = "LIFX Filament Amber"

        class cap(lifx.Capability):
            has_color = False
            has_variable_color_temp = False
            min_kelvin, max_kelvin = (2000, 2000)

    class LCM3_32_A19_PLUS_US(lifx.Product):
        pid = 109
        family = Family.LCM3
        friendly = "LIFX A19 Night Vision"

        class cap(lifx.Capability):
            has_ir = True
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_32_BR30_PLUS_US(lifx.Product):
        pid = 110
        family = Family.LCM3
        friendly = "LIFX BR30 Night Vision"

        class cap(lifx.Capability):
            has_ir = True
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)

    class LCM3_32_A19_PLUS_INTL(lifx.Product):
        pid = 111
        family = Family.LCM3
        friendly = "LIFX A19 Night Vision"

        class cap(lifx.Capability):
            has_ir = True
            has_color = True
            min_kelvin, max_kelvin = (1500, 9000)


Products = ProductsHolder(ProductRegistry, lifx.Capability)
