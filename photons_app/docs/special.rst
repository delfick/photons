.. _photons_app_special:

Special References
==================

As mentioned in :ref:`script_mechanism`, you address devices by passing in serials
to the ``run_with`` or ``run_with_all`` methods. You may also provided special
objects that dynamically work out what devices to send the messages to.

These objects are subclasses of ``photons_app.special.SpecialReference``.

.. autoclass:: photons_app.special.SpecialReference

.. autoclass:: photons_app.special.FoundSerials

.. autoclass:: photons_app.special.HardCodedSerials

.. autoclass:: photons_app.special.ResolveReferencesFromFile

You can also use the device finder module to create a ``SpecialReference`` that
filters devices based on their properties. See :ref:`photons_device_finder`
