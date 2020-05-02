.. _logging:

Logging with Photons
====================

Photons automatically provides colorful console logging for all registered
:ref:`actions <photons_action>`.

Use the ``setup_logging`` function to enable colorful console logging for
scripts that instantiate Photons using the :ref:`library_setup <library_setup>`
method:

.. code-block:: python

    from delfick_project.logging import setup_logging
    import logging

    if __name__ == "__main__":
        setup_logging(level=logging.INFO)

Use the ``photons_app.helpers.lc`` function to log key/value pairs to the
command line:

.. code-block:: python

    from photons_app import helpers as hp

    from delfick_project.logging import setup_logging
    import logging

    if __name__ == "__main__":
        setup_logging(level=logging.INFO)
        log = logging.getLogger("My Script")
        log.info(hp.lc("My log", key1="value1", key2="value2"))

Configuring log destination
---------------------------

The following command-line options are available for the ``lifx`` command-line
utility and any script that registers a Photons action.

``--silent``
    Only log errors to ``stderr``.

``--debug``
    Print debug logs

``--logging-program LOGGING_PROGRAM``
    This option adds ``LOGGING_PROGRAM`` in the ``program`` field to logs
    sent either syslog, UDP or TCP destinations.

``--tcp-logging-address TCP_LOGGING_ADDRESS:PORT``
    Send JSON-formatted logs to ``TCP_LOGGING_ADDRESS`` on port ``PORT``
    using TCP.

``--udp-logging-address UDP_LOGGING_ADDRESS``
    Send JSON-formatted logs to ``UDP_LOGGING_ADDRESS`` on port ``PORT`` using
    UDP.

``--syslog-address SYSLOG_ADDRESS``
    Send JSON-formatted logs to the ``SYSLOG_ADDRESS`` file descriptor, e.g.
    ``/dev/log``.

``--logging-handler-file LOGGING_HANDLER_FILE``
    Write JSON-formatted logs to ``LOGGING_HANDLER_FILE``, e.g.
    ``/path/to/photons.log``.

``--json-console-logs``
    Output JSON-formatted logs to the console. Ignored if another logging method
    is configured.

.. note:: Logs are only output to a single destination. The order of precedence
   is syslog followed by UDP then TCP. The console is only used if no
   alternative logging destination is provided.

The following example::

    $ lifx lan:attr _ GetColor --logging-program myprogram --udp-logging-address localhost:9999

Will send the following JSON-formatted log message to ``localhost`` on port
``9999`` over UDP:

.. code-block:: json

    {
        "@timestamp": "2020-04-21T11:30:33.041485",
        "address": ["192.168.1.1", 56700],
        "levelname": "INFO",
        "msg": "Creating datagram endpoint",
        "name": "photons_transport.transports.udp",
        "program": "myprogram",
        "serial": "d073d514e733"
    }

.. note:: The |setup_logging_func|_ has the same parameters available for
   scripts that instantiate Photons using the ``library_setup`` method.

.. |setup_logging_func| replace:: ``setup_logging`` function
.. _setup_logging_func: https://delfick-project.readthedocs.io/en/latest/api/logging.html

When no logging target is configured, logs will be output to ``stderr``. Note
that this only applies to anything logged using Python's ``logging`` module in
the standard library.

Most built-in Photons actions that output data use the ``print()`` function to
print data directly to ``stdout``. This output can be redirected to a file using
standard shell techniques and will not contain any logging information.
