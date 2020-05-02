.. _installation_root:

Requirements
============

Photons requires a UNIX-like operating system (Linux, macOS, Windows Subsystem
for Linux) with Python 3.6 or newer installed.

.. include:: installation.inc

.. _activation:

Activating the virtual environment
----------------------------------

The installation method above installs Photons into a virtual environment which
needs to be activated prior to use. The activation command can be included in
larger shell scripts to make the ``lifx`` utility available to those scripts.

To activate the virtual environment created earlier, run::

    $ source ~/.photons-core/bin/activate

.. note:: Replace ``~/.photons-core`` with the location of the virtual
   environment, if necessary.

To deactivate the virtual environment, run::

    (.photons-core) $ deactivate
