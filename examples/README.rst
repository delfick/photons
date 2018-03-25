Unlike the examples in the ``scripts`` folder, these files use the ``library_setup``
helper to setup the photons framework.

These examples assume you're executing them in an environment that already has
``lifx-photons-core`` installed.

For example, run ``./setup_venv`` in this directory and then
``source .lifx/bin/activate`` before running say ``python make_rainbow.py``

Because these examples don't use the photons_app mainline all logging settings
are up to you to sort out. But you don't have to run your code from within a
photons task function.

Note that if you're on windows ``./setup_venv`` won't work. In that environment
you'll have to make your own virtualenv and ``pip install photons-core`` in it, 
or ``pip install -e .`` frm the ``photons-core`` directory.
