.. _other_helpers:

Other things to make your life easier
=====================================

Photons provides some other utilities inside ``photons_app.helpers``. It is a
Photons convention to import this module with the alias ``hp`` and access
functionality from that:

.. code-block:: python

    from photons_app import helpers as hp


    with hp.a_temp_file() as fle:
        fle.write(b"hello")
        fle.flush()

        with open(fle.name, "rb") as reopened:
            assert reopened.read() == b"hello"

.. autofunction:: photons_app.helpers.add_error

.. autofunction:: photons_app.helpers.a_temp_file

.. autofunction:: photons_app.helpers.nested_dict_retrieve

.. autoclass:: photons_app.helpers.memoized_property
