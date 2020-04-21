.. _logging:

Logs in Photons
===============

Photons has a couple features for working with logs.

The first one is we have the option to have colourful logs on the commandline.

When you run a Photons :ref:`action <photons_action>` you get colourful logs
setup for you. If you instead go for using the
:ref:`library_setup <library_setup>` option then you'll need to do something
like the following:

.. code-block:: python
    
    from delfick_project.logging import setup_logging
    import logging


    if __name__ == "__main__":
        setup_logging(level=logging.INFO)

Once you've setup logging you can use the ``photons_app.helpers.lc`` function
to easily log key value pairs to the command line.

For example:

.. code-block:: python
    
    from photons_app import helpers as hp

    import logging


    log = getLogger("my_script")
    log.info(hp.lc("My log", key1="value1", key2="value2"))

Logging destination
-------------------

When you start from a photons action, your script will have available to it
the following command line options for configuration where the logs end up:

--silent
    Only log errors

--debug
    Print debug logs

--logging-program LOGGING_PROGRAM
    When this option is provided and the logs are going to udp, tcp or syslog,
    then there will be a ``program`` value in the log that is this value.

--tcp-logging-address TCP_LOGGING_ADDRESS
    The address to use for giving log messages to tcp (i.e. localhost:9001)

--udp-logging-address UDP_LOGGING_ADDRESS
    The address to use for giving log messages to udp (i.e. localhost:9001)

--syslog-address SYSLOG_ADDRESS
    The address to use for syslog (i.e. /dev/log)

--json-console-logs
    If we haven't set other logging arguments, this will mean we log json lines to the console

--logging-handler-file LOGGING_HANDLER_FILE
    File to print logs to

For example if you were to run::

    $ lifx lan:attr _ GetColor --logging-program myprogram --udp-logging-address localhost:9999

Then a UDP socket listening on ``localhost:9999`` would receive logs that look
like the following:

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

.. note:: If you start your script using the ``library_setup`` method then when
    you call ``setup_logging`` you'll have the options available to you from
    that function which you can find in the documentation for the
    `setup_logging <https://delfick-project.readthedocs.io/en/latest/api/logging.html>`_
    function.

When you haven't specified a udp, tcp or syslog output, the logs will go to
the ``stderr`` on your terminal. Note that this only applies to anything logged
using Python's ``logging`` module in the standard library.

Most builtin Photons commands will use the ``print()`` function to print results
without the extra logging information. This output will go to ``stdout``. This
means for many commands you can redirect output to a file and that file will
only receive the useful output from that command.
