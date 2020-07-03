Photons Interactor
==================

A `Photons <https://delfick.github.io/photons-core>`_ powered server for
interacting with LIFX lights over the lan.

The server allows us to do continuous discovery and information gathering so that
all commands are super fast.

You can find documentation at https://photons-interactor.readthedocs.io

Installation and use
--------------------

Make sure you have a version of python greater than python3.6 and do::

    $ python -m venv .interactor
    $ source .interactor/bin/activate
    $ pip install lifx-photons-interactor
    $ lifx lan:interactor serve
    # go to http://localhost:6100

Running from a docker container
-------------------------------

If you're not on a mac and want to run via a docker container, you can say::

    $ docker run --name=photons \
        --detach \
        --restart=always \
        --net=host \
        -e TZ=Australia/Melbourne \
        delfick/lifx-photons-interactor:0.6.2

Replace `Australia/Melbourne` with the correct `TZ database name <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>`_ for your timezone.

If you want custom options then I suggest having a folder that looks like::

    custominteractor/
        interactor.yml
        Dockerfile

Where the docker file says::

   FROM delfick/lifx-photons-interactor:0.6.2
   ADD interactor.yml /project/interactor.yml

Then run::

    $ cd custominteractor
    $ docker build . -t custominteractor

    # Run the docker command mentioned above but say "custominteractor"
    # instead of "delfick/lifx-photons-interactor:0.6.2"

Also, with many thanks to @Djelibeybi this docker image will work on many
architectures, including a Raspberry Pi!

Running from the code
---------------------

You can find the code at https://github.com/delfick/photons/apps/arranger

Once you've checked it out you can start the server by installing python3.6 or
above and running from the root of the photons repo::
  
  $ python3 -m virtualenv ~/.photons-core
  $ source ~/.photons-core/bin/activate
  $ pip install -e modules
  $ pip install -e apps/interactor

You can also find a handy script for running commands against the server in
this repository called ``command``.

For example::
    
    $ ./command query '{"pkt_type": "GetColor"}'
    {
        "results": {
            "d073d5001337": {
                "payload": {
                    "brightness": 1.0,
                    "hue": 0.0,
                    "kelvin": 3500,
                    "label": "",
                    "power": 65535,
                    "saturation": 0.0
                },
                "pkt_name": "LightState",
                "pkt_type": 107
            }
        }
    }
