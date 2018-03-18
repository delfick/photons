"""
The applier takes in the theme and returns a collection of colours for you to
apply to the device. It is up to you to determine which applier to use and how
to actually send the colours to the device.

This module contains ``types`` which is a dictioary of
``{<type>: {"0d": <applier>, "1d": <applier>, "2d": <applier>}}`` where ``0d``
is for lights with a single color, ``1d`` is for strips and ``2d`` are for tiles.

The ``0d`` is always ``LightApplier``

.. autoclass:: photons_themes.appliers.single.LightApplier

SPLOTCH applier
+++++++++++++++

The applier uses ``LightApplier`` for ``0d`` and ``1d`` and ``2d`` come
from the ``splotch`` module.

.. automodule:: photons_themes.appliers.splotch

STRIPE appliers
+++++++++++++++

All the STRIPE appliers use ``LightApplier`` and ``StripApplierSplotch`` for
``0d`` and ``1d`` respectively.


There is ``VERTICAL_STRIPE``, ``HORIZONTAL_STRIPE``, ``DOWN_DIAGONAL_STRIPE``
and ``UP_DIAGONAL_STRIPE`` appliers.

.. automodule:: photons_themes.appliers.stripes
"""
from photons_themes.appliers.stripes import TileApplierDownDiagnoalStripe, TileApplierUpDiagnoalStripe, TileApplierSquareStripe
from photons_themes.appliers.stripes import TileApplierHorizontalStripe, TileApplierVerticalStripe
from photons_themes.appliers.splotch import StripApplierSplotch, TileApplierSplotch
from photons_themes.appliers.single import LightApplier

types = {
      "SPLOTCH": {"0d": LightApplier, "1d": StripApplierSplotch, "2d": TileApplierSplotch}
    , "VERTICAL_STRIPE": {"0d": LightApplier, "1d": StripApplierSplotch, "2d": TileApplierVerticalStripe}
    , "HORIZONTAL_STRIPE": {"0d": LightApplier, "1d": StripApplierSplotch, "2d": TileApplierHorizontalStripe}
    , "DOWN_DIAGONAL_STRIPE": {"0d": LightApplier, "1d": StripApplierSplotch, "2d": TileApplierDownDiagnoalStripe}
    , "UP_DIAGONAL_STRIPE": {"0d": LightApplier, "1d": StripApplierSplotch, "2d": TileApplierUpDiagnoalStripe}
    , "SQUARE_STRIPE": {"0d": LightApplier, "1d": StripApplierSplotch, "2d": TileApplierSquareStripe}
    }
