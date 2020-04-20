.. _available_caps:

Available Capabilities
======================

When you :ref:`make <products_root>` a capability object, you have available
a number of attributes.

zones
    This is one of the ``photons_producst.Zones`` values. So either
    ``Zones.SINGLE`` which says this device only has one zone (e.g. a LIFX A19),
    ``Zones.LINEAR`` that says we have multizone zones in a line (so, the LIFX
    Strip and LIFX Beam) and ``Zones.MATRIX`` which says we have a 2d matrix
    of zones (Tile and Candle)

has_ir
    Does this device output infrared light (the LIFX+ range)

has_color
    Does this device support different colours? If this is ``False``, then the
    device only supports shades of white.

has_chain
    Does this device have child devices. At this time that is only the LIFX
    Tile

has_variable_color_temp
    Does this device have a range of Kelvin values. Some LIFX products can
    only output one kelvin value.

min_kelvin
    The minimum kelvin value supported by this product

max_kelvin
    The maximum kelvin value supported by this product

product
    The product object associated with this device. See
    :ref:`below <product_object>` for what is on this object.

firmware_major
    If this capability has been loaded with firmware information, this will be
    the ``major`` component of the firmware. Otherwise this will be ``0``.

firmware_minor
    If this capability has been loaded with firmware information, this will be
    the ``minor`` component of the firmware. Otherwise this will be ``0``.

has_matrix
    A shortcut for saying ``cap.zones is Zones.MATRIX``

has_multizone
    A shortcut for saying ``cap.zones is Zones.LINEAR``

has_extended_multizone
    Some LIFX devices (second gen Strip and all Beam products) support an
    ``extended multizone`` API that is more efficient than the original
    multizone API the first generation Strips support. This is only available
    for second generation strips after a certain firmware version, so as long
    as this ``cap`` object has been loaded with firmware information,
    ``has_extended_multizone`` can tell you if the device supports the better
    API.

.. _product_object:

Product object
--------------

The ``cap.product`` object (the object from ``Products[vendor, product]``) also
has some useful attributes on it.

vendor
    This is likely ``photons_products.VendorRegistry.LIFX``

pid
    The ``product_id`` for this device.

family
    The hardware family this product belongs to, so one of the
    ``photons_products.Family`` values:  ``Family.LMB`` (the originals),
    ``Family.LCM1`` (second generation), ``Family.LCM2`` (third generation)
    and ``Family.LCM3`` (fourth generation).

name:
    The name of the product

cap
    An instance of a Capability object

friendly
    A friendly name for the product

identifier
    The identifier of the product
