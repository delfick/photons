.. _changelog:

ChangeLog
=========

0.5.6 - TBD
    * photons_script.script.Repeater can now be stopped by raising Repater.Stop()
      in the on_done_loop callback

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
