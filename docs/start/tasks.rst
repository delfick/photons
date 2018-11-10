.. _tasks:

Tasks
=====

Photons provides tasks that can be executed from the command line
(as discussed in :ref:`lifx_photons_lifx_script`).

These tasks are executed like::

  $ lifx <target>:<action> <reference> <artifact> -- '{<options>}'

For example::

  $ lifx lan:set_attr d073d5000001 power -- '{"level": 0}'

Note that the target isn't always required, for example::

  $ lifx lan:unpack -- 24000034781b278000000000000000000000000000000101000000000000000002000000

When you run a command, if you want all the logging to go away, then you can
specify ``--silent`` after any positional arguments and before the ``--``.
For example::

  $ lifx lan:unpack --silent -- 24000034781b278000000000000000000000000000000101000000000000000002000000

Or you can have more logging by saying ``--debug`` instead.

References
----------

For those tasks that can take in a "special reference", the ``reference`` can be
one of the following:

``d073d5000001``
  A single serial. The serial can be found etched on the device. All LIFX serials
  are the also the MAC address of the device and always start with ``d073d5``.

``d073d5000001,d073d5000002``
  Multiple serials, as a comma separated list

``_``
  An underscore means find all the devices on the network

``match:<options>``
  This let's us select devices based on filters.

  For example:
  
  match:group_name=one&cap=multizone
    Find all the strips in the ``one`` group

  match:location_name=My%20Home
    Find all the lights in the ``My Home`` location

  See :ref:`finder_filters` for valid options to the match filter.

  Note that for this option to work, the ``device_finder`` module must be
  activated. (this matters if you are running your own script)

``file:/path/to/file``
  Point to a file containing newline separated serials in it.

Available tasks
---------------

Tasks are created across the different available modules. Note that this means
for the task to be available, that module needs to be activated. If you are
using the ``lifx`` script then all modules are already enabled. If you create
your own scripts and you want an action to be enabled, you need to make sure
your script enables the module it comes from.

.. photons_module_tasks:: *
