.. _interactor_docker:

Running the Interactor from Docker
==================================

With many thanks to `@Djelibeybi <https://github.com/Djelibeybi>`_, a docker
image is available to run the interactor, which will work on many architectures
including a Raspberry Pi.

.. note:: It's not possible to discover devices on the network from a container
    running under Docker Desktop for macOS or Windows as multicasting is not
    supported. However, if you configure :ref:`hardcoded discovery <discovery>`,
    the rest of Interactor's functionality will work. You also need to replace
    ``--net=host`` with ``-p 6100:6100`` to allow inbound connections to the
    Interactor RESTful API.

The following may be used::

    $ docker run --name=photons \
        --detach \
        --restart=always \
        --net=host \
        -e TZ=Australia/Melbourne \
        -v "${PWD}/configdir":/project/config \
        delfick/lifx-photons-interactor:0.8.5

Replace ``Australia/Melbourne`` with the appropriate
`TZ database name <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>`_.

The ``-v configdir:/project/config`` part of that command isn't strictly
required and may be left out. It is useful if the server is used to create
scenes as these are saved in an sqlite3 database that will be put in that
folder by default.

By creating a directory (in this example, ``configdir`` in the current working
directory) this sqlite3 database will exist outside the docker container and
survive across running that docker command multiple times.

For custom options, that ``configdir`` directory may have a ``lifx.yml``
containing appropriate :ref:`options <interactor_options>`.
