.. _interactor_changelog:

Changelog
=========

.. _release-interactor-0-10-0:

0.10.0 - TBD
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
