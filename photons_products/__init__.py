"""
To get a product from the registry, you can do something like:

.. code-block:: python

    from photons_products import Products

    tile_product = Products.LCM3_TILE

    # or

    tile_product = Products["LCM3_TILE"]

    # or

    tile_product = Products[1, 55]

Once you have a product object, you can access certain things on it:

.. autoclass:: photons_products.base.Product

The capability object has several things on it:

.. autoclass:: photons_products.registry.Capability

.. show_capabilities::
"""
from photons_products.enums import VendorRegistry, Zones, Family
from photons_products.registry import Products

__all__ = ["VendorRegistry", "Zones", "Family", "Products"]
