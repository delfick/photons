.. _philosophy:

The approach taken by Photons
=============================

Unlike most LIFX libraries, Photons doesn't think in terms of device objects as
such, and instead operates entirely around sending and receiving messages.

This framework takes the opinion on not trusting the "known" state of a device
and so makes little effort to hold onto that data in a device object.

Photons focuses on providing a convenient API for working with messages, the
ability to address one or more devices at a time; and makes deciding what
messages to send as easy as possible.

Photons makes discovery, retries, inflight limits, handling multiple replies,
and error handling as transparent as possible to get out of your way in telling
devices to do something.
