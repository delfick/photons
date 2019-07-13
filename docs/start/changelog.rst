.. _changelog:

ChangeLog
=========

0.20.1 - 13 July 2019
   * Fixed a bug in the device finder when you use the same device finder more
     than once with a different filter. It was forgetting devices from one filter
     and making that device not there for a subsequent filter.

0.20.0 - 13 July 2019
   * Fixed shutdown logic so that finally blocks work when we get a SIGINT
   * Refactored the transport target mechanism. There are two breaking changes
     from this work, otherwise everything should behave the same as before:

     * photons_socket no longer exists, all that functionality now belongs in
       photons_transport. It is likely that you don't need to change anything
       other than enabling the ``("lifx.photons", "transport")`` in your script
       instead of ``("lifx.photons", "socket")``
     * The third variable in a run_with call is now the original message that
       was sent to get that reply

0.13.5 - 6 July 2019
    * Some code shuffling in photons_transport
    * Removed get_list and device_forgetter from transport targets
    * Made TransportBridge.finish an async function
    * "lifx lan:find_devices" now takes a reference as the first argument, so you
      can find by filter now. For example, to find all multizone devices::
         
         lifx lan:find_devices match:cap=multizone
    * Removed afr.default_broadcast. broadcast=True will use it or you can say
      afr.transport_target.default_broadcast
    * Changed how retry messages are created so that messages from the same
      afr do not ever change source. This does mean that we can't have more than
      256 messages to the same device in flight or we get the wrong replies to
      messages, but that seems unlikely to happen

0.13.4 - 4 May 2019
   * Tiny fix to how we determine if we have enough multizone messages that
     shouldn't make a difference in practice.
   * Implemented a new "Planner" API for gathering information from devices
   * Making code in photons_control.multizone easier to re-use
   * Added a photons_control.tile.SetTileEffect helper for easily setting tile
     effects

0.13.3 - 23 April 2019
   * Fixed a bug with giving an array of complex messgaes to target.script where
     it would send the messages to all devices rather than just the devices you
     care about.
   * Some minor internal code shuffling
   * target.script() can now take objects that already have a run_with method
     and they won't be converted before use.
   * The simplify method on targets has been simplified (this is used by the
     script mechanism to convert items into objects with a run_with method for
     use)

0.13.2 - 7 April 2019
   * Fixed behaviour when you provide a list of complex messages to run_with
   * Made HardCodedSerials more efficient when the afr has already found devices

0.13.0 - 7 April 2019
   * Slight improvement to photons_control.transform.Transformer
   * Introduced photons_control.script.FromGenerator which is a complex message
     that let's you define an async generator function that yields messages to
     be sent to devices
   * Introduced FromGeneratorPerSerial which is like FromGenerator but calls
     the generator function per serial found in the reference.
   * Specifying an array of complex messages in a run_with will now send those
     complex messages in parallel rather than one after each other. (i.e. if
     you specify ``run_with([Pipeline(...), Pipeline(...)])``
   * Pipeline and Repeater are now written in terms of FromGenerator
   * Decider no longer exists
   * Created a photons_control.transform.PowerToggle message

0.12.1 - 31 March 2019
    * Removed an unnecessary option from the implementation of Transformer

0.12.0 - 31 March 2019
    * Moved tile orientation logic into photons_control instead of being in
      photons_tile_paint

    * The find method on SpecialReference objects will now return even if we
      didn't find all the serials we were looking for. The pattern is now:

      .. code-block:: python
        
        found, serials = reference.find(afr, afr.default_broadcast, timeout=30)
        missing = reference.missing(found)

      Or:

      .. code-block:: python
        
        found, serials = reference.find(afr, timeout=30)
        reference.raise_on_missing(found)

    * Reworked the internal API for discovery so that if we are trying to find
      known serials, we don't spam the network with too many discovery packets.

    * Changed the api for finding devices such that timeout must now be a keyword
      argument and broadcast is not necessary to specify.

      So, if you have a special reference:

      .. code-block:: python

        # before
        found, serials = await special_reference.find(afr, True, 30)

        # after
        found, serials = await special_reference.find(afr, timeout=30)

      And if you are using find_devices on the afr:

      .. code-block:: python

        # before
        found = await afr.find_devices(True)

        # after
        found = await afr.find_devices()

      Note that if you know what serials you are searching for you can ask the
      afr to find them specifically by saying:

      .. code-block:: python

         serials = ["d073d5000001", "d073d5000002"]
         found, missing = await afr.find_specific_serials(serials, timeout=20)

      This method is much less spammy on the network than calling find_devices
      till you have all your devices.

0.11.0 - 20 March 2019
    * Implemented a limit on inflight messages per run_with call

      * As part of this, the timeout option to run_with is now message_timeout
        and represents the timeout for each message rather than the whole
        run_with call

    * Updated the protocol definition

      * Biggest change is StateHostFirmware and StateWifiFirmware now represent
        the firmware version as two Uint16 instead of one Uint32. The two numbers
        represent the major and minor component of the version
      * TileMessages.SetState64 and TileMessages.GetState64 are now Set64 and
        Get64 respectively

    * We now determine if we have extended multizone using version_major and
      version_minor instead of build on the StateHostFirmware

0.10.2 - 3 March 2019
    * Fixed a bug when applying a theme to multiple devices

0.10.1 - 20 February 2019
    * Added messages for Extended multizone and firmware effects
    * Made photons_products_registry aware of extended multizone
    * The apply_theme action now uses extended multizone when that is available
    * Added the following actions:

      * attr: Much like get_attr and set_attr but without the auto prefix
      * attr_actual: same as attr but shows the actual values on the responses
        rather than the transformed values
      * multizone_effect: start or stop a firmware effect on your multizone
        device
      * tile_effect: start or stop a firmware effect on your LIFX Tile.

    * Fixed the set_zones action to be more useful

0.10.0 - 23 January 2019
    * Started using ruamel.yaml instead of PyYaml to load configuration

0.9.5 - 21 January 2019
    * Make the dice roll work better with multiple tiles and the combine_tiles
      option
    * Made the falling animation much smoother. Many thanks to @mic159!
    * Changed the ``hue_ranges`` option of the tile_falling animation to
      ``line_hues`` and the ``line_tip_hue`` option to ``line_tip_hues``
    * Added tile_balls tile animation
    * Made it possible for photons_protocol to specify an enum field as having
      unknown values
    * Fixed how skew_ratio in waveform messages are transformed. It's actually
      scaled 0 to 1, not -1 to 1.

0.9.4 - 3 January 2019
    * Added get_tile_positions action
    * Adjustments to the dice font
    * Added the scripts used to generate photons_messages

0.9.3 - 30 December 2018
    * Minor changes
    * Another efficiency improvement for tile animations
    * Some fixes to the scrolling animations
    * Make it possible to combine many tiles into one animation

0.9.2 - 27 December 2018
    * Made tile_marquee work without options
    * Made animations on multiple tiles recalculate the whole animation for each
      tile even if they have the same user coords
    * Fixed tile_dice_roll to work when you have specified multiple tiles
    * Take into account the orientation of the tiles when doing animations
    * apply_theme action takes tile orientation into account
    * Made tile_falling and tile_nyan animations take in a random_orientation
      option for choosing random orientations for each tile

0.9.1 - 26 December 2018
    * Added tile_falling animation
    * Added tile_dice_roll animation
    * tile_marquee animation can now do dashes and underscores
    * Added a tile_dice script for putting 1 to 5 on your tiles
    * Made tile animations are lot less taxing on the CPU
    * Made tile_gameoflife animation default to using coords from the tiles
      rather than assuming the tiles are in a line.
    * Changed the defaults for animations to have higher refresh rate and not
      require acks on the messages
    * Made it possible to pause an animation if you've started it programatically

0.9.0 - 17 December 2018
    The photons_messages module is now generated via a process internal to LIFX.
    The information required for this will be made public but for now I'm making
    the resulting changes to photons.

    As part of this change there are some moves and renames to some messages.

    * ColourMessages is now LightMessages
    * LightPower messages are now under LightMessages
    * Infrared messages are now under LightMessages
    * Infrared messages now have `brightness` instead of `level`
    * Fixed Acknowledgement message typo
    * Multizone messages have better names

      * SetMultiZoneColorZones -> SetColorZones
      * GetMultiZoneColorZones -> GetColorZones
      * StateMultiZoneStateZones -> StateZone
      * StateMultiZoneStateMultiZones -> StateMultiZone

    * Tile messages have better names

      * GetTileState64 -> GetState64
      * SetTileState64 -> SetState64
      * StateTileState64 -> State64

    * Some reserved fields have more consistent names
    * SetWaveForm is now SetWaveform
    * SetWaveFormOptional is now SetWaveformOptional
    * num_zones field on multizone messages is now zones_count
    * The type field in SetColorZones was renamed to apply

0.8.1 - 2 December 2018
    * Added twinkles tile animation
    * Made it a bit easier to start animations programmatically

0.8.0 - 29 November 2018
    * Merging photons_script module into photons_control and photons_transport
    * Removing the need for the ATarget context manager and replacing it with a
      session() context manager on the target itself.

      So:

      .. code-block:: python

        from photons_script.script import ATarget
        async with ATarget(target) as afr:
            ...

      Becomes:

      .. code-block:: python

        async with target.session() as afr
            ...
    * Pipeline/Repeater/Decider is now in photons_control.script instead of
      photons_script.script.

0.7.1 - 29 November 2018
    * Made it easier to construct a SetWaveFormOptional
    * Fix handling of sockets when the network goes away

0.7.0 - 10 November 2018
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
