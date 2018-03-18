__doc__ = """
This is an implementation of ``photons_transport`` for writing to a device over
a socket.

We expose this target as the ``lan`` target. So put this in your configuration:

.. code-block:: yaml

    ---

    targets:
      mylan:
        type: lan
        options:
          default_broadcast: 255.255.255.255

And then you have a ``mylan`` target that uses ``255.255.255.255`` as it's
broadcast address.

.. note:: This module will create a target called ``lan`` in the configuration
  if one is not already specified.

.. automodule:: photons_socket.messages

The target
----------

.. automodule:: photons_socket.target

The connection
--------------

.. automodule:: photons_socket.connection
    :members:

Helper for tests
----------------

.. automodule:: photons_socket.fake
"""
