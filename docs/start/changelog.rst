.. _changelog:

ChangeLog
=========

.. _release-core-0-40-2:

0.40.2 - 15 April 2021
    * Small fix to the arguments to the animate task

.. _release-core-0-40-1:

0.40.1 - 5 April 2021
    * The ``post`` hook on a Task class now takes ``exc_info`` with the exception that
      cause ``execute_task`` to stop.
    * Some improvements to how tasks are run.

.. _release-core-0-40-0:

0.40.0 - 28 March 2021
    * ``photons_app.actions.an_action`` has been replaced with
      ``photons_app.tasks.task_register`` and a new class based way of defining
      tasks. New documentation for this new infrastructure can be found at
      https://photons.delfick.com/scripts/photons_action.html
    * ``photons_app.special.SpecialReference`` objects no longer guarantee getting
      ``finish`` called on them at the end of the program
    * ``photons_canvas.animations.actions.animation_action`` has been replaced in favour
      of a ``AnimationTask`` in the same module and the new task register.
    * Shuffled the ``photons_app`` module a little. It is unlikely any of the
      changed imports will impact users of Photons.
    * deprecated ``get_attr`` and ``set_attr`` tasks. Please use ``attr`` instead.

.. _release-core-0-33-0:

0.33.0 - 15 March 2021
    * Allow --debug when ``PHOTONS_SILENT_BY_DEFAULT=1``
    * Removed the identifier property from the products registry. There's no
      official list of these identifiers and they were too arbitrary
      to be useful.
    * Product registry now recognises different kelvin values from updated
      firmware on devices.
    * The device finder now supports finding by ``relays``, ``hev`` and
      ``buttons`` capabilities.
    * Pulled in new HEV messages.

.. _release-core-0-32-5:

0.32.5 - 3 January 2020
    * Adding LICENSE file to the package on pypi

.. _release-core-0-32-4:

0.32.4 - 26 December 2020
    * Add the ability to pause a hp.ATicker

.. _release-core-0-32-3:

0.32.3 - 14 December 2020
    * You may now set ``PHOTONS_SILENT_BY_DEFAULT=1`` in your environment to have a
      ``--unsilent`` option instead of ``--silent`` option to make logs appear.

      This is the same as not having that environment variable and setting ``--silent``
    * HSBK values are now rounded
    * Introduced a polyfill hp.asynccontextmanager
    * Introduced a helper to fix async context managers made in photons
    * Fixed a small race condition in shutting down photons
    * Removed some more memory leaks

.. _release-core-0-32-2:

0.32.2 - 5 December 2020
    * Sort find_ips output by ip address
    * Make retry gaps configurable on a target
    * ``photons_transport.RetryOptions`` is now ``photons_transport.RetryTicker``

.. _release-core-0-32-1:

0.32.1 - 28 November 2020
    * Fix some more memory leaks

.. _release-core-0-32-0:

0.32.0 - 22 November 2020
    * Update dependencies for python3.9 compatibility

.. _release-core-0-31-5:

0.31.5 - 6 November 2020
    * Synced the product registry
    * Synced the protocol repository

.. _release-core-0-31-4:

0.31.4 - 23 August 2020
    * Fixed discovery so it doesn't take 4 seconds

      * The way discovery happens means that it was retrying sending discovery
        packets even though it already had results because the timeout for each
        attempt to find devices was less than the time it took to get back all
        the results.

    * No longer raise an exception when we receive a state packet from a device
      with an unrecognised enum value
    * A ResultStreamer with an error catcher that gets plain exceptions will
      no longer be called when a task on the result streamer is cancelled.
    * The CapabilityPlan will now return a ``state_version`` property with the
      ``StateVersion`` packet it received from the device.

.. _release-core-0-31-3:

0.31.3 - 15 August 2020
    * Fix bug in marquee based animations
    * Make sure the SetZonesPlan always applies even if it was recently applied.

.. _release-core-0-31-2:

0.31.2 - 12 August 2020
    * Fixed a bug where the device_finder would cause all the CPU to be used
    * Made retry for device discovery less agressive

.. _release-core-0-31-1:

0.31.1 - 9 August 2020
    * Fix specifying range/rate options for animations

.. _release-core-0-31-0:

0.31.0 - 9 August 2020
    * The ``photons_app.helpers.ATicker`` helper now yields
      ``(iteration, time_till_next)`` where ``iteration`` is the count of
      iterations starting from 1, and ``time_till_next`` is the number of seconds
      till the next scheduled iteration.
    * Removed photons_app.helpers.async_as_normal. It wasn't possible to ensure
      sure the task created from that was cleaned up
    * hp.ChildOfFuture is now a context manager to prevent memory leaks

        .. code-block:: python
            
            from photons_app import helpers as hp

            
            with hp.ChildOfFuture(parent_fut) as fut:
                ...

        Or

        .. code-block:: python

            from photons_app import helpers as hp

            fut = hp.ChildOfFuture(parent_fut)
            try:
                ...
            finally:
                fut.cancel()
    * hp.tick must now be used as an async context manager

        .. code-block:: python

            from photons_app import helpers as hp


            async for hp.tick(...) as ticks:
                async for _ in ticks:
                    ...
    * Make it possible to break a stream of packets.

      .. code-block:: python

        async with target.session() as sender:
            async with sender(msg, reference) as pkts:
                async for pkt in pkts:
                    ...

                    raise pkts.StopPacketStream()

    * cleaned up some old code and removed memory leaks
    * PowerToggle now has a ``group=True`` option (or you can use
      PowerToggleGroup) that means the power toggle treats the lights as a group.
      In this mode, if any light is turned on, then they are all turned off,
      otherwise they are all turned on.
    * Added ``cli_output``, ``settings_output`` and ``env_output`` options to
      ``lifx lan:find_ips`` task.

.. _release-core-0-30-0:

0.30.0 - 11 July 2020
    This release is the biggest change to the programmatic interface since the
    internal version of this library at LIFX was created over 4 years ago.

    * Rewritten documentation
    * Rewritten tile animations
    * New and improved API for creating custom scripts.
    * Moved code from https://github.com/delfick/photons-core to
      https://github.com/delfick/photons
    * Documentation is no longer github pages and is hosted on
      https://photons.delfick.com

    First, I renamed the ``afr`` object and replacing the ``run_with`` API.

    .. code-block:: python

        # before
        async with target.session() as afr:
            async for pkt, _, _ in target.script(DeviceMessages.SetPower()).run_with(reference, afr):
                print(pkt)

            results = in target.script(DeviceMessages.SetPower()).run_with_all(reference, afr):
            pkts = [pkt for pkt, _, _ in results]

        # after
        async with target.session() as sender:
            async for pkt in sender(DeviceMessages.SetPower(), reference)
                print(pkt)

            pkts = await sender(DeviceMessages.SetPower(), reference)

    Also creating the gatherer is much simpler now:

    .. code-block:: python

        # before
        from photons_control.planner import Gatherer, make_plans

        async with target.session() as afr:
            gatherer = Gatherer(target)
            plans = make_plans("capability")

            async for serial, label, info in gatherer.gather(plans, reference, afr):
                print(serial, label, info)

        # after
        async with target.session() as sender:
            plans = sender.make_plans("capability")

            async for serial, label, info in sender.gatherer.gather(plans, reference):
                print(serial, label, info)

    The DeviceFinder is now split into the Special Reference and Daemon it
    provides rather than both on the same object. This has a benefit of making
    it much easier to create a DeviceFinder special reference because it no
    longer needs a ``target`` object.

    Starting custom scripts is easier with the introduced ``photons_core.run``.

    .. code-block:: python

        # before
        if __name__ == "__main__":
            from photons_app.executor import main
            import sys

            main(["lan:my_task"] + sys.argv[1:])

        # after
        if __name__ == "__main__":
            __import__("photons_core").run("lan:my_task {@:1:}")

    The ``collector`` now has shortcuts for resolving a string into a target
    and a string into a Special Reference.

    The example scripts in the source code is now all under the ``examples``
    directory rather than spread across ``examples`` and ``scripts``.

    The ``photons_colour`` and colour related helpers in
    ``photons_control.attributes`` are now in ``photons_control.colour``.

    I've introduced some additional helpers in ``photons_app.helpers`` for
    working with asyncio tasks including the ability to stream results from
    multiple coroutines and async generators.

    The tile animations have also been rewritten from the ground up. The
    ``photons_themes`` and ``photons_tile_paint`` modules have been replaced
    with the ``photons_canvas`` module. ``ApplyTheme`` is now under
    ``photons_canvas.theme.ApplyTheme``. The programmatic and cli interface to
    animations is entirely different and explained in the documentation. The
    animations are now more capable, flexible and look a bit better.

    The ``photons_control.orientation`` module is now under
    ``photons_canvas.orientation``.

    Two new gatherer plans have been introduced: ``parts`` and
    ``parts_and_colors``. These return ``photons_canvas.points.containers.Part``
    objects which represent a single item in a chain. Devices that don't have
    chains (bulbs and strips) are represented as a single Part. The ``and_colors``
    plan will also record the current state of the device in the part object.

    Creating packets has changed slightly. Instead of
    ``photons_protocol.messages.Messages.unpack``, you have a ``create`` message
    that takes the same arguments.

    If you have a packet class already, the ``unpack``, ``empty_normalise`` and
    ``normalise`` methods have been replaced with a single ``create`` method.

    Finally, I have migrated the
    `photons interactor <https://photons-interactor.readthedocs.io/en/latest/>`_
    application into this codebase. As part of that I have split out the tile
    arranging into it's own app and remove the web UI from the interactor app.

.. _release-core-0-25-0:

0.25.0 - 8 March 2020
    * Added photons_control.planner.PacketPlan for making a plan that sends
      a message and returns a reply.
    * Made it easier to make long lived servers with more graceful shutdown.
      Usually you wait on ``photons_app.final_future`` to determine when to
      shutdown the server. Unfortunately this means that many resources that
      depend on this future to shutdown will also shutdown. Now you can do:

      .. code-block:: python

        from photons_app.errors import ApplicationStopped, UserQuit

        import asyncio

        with photons_app.using_graceful_future() as final_future:
            try:
                start_my_server()
                await final_future
            except ApplicationStopped:
                # Application got a SIGTERM
            except UserQuit:
                # The user did a ctrl-c
            except asyncio.CancelledError:
                # Something did photons_app.final_future.cancel()
            finally:
                # This is run before final_future is cancelled
                # Unless something already cancelled it!
    * Add a lan:power_toggle cli action for toggling the power of lights

.. _release-core-0-24-7:

0.24.7 - 23 February 2020
    * Introduced a ``transition_color`` option to the Transformer that says
      if we're going from off to on, then don't reset the color when we reset
      brightness before turning the device on. Many thanks to @Djelibeybi
    * The transform cli command now takes in ``transform_options`` so you can
      specify ``keep_brightness`` and ``transition_color``
    * Improved cleanup of sockets.

.. _release-core-0-24-6:

0.24.6 - 16 February 2020
    * Introduced the "colors" plan for getting the colors on devices with Single,
      Linear and Matrix zones.
    * Expanded the "chain" plan so that it would return a single chain "item"
      for devices with only a single "item" in the "chain"
    * The "capability" plan now also returns firmware information
    * The apply_theme action now works against candles
    * Rewrote all the tests to use pytest

.. _release-core-0-24-5:

0.24.5 - 9 January 2020
    * Fixed a mistake in the product registry
      (``LCM3_MINI2_WARM_WHITE`` should be ``WARM_TO_WHITE``)
    * Fixed multi options for the setting of strip Color Zones using legacy
      messages.

.. _release-core-0-24-4:

0.24.4 - 6 January 2020
    * Made it possible to override target options from the command line.

      For example::

        $ lifx 'lan(default_broadcast="10.1.1.255"):get_attr' _ color

   * Added a default ``chain`` plan for the Gatherer to use for getting tile
     chain information
   * FromGenerator can now be given a ``error_catcher_override`` option which
     is a function that takes in the ``reference`` being operated on and the
     original ``error_catcher``. It must return an ``error_catcher``. This can
     be used with say ``FromGeneratorPerSerial`` to generate an ``error_catcher``
     specifically for each serial.
   * Rewrote a few tasks to use Gatherer and FromGenerator objects to make
     them better
   * Added more products to the product registry

.. _release-core-0-24-3:

0.24.3 - 18 December 2019
    * Fixed a bug where response packets were matched to the wrong requests

.. _release-core-0-24-2:

0.24.2 - 16 December 2019
   * Fixed how retry options are created for sending messages

.. _release-core-0-24-1:

0.24.1 - 18 November 2019
   * Fixed discovery of originals
   * Allow ``--logging-program`` at the same time as ``--silent`` and ``--debug``

.. _release-core-0-24-0:

0.24.0 - 9 November 2019
   * Fixed how tagged and addressable are determined so that they are the
     correct values based on target when that is set after the packet has been
     created.
   * Changed how async generators are shutdown so it works with python3.8
   * Made photons compatible with python3.8

.. _release-core-0-23-0:

0.23.0 - 12 October 2019
   * Added large_font and speed options to the tile_marquee animation which
     allows a 16x16 font across two tile sets.
   * Changed photons_control.multizone.find_multizone to yield
     ``(serial, capability)`` instead of ``(serial, has_extended_multizone)``.
     You can get ``has_extended_multizone`` by saying ``capability.has_extended_multizone``
   * Changed the Capability plan to yield ``{"product": <Product>, "cap": <capability>}``
     instead of also yielding a ``has_extended_multizone`` field. You may get this
     by saying ``info["cap"].has_extended_multizone``
   * You should identify whether a product supports Tile messages by looking at
     the ``has_matrix`` capability instead of ``has_chain``. We may rename the
     Tile messages to be Matrix messages in the future, but that change has yet
     to be properly thought out. The ``has_matrix`` capability says there is a
     2d array of LEDs on the device. The ``has_chain`` capability now means that
     there are multiple devices that appear as a single device on the network.
   * Replaced the photons_products_registry module with the photons_products
     module. Essentially, you change code from first block to second block:

     .. code-block:: python

         from photons_products_registry import capability_for_ids, LIFIProductRegistry

         pid = LIFIProductRegistry.LCM3_TILE.pid
         vid = 1

         cap = capability_for_ids(pid, vid)
         assert cap.has_chain

         pid = LIFIProductRegistry.LCM2_Z.pid
         vid = 1

         cap = capability_for_ids(pid, vid)
         assert cap.has_multizone
         assert cap.has_extended_multizone(firmware_major=2, firmware_minor=77)

     .. code-block:: python

         from photons_products import Products

         product = Products.LCM3_TILE
         # or
         product = Products[1, 55]

         assert product.cap.has_matrix
         assert product.cap.has_chain

         # Accessing a name on Products that doesn't exist will raise an error
         # But if you do say Prodcuts[1, 9001] it'll just return a product that
         # defaults to essentially no capabilities. As this means old versions of
         # photons won't break when it sees new devices it doesn't know about

         product = Products.LCM2_Z
         assert cap.has_multizone

         # By default it'll assume firmware_major/firmware_minor of 0/0
         assert not cap.has_extended_multizone

         # But you can create a new capability object with different firmware
         assert cap(firmware_major=2, firmware_minor=77).has_extended_multizone

.. _release-core-0-22-1:

0.22.1 - 29 September 2019
   * Removed unnecessary errors from being written to the output when you
     ctrl-c a script (especially tile animations)
   * Slight fix to the tile_falling animation
   * Made receiving packets a little more efficient
   * Made tile animations consume considerably less CPU
   * Also made switches for making tile animations work better on noisy networks
   * When defining a tile animation, the ``acks`` option has been replaced by
     the ``replies`` option. When replies is True, messages will be retried.
   * Introduced ``collector.run_coro_as_main(coro)`` for running a coroutine as
     the mainline of a program. I also changed the scripts in the examples folder
     to use this method, and cleaned the code in that folder a little.
   * Another adjustment to shutdown logic to handle shuttind down async
     generators better
   * Added ``lifx lan:find_ips`` command
   * Fixed the broadcast option to run_with to allow ip addresses
   * Added discovery options for making photons see only particular devices and/or
     hard code discovery information for environments where broadcast discovery
     doesn't work so well.

.. _release-core-0-22-0:

0.22.0 - 21 September 2019
   * Changed the many option on packet definitions to multiple

     * this also means that array fields are now actually arrays and can be
       modified in place
   * Upgraded bitarray dependency

.. _release-core-0-21-0:

0.21.0 - 18 September 2019
   * Migrated to `delfick_project <https://delfick-project.readthedocs.io/>`_
   * this essentially means the following imports change from:

     .. code-block:: python

         from option_merge_addons import option_merge_addon_hook
         from input_algorithms.spec_base import NotSpecified
         from input_algorithms import spec_base as sb
         from input_algorithms.dictobj import dictobj
         from input_algorithms.meta import Meta
         from option_merge import MergedOptions

     into:

     .. code-block:: python

        from delfick_project.option_merge import MergedOptions
        from delfick_project.norms import dictobj, sb, Meta
        from delfick_project.addons import addon_hook

        NotSpecified = sb.NotSpecified

.. _release-core-0-20-5:

0.20.5 - 11 September 2019
   * Fix tile animations

.. _release-core-0-20-4:

0.20.4 - 2 September 2019
   * Photons code is now formatted by the black project

.. _release-core-0-20-3:

0.20.3 - 1 September 2019
   * Mainly just minor changes
   * Also, changed the transform functionality on packet definitions. This method
     is used to give a pack and an unpack function to the packet definition to
     transform values when going between the raw value and value used by the
     programmer. Previously only the pack received the packet being worked on,
     now both functions do.

.. _release-core-0-20-2:

0.20.2 - 17 July 2019
   * Added a hook to tile animations for overriding the default_color_func on
     the canvas

.. _release-core-0-20-1:

0.20.1 - 13 July 2019
   * Fixed a bug in the device finder when you use the same device finder more
     than once with a different filter. It was forgetting devices from one filter
     and making that device not there for a subsequent filter.

.. _release-core-0-20-0:

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

.. _release-core-0-13-5:

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

.. _release-core-0-13-4:

0.13.4 - 4 May 2019
   * Tiny fix to how we determine if we have enough multizone messages that
     shouldn't make a difference in practice.
   * Implemented a new "Planner" API for gathering information from devices
   * Making code in photons_control.multizone easier to re-use
   * Added a photons_control.tile.SetTileEffect helper for easily setting tile
     effects

.. _release-core-0-13-3:

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

.. _release-core-0-13-2:

0.13.2 - 7 April 2019
   * Fixed behaviour when you provide a list of complex messages to run_with
   * Made HardCodedSerials more efficient when the afr has already found devices

.. _release-core-0-13-0:

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

.. _release-core-0-12-1:

0.12.1 - 31 March 2019
    * Removed an unnecessary option from the implementation of Transformer

.. _release-core-0-12-0:

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

.. _release-core-0-11-0:

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

.. _release-core-0-10-2:

0.10.2 - 3 March 2019
    * Fixed a bug when applying a theme to multiple devices

.. _release-core-0-10-1:

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

.. _release-core-0-10-0:

0.10.0 - 23 January 2019
    * Started using ruamel.yaml instead of PyYaml to load configuration

.. _release-core-0-9-5:

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

.. _release-core-0-9-4:

0.9.4 - 3 January 2019
    * Added get_tile_positions action
    * Adjustments to the dice font
    * Added the scripts used to generate photons_messages

.. _release-core-0-9-3:

0.9.3 - 30 December 2018
    * Minor changes
    * Another efficiency improvement for tile animations
    * Some fixes to the scrolling animations
    * Make it possible to combine many tiles into one animation

.. _release-core-0-9-2:

0.9.2 - 27 December 2018
    * Made tile_marquee work without options
    * Made animations on multiple tiles recalculate the whole animation for each
      tile even if they have the same user coords
    * Fixed tile_dice_roll to work when you have specified multiple tiles
    * Take into account the orientation of the tiles when doing animations
    * apply_theme action takes tile orientation into account
    * Made tile_falling and tile_nyan animations take in a random_orientation
      option for choosing random orientations for each tile

.. _release-core-0-9-1:

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

.. _release-core-0-9-0:

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

.. _release-core-0-8-1:

0.8.1 - 2 December 2018
    * Added twinkles tile animation
    * Made it a bit easier to start animations programmatically

.. _release-core-0-8-0:

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

.. _release-core-0-7-1:

0.7.1 - 29 November 2018
    * Made it easier to construct a SetWaveFormOptional
    * Fix handling of sockets when the network goes away

.. _release-core-0-7-0:

0.7.0 - 10 November 2018
    Moved code into ``photons_control`` and ``photons_messages``. This means
    ``photons_attributes``, ``photons_device_messages``, ``photons_tile_messages``
    and ``photons_transform`` no longer exist.

    Anything related to messages in those modules (and in ``photons_sockets.messages``
    is now in ``photons_messages``.

    Everything else in those modules, and the actions from ``photons_protocol``
    are now in ``photons_control``.

.. _release-core-0-6-3:

0.6.3 - 10 November 2018
    * Fix potential hang when connecting to a device (very unlikely error case,
      but now it's handled).
    * Moved the __or__ functionality on packets onto the LIFXPacket object as
      it's implementation depended on fields specifically on LIFXPacket. This
      is essentially a no-op within photons.
    * Added a create helper to TransportTarget

.. _release-core-0-6-2:

0.6.2 - 22 October 2018
    * Fixed cleanup logic
    * Make products registry aware of kelvin ranges
    * Made defaults for values in a message definition go through the spec for
      that field when no value is specified
    * Don't raise an error if we can't find any devices, instead respect the
      error_catcher option and only raise errors for not finding each serial that
      we couldn't find

.. _release-core-0-6-1:

0.6.1 - 1 September 2018
    * Added the tile_gameoflife task for doing a Conway's game of life simulation
      on your tiles.

.. _release-core-0-6:

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

.. _release-core-0-5-11:

0.5.11 - 28 July 2018
    * Small fix to the version_number_spec for defining a version number on a
      protocol message
    * Made uvloop optional. To turn it off put ``photons_app: {use_uvloop: false}``
      in your configuration.

.. _release-core-0-5-10:

0.5.10 - 22 July 2018
    * Made version in StateHostFirmware and StateWifiFirmware a string instead
      of a float to tell the difference between "1.2" and "1.20"
    * Fix leaks of asyncio.Task objects

.. _release-core-0-5-9:

0.5.9 - 15 July 2018
    * Fixed a bug in the task runner such where a future could be given a result
      even though it was already done.
    * Made photons_app.helpers.ChildOfFuture behave as if it was cancelled when
      the parent future gets a non exception result. This is because ChildOfFuture
      is used to propagate errors/cancellation rather than propagate results.
    * Upgraded PyYaml and uvloop so that you can install this under python3.7
    * Fixes to make photons compatible with python3.7

.. _release-core-0-5-8:

0.5.8 - 1 July 2018
    * Fixed a bug I introduced in the Transformer in 0.5.7

.. _release-core-0-5-7:

0.5.7 - 1 July 2018
    * Fixed the FakeTarget in photons_app.test_helpers to deal with errors
      correctly
    * Made ``photons_transform.transformer.Transformer`` faster for most cases
      by making it not check the current state of the device when it doesn't
      need to

.. _release-core-0-5-6:

0.5.6 - 23 June 2018
    * photons_script.script.Repeater can now be stopped by raising Repater.Stop()
      in the on_done_loop callback
    * DeviceFinder can now be used to target specific serials

.. _release-core-0-5-5:

0.5.5 - 16 June 2018
    * Small fix to how as_dict() on a packet works so it does the right thing
      for packets that contain lists in the payload.
    * Added direction option to the marquee tile animation
    * Added nyan tile animation

.. _release-core-0-5-4:

0.5.4 - 28 April 2018
    * You can now specify ``("lifx.photon", "__all__")`` as a dependency and all
      photons modules will be seen as a dependency of your script.

      Note however that you should not do this in a module you expect to be used
      as a dependency by another module (otherwise you'll get cyclic dependencies).

.. _release-core-0-5-3:

0.5.3 - 22 April 2018
    * Tiny fix to TileState64 message

.. _release-core-0-5-2:

0.5.2 - 21 April 2018
    * Small fixes to the tile animations

.. _release-core-0-5-1:

0.5.1 - 31 March 2018
    * Tile animations
    * Added a ``serial`` property to packets that returns the hexlified target
      i.e. "d073d5000001" or None if target isn't set on the packet
    * Now installs and runs on Windows.

.. _release-core-0-5:

0.5 - 19 March 2018
    Initial opensource release after over a year of internal development.
