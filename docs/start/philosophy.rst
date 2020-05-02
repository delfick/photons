.. _philosophy:

The approach taken by Photons
=============================

Unlike most LIFX libraries, Photons thinks in terms of sending and receiving
packets onto the network, rather than providing objects that represent specific
devices.

Photons provides a convenient API for working with multiple devices at the same
time which makes it very efficient when getting and setting information on
multiple devices simultaneously.

Photons also makes discovery, retries, inflight limits, multiple replies
and error handling as transparent as possible to get out of your way while you
achieve your goals.
