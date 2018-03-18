.. _known_isues:

Known Issues
============

Startup Time
    Photons has a startup cost of about 0.4 seconds.

    This is because the module system uses pkg_resources entry_points.

    Unfortunately importing pkg_resources is slow. See
    https://github.com/pypa/setuptools/issues/510
