.. _lifx_photons_venvstarter:

Using Venvstarter
=================

Dependency management in python works best when you use virtualenvs. You can
find more information about these over at http://docs.python-guide.org/en/latest/dev/virtualenvs/

To help manage virtualenvs I created a python library called
`venvstarter <https://venvstarter.readthedocs.io>`_ which allows you to manage
a virtualenv just by specifying what modules you want in that virtualenv in a
file and then executing that file will create or modify the virtualenv before
using it to launch some python application.

.. note:: venvstarter doesn't work on windows, so in that environment you'll
  have to create and manage your virtualenv yourself.

Usage is something like:

.. code-block:: text
 
    $ pip install venvstarter

And then create a file something like:

.. code-block:: python

    #!/usr/bin/env python3

    import os

    env = {
          "LIFX_CONFIG": os.environ.get("LIFX_CONFIG", "{venv_parent}/lifx.yml")
        }

    from venvstarter import ignite
    ignite(__file__, "lifx"
        , deps = ["lifx-photons-core==0.13.2"]
        , env = env
        , min_python_version = 3.6
        )

Make this file executable and run it. It'll make a virtualenv in a folder named
``.lifx`` next to this file with the virtualenv inside. It'll then make sure
``photons-core`` is installed in the virtualenv before doing an ``os.exec`` to
the ``lifx`` executable in the virtualenv.

The ``lifx`` executable in this case is provided by ``photons-core`` and is a
generic launcher for all the functionality provided by photons modules.

You can also activate this virtualenv by doing a ``source .lifx/bin/activate``
and then when you run the ``python`` executable, you are using the ``python``
from that virtualenv.
