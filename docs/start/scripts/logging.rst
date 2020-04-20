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
    The program name to use when not logging to the console

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

If you start your script using the ``library_setup`` method then when you call
``setup_logging`` you'll have the options available to you from that
function which you can find in the documentation for the
`setup_logging <https://delfick-project.readthedocs.io/en/latest/api/logging.html>`_
function.
