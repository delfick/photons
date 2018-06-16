# coding: spec

import photons_products_registry as registry

from photons_app.test_helpers import TestCase

describe TestCase, "Product Registries":
    it "has registries":
        self.assertIs(registry.ProductRegistries.LIFI.value, registry.LIFIProductRegistry)

    it "has enum_for_id":
        for vname, e in registry.ProductRegistries.__members__.items():
            if vname != "EMPTY":
                for _, product in e.value.__members__.items():
                    vid = registry.VendorRegistry[vname].value
                    pid = int(product.value)
                    en = registry.enum_for_ids(pid, vid)
                    self.assertEqual(en, product)

    it "has capability_for_enum":
        for name, e in registry.Capabilities.__members__.items():
            company = e.value.company.upper()
            if company == "LIFX":
                company = "LIFI"

            products = registry.ProductRegistries[company].value
            en = products[name]
            self.assertEqual(registry.capability_for_enum(en), e)

    it "can get product names":
        names = registry.product_names()
        self.assertEqual(len(names), 28)
        for key in names:
            self.assertRegex(key, r"\d+\.\d+")
            self.assertEqual(type(names[key]), str)
