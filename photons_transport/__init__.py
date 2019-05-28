__doc__ = """
Core functionality for making photons transports. These are objects responsible
for getting messages to a device.

Tasks
-----

See :ref:`tasks`.

.. photons_module_tasks::

Target
------

.. automodule:: photons_transport.base
"""

from photons_transport.retry_options import RetryOptions, RetryIterator

RetryOptions = RetryOptions
RetryIterator = RetryIterator
