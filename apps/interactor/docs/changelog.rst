.. _interactor_changelog:

Changelog
=========

.. _release-interactor-0-16-0:

0.16.0 - 16 March 2024
    * Now using sanic instead of tornado
    * The v1 api remains, though some error messages are slightly different

.. _release-interactor-0-15-0:

0.15.0 - 2 January 2024
    * Photons is now python3.12+

.. _release-interactor-0-14-1:

0.14.1 - 29 December 2023
    * Fixed packaging instructions in pyproject.toml

.. _release-interactor-0-14-0:

0.14.0 - 2 December 2023
    * Photons is now python3.11+
    * Remove pkg_resources from dependent package

.. _release-interactor-0-13-0:

0.13.0 - 26 November 2023
    * Upgrade photons core for python 3.12 support

.. _release-interactor-0-12-8:

0.12.8 - 26 November 2023
    * Upgrade photons core to get String and Neon to the product registry

.. _release-interactor-0-12-7:

0.12.7 - 25 July 2023
    * Upgrade photons core to get new version of lru-dict dependency

.. _release-interactor-0-12-6:

0.12.6 - 11 February 2023
    * Upgrade photons core to get new products

.. _release-interactor-0-12-5:

0.12.5 - 20 November 2022
    * Added GET /v1/lifx/status that returns "working"
    * Removed prebuilt homeassistant image and changed the plugin to offer
      a Dockerfile that is built on installation instead

.. _release-interactor-0-12-4:

0.12.4 - 27 July 2022
    * Upgrade photons core to get new button messages

.. _release-interactor-0-12-3:

0.12.3 - 24 June 2022
    * Allow specifying direction when doing a zone effect

.. _release-interactor-0-12-2:

0.12.2 - 4 June 2022
    * Update dependencies of photons

.. _release-interactor-0-12-1:

0.12.1 - 13 February 2022
    * New products in the product registry

.. _release-interactor-0-12-0:

0.12.0 - 9 January 2022
    * Introduced options to exist as a base ZeroConf server (disabled by default)
    * Will benefit from changes to the device finder introduced in new version
      of the core of Photons

.. _release-interactor-0-11-0:

0.11.0 - 6 November 2021
    * Now python3.7+ and supports python3.10

.. _release-interactor-0-10-1:

0.10.1 - 16 October 2021
    * values in overrides when doing a scene_apply command will be ignored if
      they are set to null.

.. _release-interactor-0-10-0:

0.10.0 - 12 September 2021
    * Output from scene_capture no longer namespace'd by a "results" key
    * Migrated to asyncio sqlalchemy
    * Added ``clean/*`` commands from @Djelibeybi
    * Added ``daemon_options`` to the server options
    * Changed defaults time between queries to reduce CPU usage

      * Light state every 10 minutes instead of 10 seconds
      * Discovery every 30 minutes instead of 20 seconds

.. _release-interactor-0-9-1:

0.9.1 - 15 August 2021
    * Further fix applying scenes to candles

.. _release-interactor-0-9-0:

0.9.0 - 15 August 2021
    * Make scene capture and application aware of candles
    * Changed the input and output of scene_delete. You may now supply uuid as a
      single uuid, a list of uuids or a boolean true (to say all uuids).
      The output will always have uuid as a list of uuids that were deleted.

.. _release-interactor-0-8-7:

0.8.7 - 27 June 2021
    * Added ``matrix_options` and ``linear_options`` to the ``effects/stop``
      command with many thanks to @Djelibeybi

.. _release-interactor-0-8-6:

0.8.6 - 23 June 2021
    * Add help message for apply_theme option
    * Upgrade photons-core

.. _release-interactor-0-8-5:

0.8.5 - 15 April 2021
    * Improved logging

.. _release-interactor-0-8-4:

0.8.4 - 28 March 2021
    * Making the ``interactor`` task back to being called ``interactor``. It
      had been accidentally renamed in 0.8.3

.. _release-interactor-0-8-3:

0.8.3 - 28 March 2021
    * Update Photons and implement more graceful shutdown

.. _release-interactor-0-8-2:

0.8.2 - 15 March 2021
    * Update aiohttp dependency
    * Update Photons

.. _release-interactor-0-8-1:

0.8.1 - 3 January 2021
    * Adding LICENSE file to the package on pypi

.. _release-interactor-0-8-0:

0.8.0 - 26 December 2020
    * Update photons
    * Add commands for controlling animations

.. _release-interactor-0-7-9:

0.7.9 - 14 December 2020
    * update photons

.. _release-interactor-0-7-8:

0.7.8 - 5 December 2020
    * Update photons
    * Introduce a health check for the docker container

.. _release-interactor-0-7-7:

0.7.7 - 28 November 2020
    * Fixed some memory leaks in photons

.. _release-interactor-0-7-6:

0.7.6 - 22 November 2020
    * Update dependencies for python3.9 compatibility

.. _release-interactor-0-7-5:

0.7.5 - 6 November 2020
    * Updated photons-core for new products/protocol

.. _release-interactor-0-7-4:

0.7.4 - 22 September 2020
    * Reduced size of the docker image #22

.. _release-interactor-0-7-3:

0.7.3 - 23 August 2020
    * Upgrade photons-core to fix discovery bug

.. _release-interactor-0-7-2:

0.7.2 - 12 August 2020
    * Fixed bug where the program can enter a state of using all your CPU

.. _release-interactor-0-7-1:

0.7.1 - 9 August 2020
    * Using new photons code, including fixing memory leaks
    * Added ``group`` option to the ``power_toggle`` command

.. _release-interactor-0-7-0:

0.7.0 - 11 July 2020
    * Import from https://photons-interactor.readthedocs.io/en/latest/

        * Cleaned up code
        * Device discovery is more efficient and less noisy due to new photons
          code

    * Removed Web UI
    * Removed animation commands to be added back soon

.. _release-interactor-0-6-3:

0.6.3 - 8 March 2020
    * Added ``effects/run``, ``effects/stop`` and ``effects/status`` commands
    * Added ``power_toggle`` command
    * Updated lifx-photons-core
    * Shutdown of the server should be a bit more graceful now

.. _release-interactor-0-6-2:

0.6.2 - 27 February 2020
    * Updated lifx-photons-core
    * Added ``transform_options`` to the ``transform`` comannd. 

.. _release-interactor-0-6-1:

0.6.1 - 16 Februrary 2020
    * Updated lifx-photons-core

.. _release-interactor-0-6-0:

0.6.0 - 13 January 2020
    * Initial release to pypi
