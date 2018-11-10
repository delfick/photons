.. _changelog:

ChangeLog
=========

0.7.0 - TBD
    Moved code into ``photons_control`` and ``photons_messages``. This means
    ``photons_attributes``, ``photons_device_messages``, ``photons_tile_messages``
    and ``photons_transform`` no longer exist.

    Anything related to messages in those modules (and in ``photons_sockets.messages``
    is now in ``photons_messages``.

    Everything else in those modules, and the actions from ``photons_protocol``
    are now in ``photons_control``.

0.6.3 - 10 November 2018
    * Fix potential hang when connecting to a device (very unlikely error case,
      but now it's handled).
    * Moved the __or__ functionality on packets onto the LIFXPacket object as
      it's implementation depended on fields specifically on LIFXPacket. This
      is essentially a no-op within photons.
    * Added a create helper to TransportTarget

0.6.2 - 22 October 2018
    * Fixed cleanup logic
    * Make products registry aware of kelvin ranges
    * Made defaults for values in a message definition go through the spec for
      that field when no value is specified
    * Don't raise an error if we can't find any devices, instead respect the
      error_catcher option and only raise errors for not finding each serial that
      we couldn't find

0.6.1 - 1 September 2018
    * Added the tile_gameoflife task for doing a Conway's game of life simulation
      on your tiles.

0.6 - 26 August 2018
    * Cleaned up the code that handles retries and multiple replies

      - multiple_replies, first_send and first_wait are no longer options
        for run_with as they are no longer necessary
      - The packet definition now includes options for specifying how many
        packets to expect

    * When error_catcher to run_with is a callable, it is called straight away
      with all errors instead of being put onto the asyncio loop to be called
      soon. This means when you have awaited on run_with, you know that all
      errors have been given to the error_catcher
    * Remove uvloop altogether. I don't think it is actually necessary and it
      would break after the process was alive long enough. Also it's disabled
      for windows anyway, and something that needs to be compiled at
      installation.
    * collector.configuration["final_future"] is now the Future object itself
      rather than a function returning the future.
    * Anything inheriting from TransportTarget now has ``protocol_register``
      attribute instead of ``protocols`` and ``final_future`` instead of
      ``final_fut_finder``
    * Updated delfick_app to give us a --json-console-logs argument for showing
      logs as json lines

0.5.11 - 28 July 2018
    * Small fix to the version_number_spec for defining a version number on a
      protocol message
    * Made uvloop optional. To turn it off put ``photons_app: {use_uvloop: false}``
      in your configuration.

0.5.10 - 22 July 2018
    * Made version in StateHostFirmware and StateWifiFirmware a string instead
      of a float to tell the difference between "1.2" and "1.20"
    * Fix leaks of asyncio.Task objects

0.5.9 - 15 July 2018
    * Fixed a bug in the task runner such where a future could be given a result
      even though it was already done.
    * Made photons_app.helpers.ChildOfFuture behave as if it was cancelled when
      the parent future gets a non exception result. This is because ChildOfFuture
      is used to propagate errors/cancellation rather than propagate results.
    * Upgraded PyYaml and uvloop so that you can install this under python3.7
    * Fixes to make photons compatible with python3.7

0.5.8 - 1 July 2018
    * Fixed a bug I introduced in the Transformer in 0.5.7

0.5.7 - 1 July 2018
    * Fixed the FakeTarget in photons_app.test_helpers to deal with errors
      correctly
    * Made ``photons_transform.transformer.Transformer`` faster for most cases
      by making it not check the current state of the device when it doesn't
      need to

0.5.6 - 23 June 2018
    * photons_script.script.Repeater can now be stopped by raising Repater.Stop()
      in the on_done_loop callback
    * DeviceFinder can now be used to target specific serials

0.5.5 - 16 June 2018
    * Small fix to how as_dict() on a packet works so it does the right thing
      for packets that contain lists in the payload.
    * Added direction option to the marquee tile animation
    * Added nyan tile animation

0.5.4 - 28 April 2018
    * You can now specify ``("lifx.photon", "__all__")`` as a dependency and all
      photons modules will be seen as a dependency of your script.

      Note however that you should not do this in a module you expect to be used
      as a dependency by another module (otherwise you'll get cyclic dependencies).

0.5.3 - 22 April 2018
    * Tiny fix to TileState64 message

0.5.2 - 21 April 2018
    * Small fixes to the tile animations

0.5.1 - 31 March 2018
    * Tile animations
    * Added a ``serial`` property to packets that returns the hexlified target
      i.e. "d073d5000001" or None if target isn't set on the packet
    * Now installs and runs on Windows.

0.5 - 19 March 2018
    Initial opensource release after over a year of internal development.
