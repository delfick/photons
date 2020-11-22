.. _interactor_changelog:

Changelog
=========

0.7.6 - 22 November 2020
    * Update dependencies for python3.9 compatibility

0.7.5 - 6 November 2020
    * Updated photons-core for new products/protocol

0.7.4 - 22 September 2020
    * Reduced size of the docker image #22

0.7.3 - 23 August 2020
    * Upgrade photons-core to fix discovery bug

0.7.2 - 12 August 2020
    * Fixed bug where the program can enter a state of using all your CPU

0.7.1 - 9 August 2020
    * Using new photons code, including fixing memory leaks
    * Added ``group`` option to the ``power_toggle`` command

0.7.0 - 11 July 2020
    * Import from https://photons-interactor.readthedocs.io/en/latest/

        * Cleaned up code
        * Device discovery is more efficient and less noisy due to new photons
          code

    * Removed Web UI
    * Removed animation commands to be added back soon

0.6.3 - 8 March 2020
    * Added ``effects/run``, ``effects/stop`` and ``effects/status`` commands
    * Added ``power_toggle`` command
    * Updated lifx-photons-core
    * Shutdown of the server should be a bit more graceful now

0.6.2 - 27 February 2020
    * Updated lifx-photons-core
    * Added ``transform_options`` to the ``transform`` comannd. 

0.6.1 - 16 Februrary 2020
    * Updated lifx-photons-core

0.6.0 - 13 January 2020
    * Initial release to pypi
