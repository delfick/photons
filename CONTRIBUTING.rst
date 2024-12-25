Contributing
============

Issues and Pull Requests are very welcome!

Here are some notes about the project that may help make pull requests easier to
merge.

The environment
---------------

Everything that is needed is available in a virtualenv in the current terminal
session by doing::

    > source run.sh activate

Even if this has been done before, doing it again will install new dependencies
if the version of Photons has changed.

The tests
---------

For the core tests run from any folder::

    > ./modules/test.sh

For the interactor tests run from any folder::

    > ./apps/interactor/test.sh

Alternatively tox may be used::

    > source run.sh activate
    > cd modules
    > tox

Tests are grouped by their module inside the ``tests`` folder. Note that we name
each folder as "<module>_tests" so that import statements for that module don't
get clobbered by these test files.

Code style
----------

We use the black project (https://black.readthedocs.io/en/stable/) to format the
python code in this repository.

All the developer needs to know is that either their editor is run in the same
session as a ``source run.sh activate`` or that they run::

   $ ./format

Import sorting
++++++++++++++

Photons uses default settings on isort to sort imports

Using import as
+++++++++++++++

I tend to import things directly, but I do tend to shortcut photons_app.helpers

.. code-block:: python

    from photons_app import helpers as hp

Linting
-------

I use pylama as my code linter and can be run from::

   $ ./lint

Commits
-------

Please follow Linus'
`guide <https://github.com/torvalds/subsurface-for-dirk/blob/a48494d2fbed58c751e9b7e8fbff88582f9b2d02/README#L88>`_
for good commit messages.

And also have in the title the module or app you are working on:

    interactor: Fix some memory leaks

    It's possible for python to hold onto frame objects via exceptions so I
    need to be more careful about holding onto those

Here the short description starts with a tag of sorts in square brackets and
a short sentence of what. Followed by a paragraph with how and why.

Comments
--------

Comments in code should explain why something is done more than what is being
done.

Exception is when code is very complicated and it may be difficult to understand
what is happening.

Variable names
--------------

It's incredibly important to try your best to name things consistently. No types
means when changes are made, this makes it a lot easy/possible to ensure that
you find all instances of something that must be changed.

Commented out code
------------------

Please do not commit commented out code. Delete it. It's in git history.

async context managers
----------------------

In Python, a context manager is a cleanup mechanism that uses the ``with`` syntax.

For example, instead of saying:

.. code-block:: python

    wrapper = MyWrapper()

    wrapper.start()
    try:
        do_something()
    finally:
        wrapper.finish()

You would write:

.. code-block:: python

    with MyWrapper() as wrapper:
        do_something()

An async context manager is the same, but uses the ``async/await`` syntax as
well:

.. code-block:: python

    async with MyWrapper() as wrapper:
        do_something()

Photons can create these in two ways.

The first way is using the standard library ``asynccontextmanager`` decorator.
Photons makes this available via ``photons_app.helpers`` to make it easier to
sync with public photons until the minimum version of Python supported by it is
Python3.7 as Python3.6 does not include that function in the standard library and
public photons must polyfill it.

.. code-block:: python

    from photons_app import helpers as hp

    
    @hp.asynccontextmanager
    async def wrap():
        try:
            await something_fun()
            yield
        finally:
            await some_cleanup()

The other way is via manually defining one in a class. The protocol in Python
for a context manager is ``__enter__()/__exit__(exc_typ, exc, tb)`` for
synchronous context managers and ``__aenter__()/__aexit__(exc_typ, exc, tb)`` for
asynchronous context managers.

In Python a context manager is the same as:

.. code-block:: python

    await wrapper.__aenter__()
    try:
        do_something()
    finally:
        await wrapper.__aexit__(...)

But for cleanup purposes it is useful to instead have:

.. code-block:: python

    try:
        await wrapper.__aenter__()
        do_something()
    finally:
        await wrapper.__aexit__(...)

To make this possible, Photons supplies ``hp.AsyncCMMixin`` and you implement
``start()/finish(exc_typ=None, exc=None, tb=None)``:

.. code-block:: python

    from photons_app import helpers as hp


    class Thing(hp.AsyncCMMixin):
        async def start(self):
            ...

        async def finish(self, exc_typ=None, exc=None, tb=None):
            ...

This means all async context managers in Photons will run finish even if an
exception is raised in start, and have ``start`` and ``finish`` if you are not
using the ``with`` syntax.

Visual studio code
==================

See ``.vscode/README.rst``.
